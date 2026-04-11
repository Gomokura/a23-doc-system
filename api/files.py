"""
文件管理接口 - 负责人: 成员1
GET /files                   查询已入库文档列表（支持分页 + 状态过滤）
DELETE /files/{file_id}       删除文档（级联清理磁盘/向量/任务记录）
POST /files/{file_id}/reparse 重新解析文档（清除旧索引 + 重新解析 + 建向量 + 清缓存）
"""
import os
import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from db.models import FileRecord, TaskRecord
from errors import AppError

router = APIRouter(tags=["文件管理"])

# ── ChromaDB 单例，避免每次请求重建 client ─────────────────────
_chroma_collection = None

def _get_chroma_collection():
    global _chroma_collection
    if _chroma_collection is None:
        import chromadb
        client = chromadb.PersistentClient(path=settings.chroma_path)
        _chroma_collection = client.get_or_create_collection("documents")
    return _chroma_collection


# ── 状态枚举，防止非法值 ───────────────────────────────────────
class FileStatus(str, Enum):
    all      = "all"
    uploaded = "uploaded"
    parsed   = "parsed"
    indexed  = "indexed"


# ── GET /files ────────────────────────────────────────────────
@router.get("/files", summary="查询文档列表")
async def list_files(
    status: FileStatus = Query(FileStatus.all, description="状态过滤: uploaded | parsed | indexed | all"),
    page:   int        = Query(1,  ge=1,   description="页码，从 1 开始"),
    size:   int        = Query(20, ge=1, le=100, description="每页条数，最大 100"),
    db: Session = Depends(get_db),
):
    """
    查询已入库文档列表，支持状态过滤与分页。
    """
    query = db.query(FileRecord)
    if status != FileStatus.all:
        query = query.filter_by(status=status.value)

    total = query.count()
    records = query.offset((page - 1) * size).limit(size).all()

    files = [
        {
            "file_id":     r.file_id,
            "filename":    r.filename,
            "file_type":   r.file_type,
            "file_size":   r.file_size,
            "status":      r.status,
            "chunk_count": r.chunk_count or 0,
            "uploaded_at": r.uploaded_at,
            "parsed_at":   r.parsed_at,
            "indexed_at":  r.indexed_at,
        }
        for r in records
    ]
    return {
        "files": files,
        "total": total,
        "page":  page,
        "size":  size,
        "pages": (total + size - 1) // size,
    }


# ── DELETE /files/{file_id} ───────────────────────────────────
@router.delete("/files/{file_id}", summary="删除文档")
async def delete_file(file_id: str, db: Session = Depends(get_db)):
    """
    删除文档，级联清理：
    1. uploads/ 目录中的原始文件
    2. SQLite 中的文件记录及关联任务记录
    3. ChromaDB 中该 file_id 的所有向量
    注意：outputs/ 中已生成的填表结果不删除
    """
    record = db.query(FileRecord).filter_by(file_id=file_id).first()
    if not record:
        raise AppError(404, "FILE_NOT_FOUND", f"文件 {file_id} 不存在")

    # 1. 删除本地文件
    if os.path.exists(record.file_path):
        os.remove(record.file_path)

    # 2. 删除 ChromaDB 向量（复用单例 client）
    if record.status == "indexed":
        try:
            collection = _get_chroma_collection()
            collection.delete(where={"file_id": file_id})
        except Exception:
            pass

    # 3. 级联删除关联任务记录
    db.query(TaskRecord).filter_by(file_id=file_id).delete()

    # 4. 删除 SQLite 文件记录
    db.delete(record)
    db.commit()

    return {"deleted": True, "file_id": file_id}


