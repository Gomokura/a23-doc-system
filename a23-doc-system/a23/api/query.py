"""
问答接口 - 负责人: 成员1（路由层）
检索与问答逻辑由成员3实现: modules/retriever/hybrid_retriever.py
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import json

from db.database import get_db
from db.models import FileRecord
from errors import AppError

router = APIRouter(tags=["智能问答"])


# ── POST /ask ─────────────────────────────────────────────────
@router.post("/ask")
async def ask(body: dict, db: Session = Depends(get_db)):
    """
    同步问答接口
    请求体: { "query": "string", "file_ids": ["id1", "id2"] }
    file_ids 为空列表时检索所有已入库文档
    """
    query = body.get("query", "").strip()
    if not query:
        raise AppError(400, "INVALID_REQUEST", "query 不能为空")

    file_ids = body.get("file_ids", [])

    # 校验 file_ids 是否存在且已索引
    if file_ids:
        for fid in file_ids:
            record = db.query(FileRecord).filter_by(file_id=fid).first()
            if not record:
                raise AppError(404, "FILE_NOT_FOUND", f"文件 {fid} 不存在")
            if record.status != "indexed":
                raise AppError(409, "FILE_NOT_PARSED", f"文件 {fid} 尚未完成解析和索引，请先调用 /parse")

    # ── 调用成员3的模块 ──────────────────────────────────────
    from modules.retriever.hybrid_retriever import retrieve_and_answer
    result = retrieve_and_answer(query=query, file_ids=file_ids)
    # ────────────────────────────────────────────────────────

    return result


# ── POST /ask/stream ──────────────────────────────────────────
@router.post("/ask/stream")
async def ask_stream(body: dict, db: Session = Depends(get_db)):
    """
    流式问答接口（SSE格式）- 可选，有余力再实现
    前端接收: text/event-stream
    """
    query = body.get("query", "").strip()
    if not query:
        raise AppError(400, "INVALID_REQUEST", "query 不能为空")

    file_ids = body.get("file_ids", [])

    async def event_generator():
        # ── 调用成员3的流式模块（如果实现了的话）───────────
        # 目前返回占位响应，成员3实现后替换
        chunks = ["正在", "检索", "相关", "文档", "..."]
        for chunk in chunks:
            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'sources': [], 'confidence': -1}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
