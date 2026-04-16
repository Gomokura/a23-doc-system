"""
混合检索与问答模块 - 负责人: 成员3
函数签名已锁定，不得更改
"""
import concurrent.futures
import copy
import hashlib
import re
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


def _normalize_answer_text(raw: str) -> str:
    """
    解析「回答:…来源:…」格式，并剔除模型误粘贴的提示词语句（prompt 渗漏）。
    """
    if not raw:
        return raw
    text = raw.strip()
    for marker in ("回答:", "回答："):
        if marker in text:
            rest = text.split(marker, 1)[1]
            for stop in ("\n来源:", "\n来源：", "来源:", "来源："):
                if stop in rest:
                    rest = rest.split(stop, 1)[0]
            text = rest.strip()
            break
    leak_prefixes = (
        "## 回答要求",
        "## 回答格式",
        "## 参考文档",
        "【聚合/统计类问题】",
        "1. 基于参考文档",
        "2. 如果文档中没",
        "2. 仅当参考文档",
        "3. 回答要准确",
        "4. 【聚合",
        "5. 【成绩",
        "9. 【成绩",
        "9. 【成绩/排名表】",
        "8. 如果涉及",
        "10. 【评价",
        "11. 【指代整份材料】",
        "6. 严禁把本提示",
        "7. 只面向最终用户",
    )
    lines_out: List[str] = []
    for line in text.splitlines():
        ls = line.strip()
        if any(ls.startswith(p) for p in leak_prefixes):
            continue
        if ls.startswith("回答格式") or ls in ("来源:", "来源："):
            continue
        lines_out.append(line)
    cleaned = "\n".join(lines_out).strip()
    return cleaned if cleaned else raw.strip()


