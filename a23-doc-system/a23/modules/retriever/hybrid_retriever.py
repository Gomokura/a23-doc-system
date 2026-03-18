"""
混合检索与问答模块 - 负责人: 成员3
函数签名已锁定，不得更改
"""
from loguru import logger


def retrieve_and_answer(query: str, file_ids: list) -> dict:
    """
    混合检索（向量+BM25）→ 重排序 → 调LLM生成答案

    Args:
        query:    用户问题
        file_ids: 限定检索的文件列表，空列表表示检索所有

    Returns:
        AnswerResult dict（规范文档 4.3）
    """
    logger.info(f"收到问答请求: query={query}, file_ids={file_ids}")

    # ═══════════════════════════════════════════════════════
    # TODO: 成员3在此实现检索与问答逻辑
    # 参考技术方案：
    #   1. 向量检索 → ChromaDB.query()，权重 0.6
    #   2. BM25检索 → rank_bm25，权重 0.4
    #   3. 混合得分 = 向量 × 0.6 + BM25 × 0.4
    #   4. 取 TOP_K=5 个 chunk 构建 prompt
    #   5. 调用 DeepSeek API 生成答案
    # ═══════════════════════════════════════════════════════

    # 目前返回 Mock 数据，成员3完成后替换此 return
    from tests.mock_data import MOCK_ANSWER_RESULT
    import copy
    mock = copy.deepcopy(MOCK_ANSWER_RESULT)
    mock["query"] = query
    logger.warning(f"⚠️  retrieve_and_answer 仍在使用 Mock 数据，成员3请尽快实现")
    return mock
