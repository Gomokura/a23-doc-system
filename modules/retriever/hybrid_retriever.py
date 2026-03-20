"""
混合检索与问答模块 - 负责人: 成员3
函数签名已锁定，不得更改
"""
import concurrent.futures
import time
from typing import Optional, Callable, Tuple, Dict, List

import jieba
import numpy as np
from loguru import logger
from openai import OpenAI
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from config import settings
from modules.retriever.indexer import get_bm25_data, get_collection, _get_embed_model

# ═══════════════════════════════════════════════════════════════════════
# ReRanker 配置
# ═══════════════════════════════════════════════════════════════════════
# CrossEncoder 模型：英文通用 / 中文通用
# 可选中文模型：cross-encoder/chinese-roberta-base
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # 轻量快速
RERANKER_TOP_K = 5  # ReRanker 保留结果数

# ═══════════════════════════════════════════════════════════════════════
# 中文分词配置
# ═══════════════════════════════════════════════════════════════════════
# 常用停用词（标点、无意义词）
STOPWORDS = set([
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
    '自己', '这', '那', '里', '为', '什么', '可以', '这个', '那个', '但是', '还是',
    '如果', '因为', '所以', '但是', '而', '与', '及', '或', '等', '于', '从', '以',
    '及', '其', '被', '由', '对', '将', '把', '向', '给', '用', '通过', '进行',
    '。', '，', '！', '？', '、', '"', '"', ''', ''', '：', '；', '（', '）',
    '【', '】', '[', ']', '{', '}', '/', '\\', '-', '_', '+', '=', '*', '#',
    '@', '$', '%', '^', '&', '~', '`', '<', '>', '|', '\n', '\t', ' ', '  ',
])

def tokenize_chinese(text: str, remove_stopwords: bool = True) -> list:
    """
    中文分词（使用 jieba）

    Args:
        text: 待分词文本
        remove_stopwords: 是否去除停用词

    Returns:
        分词结果列表
    """
    if not text:
        return []

    # jieba 精确模式分词
    tokens = list(jieba.cut(text, cut_all=False))

    # 去除停用词和空字符
    if remove_stopwords:
        tokens = [t.strip() for t in tokens if t.strip() and t not in STOPWORDS]
    else:
        tokens = [t.strip() for t in tokens if t.strip()]

    return tokens


# ═══════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════


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
# 查询分词阈值：超过此数量认为是"长查询"
QUERY_TOKEN_THRESHOLD = 5

# 短查询权重（关键词、术语类）
WEIGHT_VECTOR_SHORT = 0.4
WEIGHT_BM25_SHORT = 0.6

# 长查询权重（语义理解类）
WEIGHT_VECTOR_LONG = 0.7
WEIGHT_BM25_LONG = 0.3


def get_adaptive_weights(query: str) -> Tuple[float, float]:
    """
    根据查询特征自适应调整向量检索和 BM25 权重

    策略：
    - 短查询（≤5个词）：偏向 BM25，关键词匹配更准确
    - 长查询（>5个词）：偏向向量，语义理解更重要

    Args:
        query: 用户查询文本

    Returns:
        (weight_vector, weight_bm25): 向量权重和 BM25 权重
    """
    # 对查询进行分词（不去除停用词，保持完整性）
    tokens = tokenize_chinese(query, remove_stopwords=False)
    token_count = len(tokens)

    if token_count > QUERY_TOKEN_THRESHOLD:
        # 长查询：偏向语义理解
        weight_vector = WEIGHT_VECTOR_LONG
        weight_bm25 = WEIGHT_BM25_LONG
        logger.info(f"自适应权重 [长查询 {token_count} 词]: vector={weight_vector}, bm25={weight_bm25}")
    else:
        # 短查询：偏向关键词匹配
        weight_vector = WEIGHT_VECTOR_SHORT
        weight_bm25 = WEIGHT_BM25_SHORT
        logger.info(f"自适应权重 [短查询 {token_count} 词]: vector={weight_vector}, bm25={weight_bm25}")

    return weight_vector, weight_bm25