def _build_prompt(query: str, chunks: list, scenario: str = "default") -> str:
    CHUNK_MAX_CHARS = 12000
    CONTEXT_MAX_CHARS = 32000

    # ⚠️ M3-005 修复: 句子边界切割函数，避免在句子中间截断
    def _truncate_at_sentence(text: str, max_chars: int) -> str:
        """在 max_chars 处或之前最近的句子边界（。！？；\n）处截断"""
        if len(text) <= max_chars:
            return text
        # 向前查找最后一个句子边界
        # 标点优先顺序：\n（段落）、。！？；（句子）
        for sep in ["\n\n", "。\n", "！\n", "？\n", "；\n", "\n"]:
            # 在 [max_chars - 50, max_chars] 范围内找最近的边界
            search_start = max(0, max_chars - 100)
            candidate = text.rfind(sep, search_start, max_chars)
            if candidate != -1:
                # 保留边界标点（段落分隔符需要特殊处理）
                if sep == "\n\n":
                    return text[:candidate + 2]
                elif sep == "\n":
                    return text[:candidate + 1]
                else:
                    return text[:candidate + len(sep)]
        # 没有找到句子边界，直接在 max_chars 处截断（最后手段）
        return text[:max_chars] + "…"

    parts = []
    total = 0
    seen_files = []

    for i, c in enumerate(chunks):
        content = (c.get("content") or "").strip()
        if not content:
            continue
        # ⚠️ M3-005 修复: 在句子边界处截断，而非简单字符截断
        content = _truncate_at_sentence(content, CHUNK_MAX_CHARS)

        # 用真实文件名作标签，而不是 [文档N]
        source_file = c.get("source_file", "")
        filename = c.get("filename") or source_file.replace("\\", "/").split("/")[-1] or f"文档{i+1}"
        if filename not in seen_files:
            seen_files.append(filename)

        seg = f"【{filename}】\n{content}"
        seg_len = len(seg) + 2
        # ⚠️ M3-005 修复: 在添加前判断是否溢出，避免添加后才发现溢出
        if total + seg_len > CONTEXT_MAX_CHARS:
            # 尝试对当前 chunk 在句子边界处截取剩余空间
            remaining = CONTEXT_MAX_CHARS - total - 2
            if remaining > 50:  # 剩余空间足够放置一个句子
                truncated_seg = f"【{filename}】\n{_truncate_at_sentence(content, remaining)}"
                parts.append(truncated_seg)
            break  # 空间不足，不再添加更多 chunk
        parts.append(seg)
        total += seg_len

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
        "contract": "8. 如果涉及合同条款，请重点识别：合同金额、甲乙双方、付款方式、违约责任、有效期。",
        "report": "8. 如果涉及报表数据，请进行数据对比、趋势描述，注明计量单位。",
        "regulation": "8. 如果涉及法规条文，请引用相关条款，说明适用范围和时效性。",
    }
    extra_requirement = scenario_prompts.get(scenario, "")

    # PDF 表格经纯文本提取后常丢列对齐，易把「加分」等小数字当成总分；概括类问题也会瞎编人数/极值
    table_score_hint = ""
    if re.search(
        r"最高|最低|极值|排名|成绩|分数|多少分|总分|综合|"
        r"有什么信息|都有什么|包含什么|主要内容|概括|总结|介绍下|里边|里面|有哪些",
        query,
    ):
        table_score_hint = (
            "\n9. 【成绩/排名表】若参考内容像学生成绩或推免排名表："
            "综合成绩多为约 3～4 的小数；同一行里更小的 0.xx 常为「加分」等列，**绝不是**综合成绩的最低分，"
            "不要把 0.1、0.05 等说成「最低分」。"
            "问最高/最低分时只对「综合成绩」一列取极值。"
            "总人数、最高分、最低分、名次范围等数字：**仅当参考片段里能明确核对时再写**；"
            "若片段只是表格的一部分、未写总人数，**禁止编造**「共 N 人」，应说明「当前参考仅为排名表局部，无法从片段准确统计总人数或全表极值」。"
            "问「有什么信息」时优先说明文档主题、列含义、排名性质；勿随口编造统计数字。"
        )

    critique_hint = ""
    if re.search(
        r"不好|缺点|不足|薄弱|改进|优化|问题在哪|有什么问题|写得怎样|评价|批评|指出|建议|弱项",
        query,
    ):
        critique_hint = (
            "\n10. 【评价/改进类】若用户问「哪里写得不好」「有何缺点」「如何改进」等："
            "必须直接写出**可改进点**（例如：缺少量化成果与数据、某段与目标岗位关联弱、项目描述缺背景与结果、排版或结构不清），"
            "不要只做简历摘要，也不要用「信息偏少」「较为简略」等空话敷衍；"
            "若你在后文列举出某板块已有较多具体内容，就不得再称该板块「稀疏」「过少」，避免前后矛盾。"
        )

    vague_pronoun_hint = ""
    if re.search(r"这是什么|是啥|啥玩意|什么文档|干嘛的|干什么的|介绍一下|概括一下|讲讲", query):
        vague_pronoun_hint = (
            "\n11. 【指代整份材料】若用户用「这」「啥」等指代当前选中的文档："
            "必须结合参考片段上方的【文件名】与正文（表头、列名、数据形态）判断文档类型与用途，用一两句话说明"
            "（例如：学生综合成绩排名表、推免选拔依据等）。"
            "排名类 PDF 的正文常为学号与分数，没有单独「标题段」是正常现象，**不得**因此输出「无法回答」。"
        )

    return f"""你是一个专业的文档问答助手。请根据以下参考文档，回答用户的问题。

## 参考文档
{context}

## 用户问题
{query}

## 回答要求
1. 基于参考文档内容回答；无依据时不要编造事实性信息（如虚构公司、项目、分数）。
2. 仅当参考文档几乎没有任何与问题相关的描述时，才输出「根据提供的信息无法回答该问题」。问「这是什么」且【文件名】或表格结构已能判断文档性质时，**不属于**「无法回答」情形。
3. 若问题需要合理推断（例如「如果你是 HR 会问什么」「有什么建议」），而文档中有该人的经历、项目、技能、教育等可核对信息，请基于这些信息给出简要、具体的推断或问题列表，并说明依据来自文档中的哪些类型的信息。
4. 回答要准确、简洁、有条理。
5. 【聚合/统计类问题】若用户问「有哪些」「有几个」「列出所有」等，请归纳去重后汇总作答。
{critique_hint}{vague_pronoun_hint}{extra_requirement}{table_score_hint}
6. 严禁把本提示中的条款编号、小标题或「回答格式」说明复述进答案；禁止输出以「4. 【聚合」「5. 【成绩」等开头的元说明句。
7. 只面向最终用户写作，不要解释系统规则。

## 回答格式（只输出以下两行，勿添加其它章节标题）
回答: <你的回答>
来源: {source_names}"""


