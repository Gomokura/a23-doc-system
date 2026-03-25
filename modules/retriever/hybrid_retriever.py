"""
混合检索与问答模块 - 负责人: 成员3
函数签名已锁定，不得更改
"""
import concurrent.futures
import copy
import hashlib
import time
from typing import Optional, Tuple, Dict, List

import jieba
import numpy as np
from loguru import logger
from openai import OpenAI
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from config import settings
from modules.retriever.indexer import (
    get_bm25_records,
    get_collection,
    _get_embed_model,
)

# ═══════════════════════════════════════════════════════════════════════
# ReRanker 配置
# ═══════════════════════════════════════════════════════════════════════
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANKER_TOP_K = 5

# ═══════════════════════════════════════════════════════════════════════
# 中文分词配置
# ═══════════════════════════════════════════════════════════════════════
STOPWORDS = set([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "那", "里", "为", "什么", "可以", "这个", "那个", "但是", "还是",
    "如果", "因为", "所以", "但是", "而", "与", "及", "或", "等", "于", "从", "以",
    "及", "其", "被", "由", "对", "将", "把", "向", "给", "用", "通过", "进行",
    "。", "，", "！", "？", "、", "\"", "“", "”", "‘", "’", "：", "；", "（", "）",
    "【", "】", "[", "]", "{", "}", "/", "\\", "-", "_", "+", "=", "*", "#",
    "@", "$", "%", "^", "&", "~", "`", "<", ">", "|", "\n", "\t", " ", "  ",
])


def tokenize_chinese(text: str, remove_stopwords: bool = True) -> list:
    if not text:
        return []

    tokens = list(jieba.cut(text, cut_all=False))

    if remove_stopwords:
        tokens = [t.strip() for t in tokens if t.strip() and t.strip() not in STOPWORDS]
    else:
        tokens = [t.strip() for t in tokens if t.strip()]

    return tokens


def _normalize_scores(scores: list) -> list:
    """Min-Max 归一化得分到 [0, 1]"""
    if not scores:
        return []
    min_s, max_s = min(scores), max(scores)
    if max_s == min_s:
        return [1.0] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]


# ═══════════════════════════════════════════════════════════════════════
# 自适应权重配置
# ═══════════════════════════════════════════════════════════════════════
QUERY_TOKEN_THRESHOLD = 5
WEIGHT_VECTOR_SHORT = 0.4
WEIGHT_BM25_SHORT = 0.6
WEIGHT_VECTOR_LONG = 0.7
WEIGHT_BM25_LONG = 0.3


def get_adaptive_weights(query: str) -> Tuple[float, float]:
    tokens = tokenize_chinese(query, remove_stopwords=False)
    token_count = len(tokens)

    if token_count > QUERY_TOKEN_THRESHOLD:
        weight_vector = WEIGHT_VECTOR_LONG
        weight_bm25 = WEIGHT_BM25_LONG
        logger.info(f"自适应权重 [长查询 {token_count} 词]: vector={weight_vector}, bm25={weight_bm25}")
    else:
        weight_vector = WEIGHT_VECTOR_SHORT
        weight_bm25 = WEIGHT_BM25_SHORT
        logger.info(f"自适应权重 [短查询 {token_count} 词]: vector={weight_vector}, bm25={weight_bm25}")

    return weight_vector, weight_bm25


# ═══════════════════════════════════════════════════════════════════════
# CrossEncoder ReRanker
# ═══════════════════════════════════════════════════════════════════════
_reranker_model: Optional[CrossEncoder] = None


def _get_reranker() -> CrossEncoder:
    global _reranker_model
    if _reranker_model is None:
        model_name = getattr(settings, "reranker_model", None) or RERANKER_MODEL
        logger.info(f"加载 ReRanker 模型: {model_name}")
        _reranker_model = CrossEncoder(model_name)
    return _reranker_model


def rerank_chunks(query: str, chunks: list, top_k: int = None) -> list:
    if not chunks:
        return []

    top_k = top_k or getattr(settings, "reranker_top_k", None) or RERANKER_TOP_K

    if not getattr(settings, "reranker_enabled", False):
        logger.debug("ReRanker 未启用，返回原始排序")
        return chunks[:top_k]

    if len(chunks) <= top_k:
        return chunks

    try:
        reranker = _get_reranker()
        pairs = [(query, chunk.get("content", "")) for chunk in chunks]
        scores = reranker.predict(pairs)

        for i, chunk in enumerate(chunks):
            chunk["rerank_score"] = float(scores[i])

        reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
        logger.info(f"ReRanker 完成: {len(chunks)} → {top_k} 条，得分范围 [{min(scores):.3f}, {max(scores):.3f}]")
        return reranked[:top_k]

    except Exception as e:
        logger.warning(f"ReRanker 失败: {e}，返回原始排序")
        return chunks[:top_k]