# ═══════════════════════════════════════════════════════════════════════
# CrossEncoder ReRanker
# ═══════════════════════════════════════════════════════════════════════
_reranker_model: Optional[CrossEncoder] = None


def _get_reranker() -> CrossEncoder:
    """获取或初始化 ReRanker 模型（单例模式）"""
    global _reranker_model
    if _reranker_model is None:
        model_name = settings.reranker_model or RERANKER_MODEL
        logger.info(f"加载 ReRanker 模型: {model_name}")
        _reranker_model = CrossEncoder(model_name)
    return _reranker_model


def rerank_chunks(query: str, chunks: list, top_k: int = None) -> list:
    """
    使用 CrossEncoder 对检索结果进行二次重排序

    CrossEncoder 会同时编码 (query, document) 对，计算更精确的相关性分数。

    Args:
        query: 用户查询
        chunks: 混合检索返回的 chunks 列表
        top_k: 保留的重排序结果数量，默认使用配置

    Returns:
        重排序后的 chunks 列表（按相关性降序）
    """
    if not chunks:
        return []

    top_k = top_k or settings.reranker_top_k

    # 如果未启用 ReRanker，直接返回
    if not settings.reranker_enabled:
        logger.debug("ReRanker 未启用，返回原始排序")
        return chunks[:top_k]

    # 如果结果数量少于 top_k，直接返回
    if len(chunks) <= top_k:
        return chunks

    try:
        reranker = _get_reranker()

        # 准备 (query, document) 对
        pairs = [(query, chunk.get("content", "")) for chunk in chunks]

        # 批量计算相关性分数
        scores = reranker.predict(pairs)

        # 将分数添加到 chunks
        for i, chunk in enumerate(chunks):
            chunk["rerank_score"] = float(scores[i])

        # 按 rerank_score 降序排序
        reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)

        logger.info(f"ReRanker 完成: {len(chunks)} → {top_k} 条，得分范围 [{min(scores):.3f}, {max(scores):.3f}]")

        return reranked[:top_k]

    except Exception as e:
        logger.warning(f"ReRanker 失败: {e}，返回原始排序")
        return chunks


def _build_prompt(query: str, chunks: list, scenario: str = "default") -> str:
    """构建 LLM 问答 Prompt（支持场景化扩展）"""
    context = "\n\n".join([
        f"[文档{i+1}]\n{c['content']}"
        for i, c in enumerate(chunks)
    ])

    # 场景化扩展要求
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
    """
    检测多个 chunk 之间的内容冲突

    Args:
        chunks: 检索结果列表（已按 hybrid_score 排序）

    Returns:
        conflicts: 冲突列表，每项包含 {key, values, from_chunks}
    """
    conflicts = []

    # 定义需要检测的常见关键字段模式
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
                        if val not in value_to_chunks:
                            value_to_chunks[val] = []
                        value_to_chunks[val].append(chunk.get("chunk_id", ""))

        # 同一 key 出现多个不同值 → 冲突
        if len(value_to_chunks) > 1:
            conflicts.append({
                "key": key_name,
                "values": list(value_to_chunks.keys()),
                "from_chunks": list(value_to_chunks.values())
            })

    return conflicts


def fuse_results(top_chunks: list, conflicts: list) -> tuple:
    """
    多源冲突融合：将冲突信息整合到结果中

    Returns:
        (fused_chunks, fusion_info)
    """
    fusion_info = {
        "has_conflicts": len(conflicts) > 0,
        "conflict_count": len(conflicts),
        "conflict_details": conflicts
    }

    # 如果没有冲突，直接返回原结果
    if not conflicts:
        return top_chunks, fusion_info

    # 标记每个 chunk 是否有冲突
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