# ── POST /files/{file_id}/reparse ────────────────────────────────
@router.post("/files/{file_id}/reparse", summary="重新解析文档")
async def reparse_file(file_id: str, db: Session = Depends(get_db)):
    """
    重新解析文档（用于更换解析器 / 重新上传后重建索引）。

    流程：
    1. 从 ChromaDB 删除该文件旧向量
    2. 重置 FileRecord.status = "uploaded"
    3. 提交新解析任务
    4. 清除该文件的问答缓存

    注意：不重新上传文件，只用磁盘上已有的原文件。
    """
    record = db.query(FileRecord).filter_by(file_id=file_id).first()
    if not record:
        raise AppError(404, "FILE_NOT_FOUND", f"文件 {file_id} 不存在")

    if not os.path.exists(record.file_path):
        raise AppError(400, "FILE_NOT_FOUND_ON_DISK", f"原始文件不存在: {record.file_path}，请重新上传")

    # 1. 删除 ChromaDB 旧向量
    if record.status == "indexed":
        try:
            collection = _get_chroma_collection()
            collection.delete(where={"file_id": file_id})
        except Exception as e:
            pass  # 无旧索引时 ChromaDB 会报错，忽略

    # 2. 清除该文件的问答缓存
    try:
        from modules.cache.redis_client import invalidate_cache
        invalidate_cache(file_ids=[file_id])
    except Exception:
        pass

    # 3. 重置状态，触发重新解析
    record.status = "uploaded"
    record.chunk_count = None
    record.parsed_at = None
    record.indexed_at = None
    db.commit()

    # 4. 提交新解析任务（复用 upload.py 的 _run_parse 逻辑）
    from db.models import TaskRecord
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

    asyncio.create_task(_run_file_parse(task_id, file_id, record.file_path))

    return {
        "file_id": file_id,
        "task_id": task_id,
        "status": "pending",
        "message": "重新解析任务已提交，请轮询 GET /parse/status/" + task_id,
    }


# ── 后台重新解析任务（复用 upload.py 逻辑，差异：不清旧文件磁盘）───
async def _run_file_parse(task_id: str, file_id: str, file_path: str):
    """
    与 upload.py 中 _run_parse 相同逻辑，但：
    - 不重新上传文件
    - 不删除旧磁盘文件
    - 直接复用自己的源文件路径解析
    """
    from db.database import SessionLocal
    db = SessionLocal()
    try:
        _update_parse_task(db, task_id, status="processing", progress=5)

        def _on_parse_progress(pct: int, msg: str):
            mapped = min(49, max(10, pct))
            _update_parse_task(db, task_id, status="processing", progress=mapped)

        from modules.parser.document_parser import parse_document
        result = await asyncio.get_event_loop().run_in_executor(
            None, parse_document, file_path, file_id, _on_parse_progress
        )

        if not result or not result.get("chunks"):
            raise ValueError("解析结果为空")

        _update_parse_task(db, task_id, status="processing", progress=50)

        from modules.retriever.indexer import build_index

        def _on_index_progress(pct: int, msg: str):
            mapped = min(89, max(70, pct))
            _update_parse_task(db, task_id, status="processing", progress=mapped)

        ok = await asyncio.get_event_loop().run_in_executor(
            None, build_index, result, True, _on_index_progress
        )
        if not ok:
            raise RuntimeError("向量索引构建失败")

        _update_parse_task(db, task_id, status="processing", progress=90)

        record = db.query(FileRecord).filter_by(file_id=file_id).first()
        if record:
            now = datetime.now(timezone.utc).isoformat()
            record.status = "indexed"
            record.chunk_count = len(result.get("chunks", []))
            record.parsed_at = now
            record.indexed_at = now
            db.commit()

        try:
            from modules.cache.redis_client import invalidate_cache
            invalidate_cache(file_ids=[file_id])
        except Exception:
            pass

        _update_parse_task(db, task_id, status="done", progress=100)

    except Exception as e:
        _update_parse_task(db, task_id, status="failed", error_msg=str(e))
    finally:
        db.close()


def _update_parse_task(db, task_id: str, status: str, progress: int = None, error_msg: str = None):
    """原子更新解析任务状态"""
    task = db.query(TaskRecord).filter_by(task_id=task_id).first()
    if task:
        task.status = status
        task.updated_at = datetime.now(timezone.utc).isoformat()
        if progress is not None:
            task.progress = progress
        if error_msg is not None:
            task.error_msg = error_msg
        db.commit()