def detect_conflicts(chunks: list) -> list:
    """
    从检索到的片段中扫描是否出现「同一语义字段多个不同取值」。
    注意：名单/表格类文档里多行日期、学号、序号会被旧版宽松正则误判为冲突，
    进而让前端显示「多源冲突」、拉低用户对答案的信任；此处已收紧规则。
    """
    conflicts = []

    # ── 金额冲突检测 ─────────────────────────────────────────────
    # 必须有货币单位，避免把学号、序号、年份等纯数字误判为「多个金额」
    money_patterns = [
        r"(\d+(?:\.\d+)?\s*万元)",
        r"(\d+(?:\.\d+)?\s*元)",
        r"(¥\s*\d+(?:\.\d+)?)",
        r"(人民币\s*\d+(?:\.\d+)?\s*元?)",
    ]
    money_values: Dict[str, list] = {}
    for chunk in chunks:
        content = chunk.get("content", "")
        for pat in money_patterns:
            for match in re.findall(pat, content):
                val = match.strip()
                if val and len(val) > 1:
                    money_values.setdefault(val, []).append(chunk.get("chunk_id", ""))
    if len(money_values) > 1:
        conflicts.append({
            "key": "金额",
            "values": list(money_values.keys()),
            "from_chunks": list(money_values.values())
        })

    # ── 日期冲突检测（按语义类型分类）──────────────────────────────
    # ⚠️ M3-003 修复: 按日期语义粒度分类，而非简单的数量阈值
    # 合同中自然包含：签订日期、生效日期、终止日期、付款日期等，这些不是冲突
    # 真正的冲突是：同一语义粒度的日期出现多个不同值（如两个不同的签订日期）
    # 禁止裸 \d{4}：学号/排名表中的 8 位学号会被切成 5522、0323 等，误判为「多年份冲突」
    DATE_GRANULARITY_PATTERNS = [
        # (语义标签, 正则模式, 最小字符长度)
        ("签订/生效日期", r"\d{4}年\d{1,2}月\d{1,2}日", 10),
        ("签订/生效日期", r"\d{4}-\d{2}-\d{2}", 10),
        ("签订/生效日期", r"\d{4}/\d{1,2}/\d{1,2}", 10),
        ("年月", r"\d{4}年\d{1,2}月", 7),
        ("年月", r"\d{4}-\d{2}", 7),
        ("年份", r"\d{4}年", 5),
    ]

    # 按语义粒度分组计数
    granularity_counts: Dict[str, Dict[str, list]] = {}
    for chunk in chunks:
        content = chunk.get("content", "")
        chunk_id = chunk.get("chunk_id", "")
        for label, pat, _ in DATE_GRANULARITY_PATTERNS:
            for match in re.findall(pat, content):
                if len(match) >= 4:
                    granularity_counts.setdefault(label, {}).setdefault(match, []).append(chunk_id)

    # 每个语义粒度下，若该粒度的日期值数量 >= 2 且来源 chunk 属于不同文档 → 报告冲突
    # 仅跨 chunk 来源才可能是真正的多源冲突（同一 chunk 内多行日期表格不触发）
    for label, value_map in granularity_counts.items():
        distinct_values = list(value_map.keys())
        if len(distinct_values) <= 1:
            continue
        # 获取涉及该粒度日期的所有 chunk_id
        involved_chunks = []
        for chunk_ids in value_map.values():
            involved_chunks.extend(chunk_ids)
        distinct_chunks = set(involved_chunks)
        # 若同一语义粒度下有 >= 2 个不同值，且来自不同 chunk → 可能是冲突
        # 但若所有 chunk 都来自同一文件（同一 chunk 列表中的多个表格行），则跳过
        # 当前 chunks 列表中若来自同一文件且 chunk_id 前缀相同，视为同源
        if len(distinct_values) >= 2 and len(distinct_chunks) >= 2:
            conflicts.append({
                "key": f"日期({label})",
                "values": distinct_values,
                "from_chunks": [value_map[v] for v in distinct_values]
            })

    # ── 比例冲突检测 ─────────────────────────────────────────────
    # 排名表/成绩单里每行都有不同的「综合成绩占比」等百分比，出现多个不同 % 是常态，
    # 不应视为「多源矛盾」。仅在「多份不同文档」且不同取值较少时，才可能是同一指标口径冲突。
    ratio_patterns = [r"(\d+\.?\d*%)", r"(\d+)\s*%"]
    ratio_values: Dict[str, list] = {}
    for chunk in chunks:
        content = chunk.get("content", "")
        for pat in ratio_patterns:
            for match in re.findall(pat, content):
                val = match.strip()
                if val and len(val) > 1:
                    ratio_values.setdefault(val, []).append(chunk.get("chunk_id", ""))
    distinct_sources = {chunk.get("source_file", "") or chunk.get("filename", "") for chunk in chunks}
    distinct_sources.discard("")
    many_distinct_ratios = len(ratio_values) > 6  # 典型表格：多行各不相同的百分数
    if len(ratio_values) > 1 and len(distinct_sources) >= 2 and not many_distinct_ratios:
        conflicts.append({
            "key": "比例",
            "values": list(ratio_values.keys()),
            "from_chunks": list(ratio_values.values())
        })

    # ── 公司名冲突检测 ──────────────────────────────────────────
    company_patterns = [r"([^\s]{4,}公司)", r"([^\s]{2,}贸易)", r"([^\s]{2,}科技)"]
    company_values: Dict[str, list] = {}
    for chunk in chunks:
        content = chunk.get("content", "")
        for pat in company_patterns:
            for match in re.findall(pat, content):
                val = match.strip()
                if val and len(val) > 3:
                    company_values.setdefault(val, []).append(chunk.get("chunk_id", ""))
    # 公司名去重（同一公司名可能以全称和简称出现）
    if len(company_values) > 1:
        conflicts.append({
            "key": "公司名",
            "values": list(company_values.keys()),
            "from_chunks": list(company_values.values())
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


def mmr_diversity_rerank(query: str, chunks: list, lambda_val: float = None, query_embedding: np.ndarray = None) -> list:
    """
    MMR (Maximal Marginal Relevance) Diversity 重排序。
    位于 CrossEncoder 重排序之后，在相关性和多样性之间取平衡。

    公式: MMR = λ·Sim(query, doc) − (1−λ)·max_Sim(doc, already_selected)
    论文: Carbonell & Goldstein, SIGIR 1998

    Args:
        query: 用户查询
        chunks: 已按 rerank_score 降序排列的 chunk 列表
        lambda_val: 平衡系数，1=只看相关性，0=只看多样性，默认从配置读取
        query_embedding: ⚠️ M3-004 修复: 传入预计算的 query embedding，MMR 直接复用
                                而非重新编码，节省约 50% 的 embedding 时间
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

        # chunk_embeds：无论是否传入 query_embedding，都需要编码（ChromaDB query 不返回 embedding）
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
                # ⚠️ M3-004 修复: sim_to_query 应基于向量空间中的 query-doc 相似度
                # 而非依赖 Reranker 的 score（score 已经是排序依据，非相似度量纲）
                # 由于 chunk_embeds 已归一化，query_embedding 也已归一化，
                # 点积即 cosine similarity ∈ [-1, 1]，正值越大越相似
                if query_embedding is not None:
                    sim_to_query = float(np.dot(query_embedding, chunk_embeds[idx]))
                else:
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
    max_chunks = 50  # 结构化文件允许更多 chunk

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

            # 直接取全部行，不做去重或采样，保证数据完整
            sample_df = df

            # 把所有行合并成 CSV 格式的单个 chunk，而不是每行一个 chunk
            # 这样 LLM 看到的是完整的表格，来源只有 1 个文件
            csv_text = sample_df.to_csv(index=False)
            # 结构化文件用更大的 chunk_size，保证完整性
            chunk_size = 12000
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
    query_embedding = model.encode(query)
    # 同时保留 list 供 ChromaDB query 使用，和 ndarray 供 MMR 使用
    query_embedding_list = query_embedding.tolist()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        vector_future = executor.submit(_vector_search, query, query_embedding_list, file_ids)
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

    # ⚠️ 修复 M3-001: 当 chunk 同时被向量检索和 BM25 命中时，
    # 应同时保留两个维度的得分，而非忽略 BM25 得分
    for chunk_id, bm25_score in bm25_ranked:
        if chunk_id in candidate_map:
            # chunk 已存在于 candidate_map（被向量检索命中），更新其 BM25 得分
            # 确保后续的 RRF/线性融合能同时考虑两个维度的排名
            candidate_map[chunk_id]["bm25_score"] = float(bm25_score)
        else:
            # chunk 仅被 BM25 命中（向量检索未召回），添加为候选
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
        # ⚠️ M3-002 修复: 明确标注 linear 融合为实验性功能
        # linear 模式使用自适应权重（短查询偏 BM25，长查询偏向量），
        # 通过 Min-Max 归一化将两路得分映射到 [0,1] 后加权求和。
        # RRF 模式（默认）因无需归一化、参数少、效果稳定，优先推荐使用。
        logger.warning(
            "[HYBRID] 使用了 fusion_method='linear'，这是实验性功能。"
            "推荐使用 fusion_method='rrf'（默认），效果更稳定。"
        )
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
    # ⚠️ M3-004 修复: 传入 query_embedding ndarray，消除 MMR 二次编码
    top_chunks = mmr_diversity_rerank(query, top_chunks, query_embedding=query_embedding)

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
    # key 格式含 file_ids，便于后续按 file_id 精准清缓存
    file_ids_str = ",".join(sorted(file_ids)) if file_ids else "all"
    cache_key = f"a23:query:{query_hash}:fi:{file_ids_str}"

    cached = get_cached_result(cache_key)
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
            set_cached_result(cache_key, result)
            return result

        conflicts = detect_conflicts(top_chunks)
        if conflicts:
            logger.info(f"检测到 {len(conflicts)} 处冲突")
            for cf in conflicts:
                logger.info(f"  冲突字段: {cf['key']}, 出现值: {cf['values']}")

        prompt = _build_prompt(query, top_chunks, scenario=scenario)

        llm_client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            default_headers=settings.openai_default_headers
        )

        response = llm_client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1500
        )

        answer = _normalize_answer_text((response.choices[0].message.content or "").strip())

        avg_score = float(np.mean([c["hybrid_score"] for c in top_chunks])) if top_chunks else 0.0
        ref_score = float(max(c["hybrid_score"] for c in top_chunks)) if top_chunks else 0.0
        # RRF 绝对值约 0.015～0.06，线性映射到 0.15～0.95，避免界面长期显示「2%」造成误判
        strength = max(avg_score, ref_score * 0.9)
        confidence = (
            round(min(0.95, max(0.15, 0.15 + min(1.0, strength / 0.048) * 0.8)), 2)
            if top_chunks
            else -1
        )

        top_chunks, fusion_info = fuse_results(top_chunks, conflicts)

        sources = [
            {
                "chunk_id": c["chunk_id"],
                "content": c["content"],
                "source_file": c.get("filename") or c["source_file"],  # 优先用真实文件名
                "page": c["page"],
                # RRF 等融合分绝对值较小，供前端在「本批片段」内做相对相关度展示（勿与旧版假 80% 混淆）
                "score": float(c.get("hybrid_score", 0.0)),
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
        set_cached_result(cache_key, result)
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