# ═══════════════════════════════════════════════════════════════════════
# 距离转换函数
# ═══════════════════════════════════════════════════════════════════════
def distance_to_score(distance: float, method: str = "exp") -> float:
    """
    将向量距离转换为相似度分数

    Args:
        distance: 向量距离（ChromaDB 返回的）
        method: 转换方法
            - "exp": exp(-distance)，指数衰减，效果更好
            - "linear": 1 / (1 + distance)，线性衰减

    Returns:
        相似度分数，范围 [0, 1]，越大越好
    """
    if distance is None or distance < 0:
        return 0.0

    if method == "exp":
        # 指数衰减：距离越大，分数下降越快，符合向量相似度直觉
        # exp(0) = 1, exp(-1) ≈ 0.37, exp(-2) ≈ 0.14
        return np.exp(-distance)
    else:
        # 线性衰减：1 / (1 + distance)
        return 1.0 / (1.0 + distance)


# ═══════════════════════════════════════════════════════════════════════
# 并行检索模块
# ═══════════════════════════════════════════════════════════════════════
def _vector_search(query: str, query_embedding: list, file_ids: list) -> list:
    """
    向量检索（独立函数，供并行调用）

    Args:
        query: 原始查询
        query_embedding: 查询向量
        file_ids: 文件过滤列表

    Returns:
        vector_chunks: 向量检索结果列表
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
            vector_chunks.append({
                "chunk_id": chunk_id,
                "content": documents[i] if i < len(documents) else "",
                "source_file": metadatas[i].get("source_file", "") if i < len(metadatas) else "",
                "page": metadatas[i].get("page", 0) if i < len(metadatas) else 0,
                "distance": distances[i] if i < len(distances) else 0,
                "vector_score": distance_to_score(distances[i]) if i < len(distances) else 0
            })

    logger.info(f"向量检索完成: 获取 {len(vector_chunks)} 条结果")
    return vector_chunks


def _bm25_search(query: str) -> Tuple[dict, dict]:
    """
    BM25 检索（独立函数，供并行调用）

    Args:
        query: 原始查询

    Returns:
        (bm25_scores_map, bm25_doc_map): BM25得分和文档映射
    """
    bm25_corpus, bm25_doc_map = get_bm25_data()
    bm25_scores_map = {}

    if bm25_corpus:
        # 使用 jieba 中文分词构建 BM25
        tokenized_corpus = [tokenize_chinese(doc, remove_stopwords=True) for doc in bm25_corpus]
        bm25 = BM25Okapi(tokenized_corpus)

        # 查询分词
        tokenized_query = tokenize_chinese(query, remove_stopwords=True)
        logger.info(f"BM25 分词结果: query='{query}' -> {tokenized_query}")

        raw_scores = bm25.get_scores(tokenized_query)

        # 映射到 chunk_id
        for idx, score in enumerate(raw_scores):
            if idx < len(bm25_corpus):
                content = bm25_corpus[idx]
                for cid, info in bm25_doc_map.items():
                    if info.get("content") == content:
                        bm25_scores_map[cid] = score
                        break

    logger.info(f"BM25 检索完成: {len(bm25_scores_map)} 条得分")
    return bm25_scores_map, bm25_doc_map


def retrieve_and_answer(query: str, file_ids: list, scenario: str = "default") -> dict:
    """
    混合检索（向量+BM25）→ 重排序 → 冲突检测 → 融合 → 调LLM生成答案

    Args:
        query:    用户问题
        file_ids: 限定检索的文件列表，空列表表示检索所有
        scenario: 场景类型，可选 "default" | "contract" | "report" | "regulation"

    Returns:
        AnswerResult dict（规范文档 4.3）
    """
    logger.info(f"收到问答请求: query={query}, file_ids={file_ids}")

    try:
        # ═══════════════════════════════════════════════════════════════
        # 并行检索：向量检索 + BM25 同步执行，节省 40-50% 时间
        # ═══════════════════════════════════════════════════════════════
        start_time = time.time()

        # 1. 获取模型并生成查询向量
        model = _get_embed_model()
        query_embedding = model.encode(query).tolist()

        # 2. 并行执行向量检索和 BM25 检索
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            vector_future = executor.submit(_vector_search, query, query_embedding, file_ids)
            bm25_future = executor.submit(_bm25_search, query)
            vector_chunks = vector_future.result()
            bm25_scores_map, bm25_doc_map = bm25_future.result()

        elapsed = time.time() - start_time
        logger.info(f"并行检索完成，耗时: {elapsed:.2f}s")

        # ═══════════════════════════════════════════════════════════════
        # 第3步：混合得分排序，取 TOP_K
        # ═══════════════════════════════════════════════════════════════
        # 获取自适应权重
        weight_vector, weight_bm25 = get_adaptive_weights(query)

        scored_chunks = []
        seen_contents = set()

        for vc in vector_chunks:
            chunk_id = vc["chunk_id"]
            content = vc["content"]

            if content in seen_contents:
                continue
            seen_contents.add(content)

            vector_score = vc.get("vector_score", 0)
            bm25_score = bm25_scores_map.get(chunk_id, 0)

            # BM25 归一化（如果存在非零得分）
            if bm25_scores_map:
                max_bm25 = max(bm25_scores_map.values()) or 1
                bm25_score_norm = bm25_score / max_bm25
            else:
                bm25_score_norm = 0

            # 混合得分 = 向量 × 权重 + BM25 × 权重（自适应）
            hybrid_score = vector_score * weight_vector + bm25_score_norm * weight_bm25

            # 补充 BM25 信息
            doc_info = bm25_doc_map.get(chunk_id, {})
            vc["content"] = doc_info.get("content", vc["content"])
            vc["source_file"] = doc_info.get("source_file", vc.get("source_file", ""))
            vc["page"] = doc_info.get("page", vc.get("page", 0))
            vc["bm25_score"] = bm25_score
            vc["hybrid_score"] = hybrid_score

            scored_chunks.append(vc)

        # 按混合得分排序
        scored_chunks.sort(key=lambda x: x["hybrid_score"], reverse=True)
        top_chunks = scored_chunks[:settings.top_k]

        logger.info(f"混合排序完成: TOP {len(top_chunks)}")

        # ═══════════════════════════════════════════════════════════════
        # 第4步：CrossEncoder ReRanker 二次重排序
        # ═══════════════════════════════════════════════════════════════
        top_chunks = rerank_chunks(query, top_chunks)
        logger.info(f"ReRanker 重排序完成: {len(top_chunks)} 条")

        # ═══════════════════════════════════════════════════════════════
        # 第5步：多源冲突检测与融合
        # ═══════════════════════════════════════════════════════════════
        conflicts = detect_conflicts(top_chunks)
        if conflicts:
            logger.info(f"检测到 {len(conflicts)} 处冲突")
            for cf in conflicts:
                logger.info(f"  冲突字段: {cf['key']}, 出现值: {cf['values']}")

        # ═══════════════════════════════════════════════════════════════
        # 第6步：调用 LLM 生成答案
        # ═══════════════════════════════════════════════════════════════
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

        answer = response.choices[0].message.content

        # 计算置信度（基于混合得分）
        if top_chunks:
            avg_score = np.mean([c["hybrid_score"] for c in top_chunks])
            confidence = min(avg_score * 1.2, 1.0)
        else:
            confidence = -1

        # ═══════════════════════════════════════════════════════════════
        # 第7步：构造返回结果
        # ═══════════════════════════════════════════════════════════════
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
            "confidence": round(confidence, 2),
            "fusion": fusion_info  # 冲突融合信息
        }

        logger.info(f"问答完成: confidence={result['confidence']}, has_conflicts={fusion_info['has_conflicts']}")
        return result

    except Exception as e:
        logger.error(f"问答处理异常: {e}")
        # 出错时返回友好的错误结果
        from tests.mock_data import MOCK_ANSWER_RESULT
        import copy
        mock = copy.deepcopy(MOCK_ANSWER_RESULT)
        mock["query"] = query
        mock["answer"] = f"抱歉，处理您的问题时遇到问题: {str(e)}"
        mock["confidence"] = -1
        mock["fusion"] = {"has_conflicts": False, "conflict_count": 0, "conflict_details": []}
        return mock
