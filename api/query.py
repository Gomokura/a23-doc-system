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
    请求体: { "query": "string", "file_ids": ["id1", "id2"] }
    """
    query = body.get("query", "").strip()
    if not query:
        raise AppError(400, "INVALID_REQUEST", "query 不能为空")

    file_ids = body.get("file_ids", [])
    if file_ids:
        _validate_file_ids(file_ids, db)

    from modules.retriever.hybrid_retriever import retrieve_and_answer
    result = retrieve_and_answer(query=query, file_ids=file_ids)
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
            from modules.cache.redis_client import get_cached_result, set_cached_result
            from modules.retriever.hybrid_retriever import (
                _get_embed_model, _vector_search, _bm25_search,
                get_adaptive_weights, rerank_chunks, detect_conflicts,
                fuse_results, _build_prompt,
            )
            import concurrent.futures
            import numpy as np

            # 缓存检查
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

            # 检索
            model = _get_embed_model()
            query_embedding = model.encode(query).tolist()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                vector_future = executor.submit(_vector_search, query, query_embedding, file_ids)
                bm25_future = executor.submit(_bm25_search, query)
                vector_chunks = vector_future.result()
                bm25_scores_map, bm25_doc_map = bm25_future.result()

            weight_vector, weight_bm25 = get_adaptive_weights(query)
            scored_chunks = []
            seen_contents = set()
            for vc in vector_chunks:
                content = vc["content"]
                if content in seen_contents:
                    continue
                seen_contents.add(content)
                chunk_id = vc["chunk_id"]
                vector_score = vc.get("vector_score", 0)
                bm25_score = bm25_scores_map.get(chunk_id, 0)
                max_bm25 = max(bm25_scores_map.values()) if bm25_scores_map else 1
                bm25_score_norm = bm25_score / (max_bm25 or 1)
                vc["hybrid_score"] = vector_score * weight_vector + bm25_score_norm * weight_bm25
                doc_info = bm25_doc_map.get(chunk_id, {})
                vc["content"] = doc_info.get("content", content)
                vc["source_file"] = doc_info.get("source_file", vc.get("source_file", ""))
                vc["page"] = doc_info.get("page", vc.get("page", 0))
                vc["bm25_score"] = bm25_score
                scored_chunks.append(vc)

            scored_chunks.sort(key=lambda x: x["hybrid_score"], reverse=True)
            top_chunks = scored_chunks[:settings.top_k]
            top_chunks = rerank_chunks(query, top_chunks)

            yield _sse("retrieval_done", {"chunks_count": len(top_chunks), "cached": False})

            # LLM 流式生成
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

            # 完成
            conflicts = detect_conflicts(top_chunks)
            top_chunks, fusion_info = fuse_results(top_chunks, conflicts)
            avg_score = float(np.mean([c["hybrid_score"] for c in top_chunks])) if top_chunks else 0
            confidence = round(min(avg_score * 1.2, 1.0), 2)
            sources = [
                {"chunk_id": c["chunk_id"], "content": c["content"],
                 "source_file": c["source_file"], "page": c["page"]}
                for c in top_chunks
            ]
            yield _sse("done", {"sources": sources, "confidence": confidence, "fusion": fusion_info})

            set_cached_result(query_hash, {
                "query": query, "answer": full_answer,
                "sources": sources, "confidence": confidence, "fusion": fusion_info,
            })

        except Exception as e:
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")