def _build_prompt(query: str, chunks: list, scenario: str = "default") -> str:
    context = "\n\n".join([
        f"[文档{i + 1}]\n{c['content']}"
        for i, c in enumerate(chunks)
    ])

    scenario_prompts = {
        "contract": "5. 如果涉及合同条款，请重点识别：合同金额、甲乙双方、付款方式、违约责任、有效期。",
        "report": "5. 如果涉及报表数据，请进行数据对比、趋势描述，注明计量单位。",
        "regulation": "5. 如果涉及法规条文，请引用相关条款，说明适用范围和时效性。",
    }
    extra_requirement = scenario_prompts.get(scenario, "")

    return f"""你是一个专业的文档问答助手。请根据以下参考文档，回答用户的问题。

## 参考文档
{context}

## 用户问题
{query}

## 回答要求
1. 基于参考文档内容回答，不要编造信息
2. 如果文档中没有相关内容，请明确说明"根据提供的信息无法回答该问题"
3. 回答要准确、简洁、有条理
4. 在回答中引用相关文档来源
{extra_requirement}

## 回答格式
回答: <你的回答>
来源: <列出参考的文档编号，如 [文档1]、[文档2]>"""


def detect_conflicts(chunks: list) -> list:
    conflicts = []

    key_patterns = [
        ("金额", [r"(\d+\.?\d*万)", r"(¥?\d+)"]),
        ("日期", [r"(\d{4}年\d{1,2}月\d{1,2}日)", r"(\d{4}-\d{2}-\d{2})"]),
        ("比例", [r"(\d+\.?\d*%)", r"(\d+)%"]),
        ("公司名", [r"([^\s]{4,}公司)", r"([^\s]{2,}贸易)", r"([^\s]{2,}科技)"]),
    ]

    for key_name, patterns in key_patterns:
        import re
        value_to_chunks = {}

        for chunk in chunks:
            content = chunk.get("content", "")
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    val = match.strip()
                    if val and len(val) > 1:
                        value_to_chunks.setdefault(val, []).append(chunk.get("chunk_id", ""))

        if len(value_to_chunks) > 1:
            conflicts.append({
                "key": key_name,
                "values": list(value_to_chunks.keys()),
                "from_chunks": list(value_to_chunks.values())
            })

    return conflicts


def fuse_results(top_chunks: list, conflicts: list) -> tuple:
    fusion_info = {
        "has_conflicts": len(conflicts) > 0,
        "conflict_count": len(conflicts),
        "conflict_details": conflicts
    }

    if not conflicts:
        return top_chunks, fusion_info

    for chunk in top_chunks:
        chunk_id = chunk.get("chunk_id", "")
        chunk_conflicts = []
        for cf in conflicts:
            for cid_list in cf["from_chunks"]:
                if chunk_id in cid_list:
                    chunk_conflicts.append({
                        "key": cf["key"],
                        "values": cf["values"]
                    })
        chunk["has_conflict"] = len(chunk_conflicts) > 0
        chunk["related_conflicts"] = chunk_conflicts

    return top_chunks, fusion_info


def distance_to_score(distance: float, method: str = "exp") -> float:
    if distance is None or distance < 0:
        return 0.0

    if method == "exp":
        return float(np.exp(-distance))
    return 1.0 / (1.0 + distance)


def _vector_search(query: str, query_embedding: list, file_ids: list) -> list:
    """
    向量检索（独立函数，供并行调用）
    """
    collection = get_collection()

    vector_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=settings.top_k * 2,
        where={"file_id": {"$in": file_ids}} if file_ids else None
    )

    vector_chunks = []
    if vector_results and vector_results.get("ids"):
        ids = vector_results["ids"][0]
        documents = vector_results.get("documents", [[]])[0]
        metadatas = vector_results.get("metadatas", [[]])[0]
        distances = vector_results.get("distances", [[]])[0]

        for i, chunk_id in enumerate(ids):
            metadata = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            vector_chunks.append({
                "chunk_id": chunk_id,
                "content": documents[i] if i < len(documents) else "",
                "source_file": metadata.get("source_file", ""),
                "page": metadata.get("page", 0),
                "distance": distances[i] if i < len(distances) else 0,
                "vector_score": distance_to_score(distances[i]) if i < len(distances) else 0
            })

    logger.info(f"向量检索完成: 获取 {len(vector_chunks)} 条结果")
    return vector_chunks


