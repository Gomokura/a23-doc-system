"""
上传与解析接口 - 负责人: 成员1（路由层）
解析逻辑由成员2实现: modules/parser/document_parser.py
"""
import uuid
import os
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from db.models import FileRecord, TaskRecord
from main import AppError

router = APIRouter(tags=["文档上传与解析"])


# ── POST /upload ──────────────────────────────────────────────
@router.post("/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传文件，返回 file_id"""

    # 校验文件格式
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_extensions:
        raise AppError(400, "INVALID_FILE_TYPE", f"不支持的文件格式: .{ext}")

    # 校验文件大小
    content = await file.read()
    if len(content) > settings.max_file_size_mb * 1024 * 1024:
        raise AppError(400, "FILE_TOO_LARGE", f"文件超过 {settings.max_file_size_mb}MB 限制")

    # 保存文件
    file_id = str(uuid.uuid4())
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_path = os.path.join(settings.upload_dir, f"{file_id}.{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    # 写入数据库
    now = datetime.now(timezone.utc).isoformat()
    record = FileRecord(
        file_id=file_id,
        filename=file.filename,
        file_type=ext,
        file_path=file_path,
        status="uploaded",
        uploaded_at=now,
    )
    db.add(record)
    db.commit()

    return {"file_id": file_id, "filename": file.filename, "status": "uploaded"}


# ── POST /parse ───────────────────────────────────────────────
@router.post("/parse")
async def parse_file(body: dict, db: Session = Depends(get_db)):
    """提交解析任务（异步），立即返回 task_id，前端轮询 /parse/status/{task_id}"""

    file_id = body.get("file_id")
    if not file_id:
        raise AppError(400, "INVALID_REQUEST", "缺少 file_id 字段")

    record = db.query(FileRecord).filter_by(file_id=file_id).first()
    if not record:
        raise AppError(404, "FILE_NOT_FOUND", f"文件 {file_id} 不存在")

    # 创建任务记录
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    task = TaskRecord(
        task_id=task_id,
        file_id=file_id,
        task_type="parse",
        status="pending",
        progress=0,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()

    # 后台异步执行解析
    asyncio.create_task(_run_parse(task_id, file_id, record.file_path))

    return {"task_id": task_id, "file_id": file_id, "status": "pending"}


# ── GET /parse/status/{task_id} ───────────────────────────────
@router.get("/parse/status/{task_id}")
async def parse_status(task_id: str, db: Session = Depends(get_db)):
    """轮询解析任务状态，建议每2秒轮询一次"""
    task = db.query(TaskRecord).filter_by(task_id=task_id).first()
    if not task:
        raise AppError(404, "TASK_NOT_FOUND", f"任务 {task_id} 不存在")

    if task.status == "done":
        return {"status": "done", "file_id": task.file_id}
    elif task.status == "failed":
        return {"status": "failed", "error": task.error_msg}
    else:
        return {"status": task.status, "progress": task.progress}


# ── 后台解析任务（成员1写调度，成员2写 parse_document 函数）─────
async def _run_parse(task_id: str, file_id: str, file_path: str):
    """后台任务：调用成员2的解析模块，更新任务状态"""
    from db.database import SessionLocal
    db = SessionLocal()
    try:
        # 更新状态为 processing
        _update_task(db, task_id, status="processing", progress=10)

        # ── 调用成员2的模块 ──────────────────────────────────
        from modules.parser.document_parser import parse_document
        result = parse_document(file_path=file_path, file_id=file_id)
        # ────────────────────────────────────────────────────

        _update_task(db, task_id, status="processing", progress=70)

        # 调用成员3的索引模块
        from modules.retriever.indexer import build_index
        build_index(result)

        _update_task(db, task_id, status="processing", progress=90)

        # 更新文件状态
        record = db.query(FileRecord).filter_by(file_id=file_id).first()
        now = datetime.now(timezone.utc).isoformat()
        record.status = "indexed"
        record.chunk_count = len(result.get("chunks", []))
        record.parsed_at = now
        record.indexed_at = now
        db.commit()

        _update_task(db, task_id, status="done", progress=100)

    except Exception as e:
        _update_task(db, task_id, status="failed", error_msg=str(e))
    finally:
        db.close()


def _update_task(db, task_id, status, progress=None, error_msg=None):
    task = db.query(TaskRecord).filter_by(task_id=task_id).first()
    if task:
        task.status = status
        task.updated_at = datetime.now(timezone.utc).isoformat()
        if progress is not None:
            task.progress = progress
        if error_msg is not None:
            task.error_msg = error_msg
        db.commit()
