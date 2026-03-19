"""
上传与解析接口 - 负责人: 成员1（路由层）
解析逻辑由成员2实现: modules/parser/document_parser.py
"""
import uuid
import os
import hashlib
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
 
from config import settings
from db.database import get_db
from db.models import FileRecord, TaskRecord
from errors import AppError
 
router = APIRouter(tags=["文档上传与解析"])
 
ALLOWED_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
 
 
def _safe_filename(filename: str) -> str:
    """去除路径符号，只保留安全文件名"""
    return os.path.basename(filename).replace("..", "").strip()
 
 
def _file_md5(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()
 
 
# ── POST /upload ──────────────────────────────────────────────
@router.post("/upload", summary="上传文件")
async def upload_file(
    file: UploadFile = File(..., description="支持 PDF / DOCX / XLSX"),
    db: Session = Depends(get_db),
):
    """
    上传文件，返回 file_id。
    - 自动校验格式与大小
    - 相同内容的文件不重复存储（MD5去重）
    """
    # ── 文件名安全处理 ──
    safe_name = _safe_filename(file.filename or "unnamed")
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
 
    if ext not in settings.allowed_extensions:
        raise AppError(400, "INVALID_FILE_TYPE", f"不支持的文件格式: .{ext}，允许: {settings.allowed_extensions}")
 
    # ── 读取内容 & 大小校验 ──
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_file_size_mb:
        raise AppError(400, "FILE_TOO_LARGE", f"文件 {size_mb:.1f}MB 超过 {settings.max_file_size_mb}MB 限制")
 
    # ── MD5去重：相同文件直接返回已有 file_id ──
    md5 = _file_md5(content)
    existing = db.query(FileRecord).filter_by(md5=md5).first()
    if existing:
        return {
            "file_id": existing.file_id,
            "filename": existing.filename,
            "status": existing.status,
            "duplicate": True,
        }
 
    # ── 保存文件 ──
    file_id = str(uuid.uuid4())
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_path = os.path.join(settings.upload_dir, f"{file_id}.{ext}")
    with open(file_path, "wb") as f:
        f.write(content)
 
    # ── 写入数据库 ──
    now = datetime.now(timezone.utc).isoformat()
    record = FileRecord(
        file_id=file_id,
        filename=safe_name,
        file_type=ext,
        file_path=file_path,
        file_size=len(content),
        md5=md5,
        status="uploaded",
        uploaded_at=now,
    )
    db.add(record)
    db.commit()
 
    return {
        "file_id": file_id,
        "filename": safe_name,
        "size_mb": round(size_mb, 2),
        "status": "uploaded",
        "duplicate": False,
    }
 
 
# ── POST /parse ───────────────────────────────────────────────
class ParseRequest(BaseModel):
    file_id: str
    priority: int = 1  # 预留优先级字段，默认普通优先级
 
 
@router.post("/parse", summary="提交解析任务")
async def parse_file(body: ParseRequest, db: Session = Depends(get_db)):
    """
    提交解析任务（异步），立即返回 task_id。
    前端每2秒轮询 GET /parse/status/{task_id}。
    """
    record = db.query(FileRecord).filter_by(file_id=body.file_id).first()
    if not record:
        raise AppError(404, "FILE_NOT_FOUND", f"文件 {body.file_id} 不存在")
 
    # 防止重复提交：同一文件已有 pending/processing 任务时直接返回
    existing_task = (
        db.query(TaskRecord)
        .filter_by(file_id=body.file_id, task_type="parse")
        .filter(TaskRecord.status.in_(["pending", "processing"]))
        .first()
    )
    if existing_task:
        return {
            "task_id": existing_task.task_id,
            "file_id": body.file_id,
            "status": existing_task.status,
            "message": "该文件已有进行中的解析任务",
        }
 
    # ── 创建任务记录 ──
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    task = TaskRecord(
        task_id=task_id,
        file_id=body.file_id,
        task_type="parse",
        status="pending",
        progress=0,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
 
    # ── 后台异步执行 ──
    asyncio.create_task(_run_parse(task_id, body.file_id, record.file_path))
 
    return {"task_id": task_id, "file_id": body.file_id, "status": "pending"}
 
 
# ── GET /parse/status/{task_id} ───────────────────────────────
@router.get("/parse/status/{task_id}", summary="查询解析任务状态")
async def parse_status(task_id: str, db: Session = Depends(get_db)):
    """
    轮询解析任务状态，建议每2秒一次。
    返回字段:
    - status: pending | processing | done | failed
    - progress: 0~100
    - chunk_count: 解析完成后的分块数量
    - error: 失败原因（仅 failed 时有）
    """
    task = db.query(TaskRecord).filter_by(task_id=task_id).first()
    if not task:
        raise AppError(404, "TASK_NOT_FOUND", f"任务 {task_id} 不存在")
 
    base = {
        "task_id": task_id,
        "file_id": task.file_id,
        "status": task.status,
        "progress": task.progress,
        "updated_at": task.updated_at,
    }
 
    if task.status == "done":
        file_record = db.query(FileRecord).filter_by(file_id=task.file_id).first()
        base["chunk_count"] = file_record.chunk_count if file_record else 0
    elif task.status == "failed":
        base["error"] = task.error_msg
 
    return base
 
 
# ── 后台解析任务 ──────────────────────────────────────────────
async def _run_parse(task_id: str, file_id: str, file_path: str):
    """
    后台任务调度：
      10% → 开始解析（成员2）
      70% → 解析完成，开始建索引（成员3）
      90% → 索引完成
     100% → done
    """
    from db.database import SessionLocal
    db = SessionLocal()
    try:
        _update_task(db, task_id, status="processing", progress=10)
 
        # ── 调用成员2：文档解析 ──────────────────────────────
        from modules.parser.document_parser import parse_document
        result = await asyncio.get_event_loop().run_in_executor(
            None, parse_document, file_path, file_id
        )
        # ────────────────────────────────────────────────────
 
        if not result or not result.get("chunks"):
            raise ValueError("解析结果为空，chunk 列表不能为空")
 
        _update_task(db, task_id, status="processing", progress=70)
 
        # ── 调用成员3：建立检索索引 ──────────────────────────
        from modules.retriever.indexer import build_index
        await asyncio.get_event_loop().run_in_executor(None, build_index, result)
        # ────────────────────────────────────────────────────
 
        _update_task(db, task_id, status="processing", progress=90)
 
        # ── 更新文件状态 ──
        record = db.query(FileRecord).filter_by(file_id=file_id).first()
        if record:
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
 
 
def _update_task(db, task_id: str, status: str, progress: int = None, error_msg: str = None):
    """原子更新任务状态"""
    task = db.query(TaskRecord).filter_by(task_id=task_id).first()
    if task:
        task.status = status
        task.updated_at = datetime.now(timezone.utc).isoformat()
        if progress is not None:
            task.progress = progress
        if error_msg is not None:
            task.error_msg = error_msg
        db.commit()