"""
文件管理接口 - 负责人: 成员1
GET /files                   查询已入库文档列表（支持分页 + 状态过滤）
DELETE /files/{file_id}      删除文档（级联清理磁盘/向量/任务记录）
"""
import os
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
