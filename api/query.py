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


@router.post("/cache/clear")
async def clear_cache():
    """清除所有问答缓存（文件更新后调用）"""
    from modules.cache.redis_client import invalidate_cache
    count = invalidate_cache("*")
    return {"cleared": count, "message": f"已清除 {count} 条缓存"}


@router.post("/cache/clear/{file_id}")
async def clear_file_cache(file_id: str, db: Session = Depends(get_db)):
    """
    精确清除指定文件的问答缓存（重新解析后调用，避免旧答案残留）。
    同时清该文件的缓存 + 重新解析并建索引。
    请求体（可选）: { "reparse": true }  → 重新解析该文件
    """
    record = db.query(FileRecord).filter_by(file_id=file_id).first()
    if not record:
        raise AppError(404, "FILE_NOT_FOUND", f"文件 {file_id} 不存在")

    # 清除涉及该文件的问答缓存
    from modules.cache.redis_client import invalidate_cache
    count = invalidate_cache(file_ids=[file_id])

    # 若请求体含 reparse=true，触发重新解析
    reparse = False  # 暂时禁用，防止误触发；由 /files/{file_id}/reparse 统一入口
    if reparse:
        asyncio.create_task(_reparse_file(file_id, record.file_path))
        return {"cleared": count, "file_id": file_id, "reparse": "triggered", "message": f"已清除 {count} 条缓存，重新解析任务已提交"}

    return {"cleared": count, "file_id": file_id, "message": f"已清除 {count} 条缓存"}


def _validate_file_ids(file_ids: list, db: Session):
    """校验文件存在且已索引，返回 (file_paths, file_name_map)
    file_name_map: {磁盘路径|basename: 真实文件名}
      - 完整路径用于结构化文件直接读取时的映射
      - basename 用于向量检索结果（ChromaDB metadata 只存 basename）
    """
    import os
    file_paths = []
    file_name_map = {}
    for fid in file_ids:
        record = db.query(FileRecord).filter_by(file_id=fid).first()
        if not record:
            raise AppError(404, "FILE_NOT_FOUND", f"文件 {fid} 不存在")
        if record.status != "indexed":
            raise AppError(409, "FILE_NOT_PARSED", f"文件 {fid} 尚未完成解析和索引，请先调用 /parse")
        file_paths.append(record.file_path)
        file_name_map[record.file_path] = record.filename           # 完整路径 → 真实名
        file_name_map[os.path.basename(record.file_path)] = record.filename  # basename → 真实名
    return file_paths, file_name_map


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

    file_paths = []
    file_name_map = {}
    if file_ids:
        file_paths, file_name_map = _validate_file_ids(file_ids, db)
    else:
        # 全库检索：构建所有已索引文件的 name map，避免返回 UUID 文件名
        import os
        for record in db.query(FileRecord).filter_by(status="indexed").all():
            file_name_map[record.file_path] = record.filename
            file_name_map[os.path.basename(record.file_path)] = record.filename

    from modules.retriever.hybrid_retriever import retrieve_and_answer
    result = retrieve_and_answer(query=query, file_ids=file_ids, file_paths=file_paths,
                                 scenario=scenario, file_name_map=file_name_map)
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

    file_paths = []
    file_name_map = {}
    if file_ids:
        file_paths, file_name_map = _validate_file_ids(file_ids, db)
    else:
        # 全库检索：构建所有已索引文件的 name map
        import os as _os
        for _rec in db.query(FileRecord).filter_by(status="indexed").all():
            file_name_map[_rec.file_path] = _rec.filename
            file_name_map[_os.path.basename(_rec.file_path)] = _rec.filename

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

            top_chunks = _hybrid_retrieve(query, file_ids, file_paths=file_paths, file_name_map=file_name_map)
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
            llm_client = OpenAI(
                api_key=settings.llm_api_key, 
                base_url=settings.llm_base_url,
                default_headers=settings.openai_default_headers
            )

            stream = llm_client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=1500,
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
                    "source_file": c.get("filename") or c["source_file"],  # 优先用真实文件名
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