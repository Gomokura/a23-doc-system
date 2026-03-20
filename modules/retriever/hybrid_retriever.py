"""
混合检索与问答模块 - 负责人: 成员3
函数签名已锁定，不得更改
"""
from typing import Optional

import numpy as np
from loguru import logger
from openai import OpenAI
from rank_bm25 import BM25Okapi

from config import settings
from modules.retriever.indexer import get_bm25_data, get_collection, _get_embed_model


def _normalize_scores(scores: list) -> list:
    """Min-Max 归一化得分到 [0, 1]"""
    if not scores:
        return []
    min_s, max_s = min(scores), max(scores)
    if max_s == min_s:
        return [1.0] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]


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
        # ═══════════════════════════════════════════════════════
        # 第1步：向量检索（权重 0.6）
        # ═══════════════════════════════════════════════════════
        model = _get_embed_model()
        collection = get_collection()

        query_embedding = model.encode(query).tolist()

        # 从 ChromaDB 查询
        vector_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=settings.top_k * 2,  # 多取一些，留给混合排序
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
                    "vector_score": 1.0 / (1.0 + distances[i]) if i < len(distances) else 0
                })

        logger.info(f"向量检索完成: 获取 {len(vector_chunks)} 条结果")

        # ═══════════════════════════════════════════════════════
        # 第2步：BM25 检索（权重 0.4）
        # ═══════════════════════════════════════════════════════
        bm25_corpus, bm25_doc_map = get_bm25_data()
        bm25_scores_map = {}

        if bm25_corpus:
            # 分词构建 BM25
            tokenized_corpus = [doc.split() for doc in bm25_corpus]
            bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = query.split()
            raw_scores = bm25.get_scores(tokenized_query)

            # 映射到 chunk_id
            for idx, score in enumerate(raw_scores):
                if idx < len(bm25_corpus):
                    content = bm25_corpus[idx]
                    # 找到对应的 chunk_id（简单用内容匹配）
                    for cid, info in bm25_doc_map.items():
                        if info.get("content") == content:
                            bm25_scores_map[cid] = score
                            break

        logger.info(f"BM25 检索完成: {len(bm25_scores_map)} 条得分")

        # ═══════════════════════════════════════════════════════
        # 第3步：混合得分排序，取 TOP_K
        # ═══════════════════════════════════════════════════════
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

            # 混合得分 = 向量 × 0.6 + BM25 × 0.4
            hybrid_score = vector_score * settings.vector_weight + bm25_score_norm * settings.bm25_weight

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

        # ═══════════════════════════════════════════════════════
        # 第4步：多源冲突检测与融合
        # ═══════════════════════════════════════════════════════
        conflicts = detect_conflicts(top_chunks)
        if conflicts:
            logger.info(f"检测到 {len(conflicts)} 处冲突")
            for cf in conflicts:
                logger.info(f"  冲突字段: {cf['key']}, 出现值: {cf['values']}")

        # ═══════════════════════════════════════════════════════
        # 第5步：调用 LLM 生成答案
        # ═══════════════════════════════════════════════════════
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

        # ═══════════════════════════════════════════════════════
        # 第6步：构造返回结果
        # ═══════════════════════════════════════════════════════
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
