"""
索引构建模块 - 负责人: 成员3
函数签名已锁定，不得更改
"""
from loguru import logger


def build_index(parsed_doc: dict) -> bool:
    """
    将 ParsedDocument 写入向量数据库（ChromaDB）和 BM25 索引

    Args:
        parsed_doc: ParsedDocument dict（规范文档 4.1）

    Returns:
        True 成功 / False 失败
    """
    file_id = parsed_doc.get("file_id", "unknown")
    logger.info(f"开始构建索引: file_id={file_id}")

    # ═══════════════════════════════════════════════════════
    # TODO: 成员3在此实现索引逻辑
    # 参考技术方案：
    #   向量索引 → chromadb.PersistentClient + sentence-transformers
    #   BM25索引 → rank_bm25.BM25Okapi，持久化到 db/ 目录
    # ═══════════════════════════════════════════════════════

    logger.warning(f"⚠️  build_index 是空实现，成员3请尽快实现")
    return True
