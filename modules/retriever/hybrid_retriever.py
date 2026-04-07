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
import bm25s
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
def get_adaptive_weights(query: str) -> Tuple[float, float]:
    tokens = tokenize_chinese(query, remove_stopwords=False)
    token_count = len(tokens)

    threshold = getattr(settings, "query_token_threshold", 5)
    wv_short = getattr(settings, "weight_vector_short", 0.4)
    wb_short = getattr(settings, "weight_bm25_short", 0.6)
    wv_long = getattr(settings, "weight_vector_long", 0.7)
    wb_long = getattr(settings, "weight_bm25_long", 0.3)

    if token_count > threshold:
        weight_vector = wv_long
        weight_bm25 = wb_long
        logger.info(f"自适应权重 [长查询 {token_count} 词]: vector={weight_vector}, bm25={weight_bm25}")
    else:
        weight_vector = wv_short
        weight_bm25 = wb_short
        logger.info(f"自适应权重 [短查询 {token_count} 词]: vector={weight_vector}, bm25={weight_bm25}")

    return weight_vector, weight_bm25


# ═══════════════════════════════════════════════════════════════════════
# CrossEncoder ReRanker
# ═══════════════════════════════════════════════════════════════════════
_reranker_model: Optional[CrossEncoder] = None


def _get_reranker() -> CrossEncoder:
    global _reranker_model
    if _reranker_model is None:
        model_name = getattr(settings, "reranker_model", None) or "Qwen/Qwen3-Reranker-0.6B"
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
    CHUNK_MAX_CHARS = 3000
    CONTEXT_MAX_CHARS = 8000

    parts = []
    total = 0
    seen_files = []

    for i, c in enumerate(chunks):
        content = (c.get("content") or "").strip()
        if not content:
            continue
        if len(content) > CHUNK_MAX_CHARS:
            content = content[:CHUNK_MAX_CHARS] + "…"

        # 用真实文件名作标签，而不是 [文档N]
        source_file = c.get("source_file", "")
        filename = c.get("filename") or source_file.replace("\\", "/").split("/")[-1] or f"文档{i+1}"
        if filename not in seen_files:
            seen_files.append(filename)

        seg = f"【{filename}】\n{content}"
        if total + len(seg) + 2 > CONTEXT_MAX_CHARS:
            break
        parts.append(seg)
        total += len(seg) + 2

    context = "\n\n".join(parts)
    # 来源列表用真实文件名
    source_names = "、".join(f"【{fn}】" for fn in seen_files) if seen_files else "未知文件"

    if scenario == "extract":
        return f"""你是一个文档字段提取助手。请从以下文档内容中提取指定字段的值。

## 文档内容
{context}

## 提取任务
{query}

## 严格要求
1. 只输出提取到的具体值，不要任何解释、前缀或来源说明
2. 如果文档中确实没有该字段的值，只输出：(无)
3. 不要输出"回答:"、"值:"、"来源:"等前缀
4. 不要编造，只从文档中提取

直接输出值："""

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
4. 【聚合/统计类问题】如果用户问"有哪些"、"有几个"、"列出所有"等，请归纳去重后汇总作答
{extra_requirement}

