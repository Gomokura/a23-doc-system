"""
问答接口 - 负责人: 成员1（路由层）
检索与问答逻辑由成员3实现: modules/retriever/hybrid_retriever.py
"""
import hashlib
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openai import OpenAI
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from db.models import FileRecord
from errors import AppError

router = APIRouter(tags=["智能问答"])


def _validate_file_ids(file_ids: list, db: Session):
    for fid in file_ids:
        record = db.query(FileRecord).filter_by(file_id=fid).first()
        if not record:
            raise AppError(404, "FILE_NOT_FOUND", f"文件 {fid} 不存在")
        if record.status != "indexed":
            raise AppError(409, "FILE_NOT_PARSED", f"文件 {fid} 尚未完成解析和索引，请先调用 /parse")


@router.post("/ask")
async def ask(body: dict, db: Session = Depends(get_db)):
    """
    同步问答接口
    请求体: { "query": "string", "file_ids": ["id1", "id2"], "scenario": "default|contract|report|regulation" }
    """
    query = body.get("query", "").strip()
    if not query:
        raise AppError(400, "INVALID_REQUEST", "query 不能为空")

    file_ids = body.get("file_ids", [])
    scenario = body.get("scenario", "default")

    if file_ids:
        _validate_file_ids(file_ids, db)

    from modules.retriever.hybrid_retriever import retrieve_and_answer
    result = retrieve_and_answer(query=query, file_ids=file_ids, scenario=scenario)
    return result


@router.post("/ask/stream")
async def ask_stream(body: dict, db: Session = Depends(get_db)):
    """
    流式问答接口（SSE 格式）
    事件: retrieval_done / token / done / error
    """
    query = body.get("query", "").strip()
    if not query:
        raise AppError(400, "INVALID_REQUEST", "query 不能为空")

    file_ids = body.get("file_ids", [])
    scenario = body.get("scenario", "default")

    if file_ids:
        _validate_file_ids(file_ids, db)

    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def event_generator():
        try:
            import numpy as np
            from modules.cache.redis_client import get_cached_result, set_cached_result
            from modules.retriever.hybrid_retriever import (
                _hybrid_retrieve,
                detect_conflicts,
                fuse_results,
                _build_prompt,
            )

            cache_key_raw = f"{query}|{sorted(file_ids)}|{scenario}"
            query_hash = hashlib.md5(cache_key_raw.encode()).hexdigest()
            cached = get_cached_result(query_hash)

            if cached:
                yield _sse("retrieval_done", {"chunks_count": len(cached.get("sources", [])), "cached": True})
                for char in cached.get("answer", ""):
                    yield _sse("token", {"content": char})
                yield _sse("done", {
                    "sources": cached.get("sources", []),
                    "confidence": cached.get("confidence", -1),
                    "fusion": cached.get("fusion", {}),
                })
                return

            top_chunks = _hybrid_retrieve(query, file_ids)
            yield _sse("retrieval_done", {"chunks_count": len(top_chunks), "cached": False})

            if not top_chunks:
                result = {
                    "query": query,
                    "answer": "根据提供的信息无法回答该问题。",
                    "sources": [],
                    "confidence": -1,
                    "fusion": {
                        "has_conflicts": False,
                        "conflict_count": 0,
                        "conflict_details": []
                    }
                }
                set_cached_result(query_hash, result)
                for char in result["answer"]:
                    yield _sse("token", {"content": char})
                yield _sse("done", {
                    "sources": result["sources"],
                    "confidence": result["confidence"],
                    "fusion": result["fusion"],
                })
                return

            prompt = _build_prompt(query, top_chunks, scenario=scenario)
            llm_client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

            stream = llm_client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
                stream=True,
            )

            full_answer = ""
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_answer += delta
                    yield _sse("token", {"content": delta})

            conflicts = detect_conflicts(top_chunks)
            top_chunks, fusion_info = fuse_results(top_chunks, conflicts)
            avg_score = float(np.mean([c["hybrid_score"] for c in top_chunks])) if top_chunks else 0.0
            confidence = round(min(avg_score * 1.2, 1.0), 2) if top_chunks else -1

            sources = [
                {
                    "chunk_id": c["chunk_id"],
                    "content": c["content"],
                    "source_file": c["source_file"],
                    "page": c["page"]
                }
                for c in top_chunks
            ]

            result = {
                "query": query,
                "answer": full_answer,
                "sources": sources,
                "confidence": confidence,
                "fusion": fusion_info,
            }
            set_cached_result(query_hash, result)

            yield _sse("done", {
                "sources": sources,
                "confidence": confidence,
                "fusion": fusion_info,
            })

        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")