# ═══════════════════════════════════════════════════════════════════════
# BM25 运行时缓存
# ═══════════════════════════════════════════════════════════════════════
_BM25_CACHE_VALID = False
_BM25_INDEX: Optional[BM25Okapi] = None
_BM25_CACHE_KEY = None
_BM25_RECORDS: list = []
_TOKENIZED_CORPUS: list = []


def invalidate_bm25_runtime_cache():
    global _BM25_CACHE_VALID, _BM25_INDEX, _BM25_CACHE_KEY, _BM25_RECORDS, _TOKENIZED_CORPUS
    _BM25_CACHE_VALID = False
    _BM25_INDEX = None
    _BM25_CACHE_KEY = None
    _BM25_RECORDS = []
    _TOKENIZED_CORPUS = []
    logger.info("BM25 运行时缓存已失效")


def _ensure_bm25_ready(file_ids: list = None):
    global _BM25_INDEX, _TOKENIZED_CORPUS, _BM25_CACHE_VALID, _BM25_CACHE_KEY, _BM25_RECORDS

    cache_key = tuple(sorted(file_ids)) if file_ids else "__all__"

    if _BM25_CACHE_VALID and _BM25_INDEX is not None and _BM25_CACHE_KEY == cache_key:
        return

    records = get_bm25_records(file_ids)
    _BM25_RECORDS = records

    if not records:
        _BM25_INDEX = None
        _TOKENIZED_CORPUS = []
        _BM25_CACHE_VALID = True
        _BM25_CACHE_KEY = cache_key
        return

    corpus = [r["content"] for r in records]
    _TOKENIZED_CORPUS = [tokenize_chinese(doc, remove_stopwords=True) for doc in corpus]
    _BM25_INDEX = BM25Okapi(_TOKENIZED_CORPUS)
    _BM25_CACHE_VALID = True
    _BM25_CACHE_KEY = cache_key

    logger.info(f"BM25 索引预构建完成: {len(records)} 条文档, file_filter={cache_key}")


def _bm25_search(query: str, file_ids: list = None) -> Tuple[dict, dict]:
    """
    BM25 检索（独立函数，供并行调用）
    支持 file_ids 过滤，并直接返回 chunk_id -> score 映射
    """
    _ensure_bm25_ready(file_ids)

    bm25_scores_map = {}
    bm25_doc_map = {}

    if not _BM25_RECORDS or _BM25_INDEX is None:
        return bm25_scores_map, bm25_doc_map

    tokenized_query = tokenize_chinese(query, remove_stopwords=True)
    logger.info(f"BM25 分词结果: query='{query}' -> {tokenized_query}")

    raw_scores = _BM25_INDEX.get_scores(tokenized_query)

    for record, score in zip(_BM25_RECORDS, raw_scores):
        chunk_id = record["chunk_id"]
        bm25_scores_map[chunk_id] = float(score)
        bm25_doc_map[chunk_id] = {
            "content": record["content"],
            "file_id": record["file_id"],
            "source_file": record["source_file"],
            "page": record["page"],
        }

    logger.info(f"BM25 检索完成: {len(bm25_scores_map)} 条得分")
    return bm25_scores_map, bm25_doc_map