## 回答格式
回答: <你的回答>
来源: {source_names}"""


def detect_conflicts(chunks: list) -> list:
    """
    从检索到的片段中扫描是否出现「同一语义字段多个不同取值」。
    注意：名单/表格类文档里多行日期、学号、序号会被旧版宽松正则误判为冲突，
    进而让前端显示「多源冲突」、拉低用户对答案的信任；此处已收紧规则。
    """
    import re

    conflicts = []
    # 金额：必须有货币单位，避免把学号、序号、年份等纯数字当成「多个金额」
    key_patterns = [
        ("金额", [
            r"(\d+(?:\.\d+)?\s*万元)",
            r"(\d+(?:\.\d+)?\s*元)",
            r"(¥\s*\d+(?:\.\d+)?)",
            r"(人民币\s*\d+(?:\.\d+)?\s*元?)",
        ]),
        ("日期", [
            r"(\d{4}年\d{1,2}月\d{1,2}日)",
            r"(\d{4}-\d{2}-\d{2})",
        ]),
        ("比例", [r"(\d+\.?\d*%)", r"(\d+)\s*%"]),
        ("公司名", [r"([^\s]{4,}公司)", r"([^\s]{2,}贸易)", r"([^\s]{2,}科技)"]),
    ]

    for key_name, patterns in key_patterns:
        value_to_chunks = {}

        for chunk in chunks:
            content = chunk.get("content", "")
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    val = match.strip()
                    if val and len(val) > 1:
                        value_to_chunks.setdefault(val, []).append(chunk.get("chunk_id", ""))

        distinct = len(value_to_chunks)
        if distinct <= 1:
            continue
        # 表格里常见「每行一个日期」，多种日期并不等于信息矛盾
        if key_name == "日期" and distinct > 4:
            continue

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


def mmr_diversity_rerank(query: str, chunks: list, lambda_val: float = None) -> list:
    """
    MMR (Maximal Marginal Relevance) Diversity 重排序。
    位于 CrossEncoder 重排序之后，在相关性和多样性之间取平衡。

    公式: MMR = λ·Sim(query, doc) − (1−λ)·max_Sim(doc, already_selected)
    论文: Carbonell & Goldstein, SIGIR 1998

    Args:
        query: 用户查询
        chunks: 已按 rerank_score 降序排列的 chunk 列表
        lambda_val: 平衡系数，1=只看相关性，0=只看多样性，默认从配置读取
    Returns:
        经 MMR 筛选后的 chunk 列表（顺序已更新）
    """
    if not chunks or len(chunks) <= 2:
        return chunks

    lambda_val = lambda_val or getattr(settings, "mmr_lambda", 0.7)
    if not getattr(settings, "mmr_enabled", False):
        return chunks

    try:
        embed_model = _get_embed_model()
        contents = [c.get("content", "") for c in chunks]
        chunk_embeds = embed_model.encode(contents, normalize_embeddings=True)

        relevance_scores = np.array([c.get("rerank_score", 0.0) for c in chunks])
        if relevance_scores.max() != relevance_scores.min():
            relevance_scores = (relevance_scores - relevance_scores.min()) / (
                relevance_scores.max() - relevance_scores.min()
            )
        else:
            relevance_scores = np.ones_like(relevance_scores) * 0.5

        selected: list = []
        remaining = list(range(len(chunks)))

        while remaining and len(selected) < len(chunks):
            best_score = -float("inf")
            best_idx = None

            for idx in remaining:
                sim_to_query = float(relevance_scores[idx])

                max_sim_to_selected = 0.0
                if selected:
                    selected_embeds = chunk_embeds[selected]
                    similarities = np.dot(chunk_embeds[idx], selected_embeds.T)
                    max_sim_to_selected = float(np.max(similarities))

                mmr_score = (
                    lambda_val * sim_to_query
                    - (1 - lambda_val) * max_sim_to_selected
                )

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx

            if best_idx is not None:
                selected.append(best_idx)
                remaining.remove(best_idx)

        result = [chunks[i] for i in selected]
        logger.info(
            f"MMR Diversity 完成 (λ={lambda_val:.2f}): "
            f"{len(chunks)} → {len(result)} 条，移除了 {len(chunks)-len(result)} 个冗余 chunk"
        )
        return result

    except Exception as e:
        logger.warning(f"MMR Diversity 失败: {e}，返回原始排序")
        return chunks


def _load_file_as_chunks(file_paths: list, file_name_map: dict = None) -> list:
    """
    直接读取源文件，把内容合并成少量 chunk 传给 LLM。
    Excel/CSV：按分类列去重后，所有行合并为 1~2 个大 chunk（CSV 格式），不拆分成每行一个 chunk。
    其他文件：按段落切分，限制数量。
    file_name_map: {磁盘路径: 真实文件名}，优先用真实文件名展示
    """
    chunks = []
    max_chunks = getattr(settings, "top_k", 10)  # 总 chunk 数不超过 TOP_K

    for fp in file_paths:
        # 优先使用数据库中的真实文件名，避免显示 UUID 磁盘名
        disk_name = fp.replace("\\", "/").split("/")[-1]
        filename = (file_name_map or {}).get(fp, disk_name)
        ext = fp.rsplit(".", 1)[-1].lower()
        try:
            if ext in ("xlsx", "xls"):
                import pandas as pd
                df = pd.read_excel(fp)
            elif ext == "csv":
                import pandas as pd
                df = pd.read_csv(fp)
            else:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                for i, para in enumerate(text.split("\n\n")):
                    para = para.strip()
                    if para and len(chunks) < max_chunks:
                        chunks.append({"chunk_id": f"file_{i}", "content": para,
                                       "source_file": fp, "page": i,
                                       "hybrid_score": 1.0, "filename": filename})
                continue

            if df.empty:
                continue

            # 找分类列去重
            dedup_col = None
            for col in df.columns:
                nunique = df[col].nunique()
                if 1 < nunique < min(200, len(df) * 0.3):
                    dedup_col = col
                    break

            sample_df = (df.drop_duplicates(subset=[dedup_col])
                         if dedup_col else df.sample(n=min(50, len(df)), random_state=42))

            # 把所有行合并成 CSV 格式的单个 chunk，而不是每行一个 chunk
            # 这样 LLM 看到的是完整的表格，来源只有 1 个文件
            csv_text = sample_df.to_csv(index=False)
            # 若内容太长则切成 2 个 chunk
            chunk_size = 3000
            for ci, start in enumerate(range(0, len(csv_text), chunk_size)):
                piece = csv_text[start:start + chunk_size]
                chunks.append({
                    "chunk_id": f"{filename}_{ci}",
                    "content": piece,
                    "source_file": fp,
                    "page": ci,
                    "hybrid_score": 1.0,
                    "filename": filename,
                })
                if len(chunks) >= max_chunks:
                    break

            logger.info(f"直接读取文件 {filename}：{len(sample_df)} 行，生成 chunk 数: {len(chunks)}")
        except Exception as e:
            logger.warning(f"直接读取文件 {fp} 失败: {e}")

    return chunks


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
# BM25S 运行时缓存
# ═══════════════════════════════════════════════════════════════════════
_BM25_CACHE_VALID = False
_BM25_INDEX: Optional[bm25s.BM25] = None
_BM25_CACHE_KEY = None
_BM25_RECORDS: list = []
_BM25_CORPUS: list = []  # BM25S 需要原始文本供 retrieve() 使用
_BM25S_INDEX_PATH = "./db/bm25s_index"


def invalidate_bm25_runtime_cache():
    global _BM25_CACHE_VALID, _BM25_INDEX, _BM25_CACHE_KEY, _BM25_RECORDS, _BM25_CORPUS
    _BM25_CACHE_VALID = False
    _BM25_INDEX = None
    _BM25_CACHE_KEY = None
    _BM25_RECORDS = []
    _BM25_CORPUS = []
    logger.info("BM25S 运行时缓存已失效")


def _ensure_bm25_ready(file_ids: list = None):
    global _BM25_INDEX, _BM25_CORPUS, _BM25_CACHE_VALID, _BM25_CACHE_KEY, _BM25_RECORDS

    cache_key = tuple(sorted(file_ids)) if file_ids else "__all__"

    if _BM25_CACHE_VALID and _BM25_INDEX is not None and _BM25_CACHE_KEY == cache_key:
        return

    records = get_bm25_records(file_ids)
    _BM25_RECORDS = records

    if not records:
        _BM25_INDEX = None
        _BM25_CORPUS = []
        _BM25_CACHE_VALID = True
        _BM25_CACHE_KEY = cache_key
        return

    corpus = [r["content"] for r in records]
    _BM25_CORPUS = corpus

    # 尝试从持久化文件加载（文件名含记录数，记录数变化时自动失效）
    method = getattr(settings, "bm25s_method", "robertson")
    index_file = f"{_BM25S_INDEX_PATH}_{cache_key}_n{len(records)}.pt"
    corpus_file = f"{_BM25S_INDEX_PATH}_{cache_key}_corpus.json"

    import os, glob
    if os.path.exists(index_file):
        try:
            _BM25_INDEX = bm25s.BM25.load(index_file, load_corpus=True)
            _BM25_CACHE_VALID = True
            _BM25_CACHE_KEY = cache_key
            logger.info(f"BM25S 从持久化加载: {len(records)} 条")
            return
        except Exception as e:
            logger.warning(f"BM25S 持久化加载失败，重新构建: {e}")

    # 构建索引
    corpus_tokens = bm25s.tokenize(corpus, stopwords=None)
    _BM25_INDEX = bm25s.BM25(method=method)
    _BM25_INDEX.index(corpus_tokens)

    # 持久化保存（先删同 cache_key 的旧文件）
    try:
        for old in glob.glob(f"{_BM25S_INDEX_PATH}_{cache_key}_n*.pt"):
            try:
                os.remove(old)
            except Exception:
                pass
        os.makedirs(os.path.dirname(index_file) or ".", exist_ok=True)
        _BM25_INDEX.save(index_file)
        logger.info(f"BM25S 持久化已保存: {index_file}")
    except Exception as e:
        logger.warning(f"BM25S 持久化失败: {e}")

    _BM25_CACHE_VALID = True
    _BM25_CACHE_KEY = cache_key
    logger.info(f"BM25S 索引构建完成: {len(records)} 条, method={method}")


def _bm25_search(query: str, file_ids: list = None) -> Tuple[dict, dict]:
    """
    BM25S 检索（独立函数，供并行调用）
    支持 file_ids 过滤，并直接返回 chunk_id -> score 映射
    """
    _ensure_bm25_ready(file_ids)

    bm25_scores_map = {}
    bm25_doc_map = {}

    if not _BM25_RECORDS or _BM25_INDEX is None:
        return bm25_scores_map, bm25_doc_map

    # BM25S 内置分词，同时支持中文 jieba
    query_tokens = list(jieba.cut(query))
    query_tokens = [t.strip() for t in query_tokens if t.strip()]
    logger.info(f"BM25S 分词结果: query='{query}' -> {query_tokens}")

    # retrieve 返回 namedtuple(result.documents, result.scores)，k=None 取全部
    # BM25S.load(load_corpus=True) 会把 corpus 存入对象内部，corpus=None 则自动用内部的
    result = _BM25_INDEX.retrieve(
        [query_tokens],
        corpus=None,
        k=len(_BM25_CORPUS),
        return_as="tuple",
    )
    doc_ids = result.documents[0] if len(result.documents) else []
    scores = result.scores[0] if len(result.scores) else []

    for idx, score in zip(doc_ids, scores):
        idx_int = int(idx)
        if idx_int < len(_BM25_RECORDS):
            record = _BM25_RECORDS[idx_int]
            chunk_id = record["chunk_id"]
            bm25_scores_map[chunk_id] = float(score)
            bm25_doc_map[chunk_id] = {
                "content": record["content"],
                "file_id": record["file_id"],
                "source_file": record["source_file"],
                "page": record["page"],
            }

    logger.info(f"BM25S 检索完成: {len(bm25_scores_map)} 条得分")
    return bm25_scores_map, bm25_doc_map


def reciprocal_rank_fusion(results_list: list, k: int = 60) -> dict:
    """
    Reciprocal Rank Fusion (RRF) — Google 提出的无参检索融合方法。
    不依赖得分绝对值，只依赖排名顺序，对各路检索结果一视同仁。
    公式: RRF(d) = Σ 1/(k + rank(d))

    Args:
        results_list: 各路检索的已排序结果列表（每个元素是 dict，需有 chunk_id）
        k: RRF 超参数，默认 60。值越大，各路结果的权重越趋于均等。
    Returns:
        chunk_id -> rrf_score 的映射，按分降序排列
    """
    scores: dict = {}

    for results in results_list:
        if not results:
            continue
        for rank, item in enumerate(results):
            chunk_id = item.get("chunk_id")
            if chunk_id:
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)

    sorted_chunk_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_chunk_ids)


def _hybrid_retrieve(query: str, file_ids: list, file_paths: list = None, file_name_map: dict = None) -> list:
    """
    混合检索：
    - 若提供 file_paths 且文件为结构化表格（Excel/CSV），直接读文件取多样性样本，跳过向量检索
    - 否则走向量+BM25混合检索
    """
    # 判断是否有结构化文件可直接读取
    structured_exts = {"xlsx", "xls", "csv"}
    if file_paths:
        structured = [fp for fp in file_paths if fp.rsplit(".", 1)[-1].lower() in structured_exts]
        if structured:
            logger.info(f"检测到结构化文件，直接读取跳过向量检索: {structured}")
            direct_chunks = _load_file_as_chunks(structured, file_name_map=file_name_map)
            # 非结构化文件仍走向量检索
            other = [fp for fp in file_paths if fp not in structured]
            if other:
                pass  # 暂不处理混合情况
            if direct_chunks:
                return direct_chunks
    model = _get_embed_model()
    query_embedding = model.encode(query).tolist()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        vector_future = executor.submit(_vector_search, query, query_embedding, file_ids)
        bm25_future = executor.submit(_bm25_search, query, file_ids)

        vector_chunks = vector_future.result()
        bm25_scores_map, bm25_doc_map = bm25_future.result()

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

    fusion_method = getattr(settings, "fusion_method", "rrf")

    if fusion_method == "rrf":
        rrf_k = getattr(settings, "rrf_k", 60)

        vector_ranked = sorted(
            [c for c in candidates if c.get("vector_score", 0) > 0 or c.get("distance") is not None],
            key=lambda x: x.get("vector_score", 0),
            reverse=True
        )
        bm25_ranked = sorted(
            [c for c in candidates if c.get("bm25_score", 0) > 0],
            key=lambda x: x.get("bm25_score", 0),
            reverse=True
        )

        rrf_scores = reciprocal_rank_fusion([vector_ranked, bm25_ranked], k=rrf_k)

        for c in candidates:
            c["hybrid_score"] = float(rrf_scores.get(c["chunk_id"], 0.0))

        candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)
        logger.info(f"RRF 融合完成 (k={rrf_k}), vector_rank={len(vector_ranked)}, bm25_rank={len(bm25_ranked)}")
    else:
        weight_vector, weight_bm25 = get_adaptive_weights(query)

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
    top_chunks = mmr_diversity_rerank(query, top_chunks)

    # 向量/BM25 路径：用 file_name_map 把 UUID basename 替换成真实文件名
    if file_name_map:
        for c in top_chunks:
            if not c.get("filename"):
                src = c.get("source_file", "")
                # source_file 可能是 basename 或完整路径，两种都查
                real = file_name_map.get(src) or file_name_map.get(src.replace("\\", "/").split("/")[-1])
                if real:
                    c["filename"] = real

    logger.info(
        f"混合检索完成: vector={len(vector_chunks)}, bm25={len(bm25_scores_map)}, "
        f"merged={len(candidates)}, deduped={len(deduped)}, top={len(top_chunks)}"
    )
    return top_chunks


def retrieve_and_answer(query: str, file_ids: list, file_paths: list = None,
                        scenario: str = "default", file_name_map: dict = None) -> dict:
    """
    混合检索（向量+BM25）→ 重排序 → 冲突检测 → 融合 → 调LLM生成答案
    file_paths: 由 API 层从 DB 查出，结构化文件直接读取，无需向量检索
    file_name_map: {磁盘路径: 真实文件名}，用于在来源中显示可读文件名
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
        top_chunks = _hybrid_retrieve(query, file_ids, file_paths=file_paths, file_name_map=file_name_map)
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
            temperature=0,
            max_tokens=1500
        )

        answer = (response.choices[0].message.content or "").strip()

        avg_score = float(np.mean([c["hybrid_score"] for c in top_chunks])) if top_chunks else 0.0
        confidence = round(min(avg_score * 1.2, 1.0), 2) if top_chunks else -1

        top_chunks, fusion_info = fuse_results(top_chunks, conflicts)

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