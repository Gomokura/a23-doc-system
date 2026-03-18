"""
文件管理接口 - 负责人: 成员1
GET /files    查询已入库文档列表
DELETE /files/{file_id}  删除文档
"""
import os
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from db.models import FileRecord
from main import AppError

router = APIRouter(tags=["文件管理"])


# ── GET /files ────────────────────────────────────────────────
@router.get("/files")
async def list_files(status: str = "all", db: Session = Depends(get_db)):
    """
    查询已入库文档列表
    status 可选: uploaded | parsed | indexed | all（默认 all）
    """
    query = db.query(FileRecord)
    if status != "all":
        query = query.filter_by(status=status)

    records = query.all()
    files = [
        {
            "file_id":     r.file_id,
            "filename":    r.filename,
            "file_type":   r.file_type,
            "status":      r.status,
            "uploaded_at": r.uploaded_at,
            "chunk_count": r.chunk_count if r.chunk_count else None,
        }
        for r in records
    ]
    return {"files": files, "total": len(files)}


# ── DELETE /files/{file_id} ───────────────────────────────────
@router.delete("/files/{file_id}")
async def delete_file(file_id: str, db: Session = Depends(get_db)):
    """
    删除文档，同时清除：
    1. uploads/ 目录中的原始文件
    2. SQLite 中的文件记录
    3. ChromaDB 中该 file_id 的所有向量
    注意：outputs/ 中已生成的填表结果不删除
    """
    record = db.query(FileRecord).filter_by(file_id=file_id).first()
    if not record:
        raise AppError(404, "FILE_NOT_FOUND", f"文件 {file_id} 不存在")

    # 1. 删除本地文件
    if os.path.exists(record.file_path):
        os.remove(record.file_path)

    # 2. 删除 ChromaDB 向量（如果已索引）
    if record.status == "indexed":
        try:
            import chromadb
            client = chromadb.PersistentClient(path=settings.chroma_path)
            collection = client.get_or_create_collection("documents")
            collection.delete(where={"file_id": file_id})
        except Exception:
            pass  # ChromaDB 删除失败不影响主流程

    # 3. 删除 SQLite 记录
    db.delete(record)
    db.commit()

    return {"deleted": True, "file_id": file_id}