def _hybrid_retrieve(query: str, file_ids: list) -> list:
    """
    真正的混合检索：
    1. 向量检索召回候选
    2. BM25 检索召回候选
    3. 取并集后统一计算 hybrid_score
    4. rerank 后返回 top chunks
    """
    model = _get_embed_model()
    query_embedding = model.encode(query).tolist()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        vector_future = executor.submit(_vector_search, query, query_embedding, file_ids)
        bm25_future = executor.submit(_bm25_search, query, file_ids)

        vector_chunks = vector_future.result()
        bm25_scores_map, bm25_doc_map = bm25_future.result()

    weight_vector, weight_bm25 = get_adaptive_weights(query)
    candidate_map = {}

    for vc in vector_chunks:
        chunk_id = vc["chunk_id"]
        candidate_map[chunk_id] = {
            "chunk_id": chunk_id,
            "content": vc.get("content", ""),
            "source_file": vc.get("source_file", ""),
            "page": vc.get("page", 0),
            "distance": vc.get("distance", 0),
            "vector_score": float(vc.get("vector_score", 0.0)),
            "bm25_score": float(bm25_scores_map.get(chunk_id, 0.0)),
        }

    bm25_ranked = sorted(
        bm25_scores_map.items(),
        key=lambda x: x[1],
        reverse=True
    )[: settings.top_k * 3]

    for chunk_id, bm25_score in bm25_ranked:
        if chunk_id in candidate_map:
            continue
        doc_info = bm25_doc_map.get(chunk_id, {})
        candidate_map[chunk_id] = {
            "chunk_id": chunk_id,
            "content": doc_info.get("content", ""),
            "source_file": doc_info.get("source_file", ""),
            "page": doc_info.get("page", 0),
            "distance": None,
            "vector_score": 0.0,
            "bm25_score": float(bm25_score),
        }

    candidates = list(candidate_map.values())
    if not candidates:
        return []

    vector_scores = [c["vector_score"] for c in candidates]
    bm25_scores = [c["bm25_score"] for c in candidates]

    vector_norm = _normalize_scores(vector_scores)
    bm25_norm = _normalize_scores(bm25_scores)

    for i, c in enumerate(candidates):
        c["vector_score_norm"] = vector_norm[i]
        c["bm25_score_norm"] = bm25_norm[i]
        c["hybrid_score"] = (
            c["vector_score_norm"] * weight_vector +
            c["bm25_score_norm"] * weight_bm25
        )

    candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)

    # 去重：优先按 chunk_id；若 chunk_id 不同但 content 一样，也只保留分高的
    deduped = []
    seen_contents = set()
    for c in candidates:
        content_key = (c.get("content") or "").strip()
        if content_key and content_key in seen_contents:
            continue
        if content_key:
            seen_contents.add(content_key)
        deduped.append(c)

    top_chunks = deduped[: settings.top_k * 2]
    top_chunks = rerank_chunks(query, top_chunks, top_k=settings.top_k)

    logger.info(
        f"混合检索完成: vector={len(vector_chunks)}, bm25={len(bm25_scores_map)}, "
        f"merged={len(candidates)}, deduped={len(deduped)}, top={len(top_chunks)}"
    )
    return top_chunks


def retrieve_and_answer(query: str, file_ids: list, scenario: str = "default") -> dict:
    """
    混合检索（向量+BM25）→ 重排序 → 冲突检测 → 融合 → 调LLM生成答案
    """
    logger.info(f"收到问答请求: query={query}, file_ids={file_ids}")

    from modules.cache.redis_client import get_cached_result, set_cached_result

    cache_key_raw = f"{query}|{sorted(file_ids)}|{scenario}"
    query_hash = hashlib.md5(cache_key_raw.encode()).hexdigest()

    cached = get_cached_result(query_hash)
    if cached:
        logger.info("返回缓存结果，跳过检索")
        return cached

    try:
        start_time = time.time()
        top_chunks = _hybrid_retrieve(query, file_ids)
        elapsed = time.time() - start_time
        logger.info(f"检索完成，耗时: {elapsed:.2f}s, top_chunks={len(top_chunks)}")

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
            return result

        conflicts = detect_conflicts(top_chunks)
        if conflicts:
            logger.info(f"检测到 {len(conflicts)} 处冲突")
            for cf in conflicts:
                logger.info(f"  冲突字段: {cf['key']}, 出现值: {cf['values']}")

        prompt = _build_prompt(query, top_chunks, scenario=scenario)

        llm_client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url
        )

        response = llm_client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )

        answer = (response.choices[0].message.content or "").strip()

        avg_score = float(np.mean([c["hybrid_score"] for c in top_chunks])) if top_chunks else 0.0
        confidence = round(min(avg_score * 1.2, 1.0), 2) if top_chunks else -1

        top_chunks, fusion_info = fuse_results(top_chunks, conflicts)

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
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
            "fusion": fusion_info
        }

        logger.info(f"问答完成: confidence={result['confidence']}, has_conflicts={fusion_info['has_conflicts']}")
        set_cached_result(query_hash, result)
        return result

    except Exception as e:
        logger.exception(f"问答处理异常: {e}")
        from tests.mock_data import MOCK_ANSWER_RESULT
        mock = copy.deepcopy(MOCK_ANSWER_RESULT)
        mock["query"] = query
        mock["answer"] = f"抱歉，处理您的问题时遇到问题: {str(e)}"
        mock["confidence"] = -1
        mock["fusion"] = {"has_conflicts": False, "conflict_count": 0, "conflict_details": []}
        return mock