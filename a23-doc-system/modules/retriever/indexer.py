"""
索引构建模块 - 负责人: 成员3
函数签名已锁定，不得更改
"""
import os
import pickle
from typing import Optional, List, Set

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger
from sentence_transformers import SentenceTransformer

from config import settings

# 全局变量（模块级缓存）
_embed_model: Optional[SentenceTransformer] = None
_chroma_client: Optional[chromadb.PersistentClient] = None
_bm25_corpus: list = []
_bm25_doc_map: dict = {}
_indexed_files: Set[str] = set()  # 已索引的文件ID集合

# ═══════════════════════════════════════════════════════════════════════
# 批量编码配置
# ═══════════════════════════════════════════════════════════════════════
BATCH_SIZE = 32  # 批量编码大小，可根据内存调整


def _get_embed_model() -> SentenceTransformer:
    """获取或初始化嵌入模型（单例模式）"""
    global _embed_model
    if _embed_model is None:
        logger.info(f"加载嵌入模型: {settings.embed_model}")
        _embed_model = SentenceTransformer(settings.embed_model)
    return _embed_model


def _get_chroma_client() -> chromadb.PersistentClient:
    """获取或初始化 ChromaDB 客户端（单例模式）"""
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(settings.chroma_path, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
    return _chroma_client


def _load_bm25_index() -> bool:
    """从磁盘加载 BM25 索引和已索引文件列表"""
    global _bm25_corpus, _bm25_doc_map, _indexed_files
    bm25_path = os.path.join(settings.chroma_path, "bm25_index.pkl")
    if os.path.exists(bm25_path):
        try:
            with open(bm25_path, "rb") as f:
                data = pickle.load(f)
                _bm25_corpus = data.get("corpus", [])
                _bm25_doc_map = data.get("doc_map", {})
                _indexed_files = set(data.get("indexed_files", []))
            logger.info(f"加载 BM25 索引: {len(_bm25_corpus)} 条文档, 已索引文件: {len(_indexed_files)} 个")
            return True
        except Exception as e:
            logger.warning(f"加载 BM25 索引失败: {e}，将重新构建")
    return False


def _save_bm25_index() -> bool:
    """持久化 BM25 索引到磁盘"""
    bm25_path = os.path.join(settings.chroma_path, "bm25_index.pkl")
    try:
        with open(bm25_path, "wb") as f:
            pickle.dump({
                "corpus": _bm25_corpus,
                "doc_map": _bm25_doc_map,
                "indexed_files": list(_indexed_files)  # 记录已索引文件
            }, f)
        logger.info(f"BM25 索引已持久化: {bm25_path}")
        return True
    except Exception as e:
        logger.error(f"持久化 BM25 索引失败: {e}")
        return False


def build_index(parsed_doc: dict, force_rebuild: bool = False) -> bool:
    """
    将 ParsedDocument 写入向量数据库（ChromaDB）和 BM25 索引

    Args:
        parsed_doc: ParsedDocument dict（规范文档 4.1）
        force_rebuild: 是否强制重建（忽略增量检查）

    Returns:
        True 成功 / False 失败
    """
    file_id = parsed_doc.get("file_id", "unknown")
    filename = parsed_doc.get("filename", "unknown")
    chunks = parsed_doc.get("chunks", [])

    logger.info(f"开始构建索引: file_id={file_id}, chunks数量={len(chunks)}")

    if not chunks:
        logger.warning(f"文档 {file_id} 没有 chunks，跳过索引构建")
        return False

    # ═══════════════════════════════════════════════════════════════════════
    # 增量索引：检查文件是否已索引
    # ═══════════════════════════════════════════════════════════════════════
    if not force_rebuild:
        _load_bm25_index()
        if file_id in _indexed_files:
            logger.info(f"文件 {file_id} 已索引，跳过（使用 force_rebuild=True 强制重建）")
            return True

    try:
        # 初始化模型和客户端
        model = _get_embed_model()
        client = _get_chroma_client()

        # 获取或创建集合（支持配置距离度量）
        collection = client.get_or_create_collection(
            name="documents",
            metadata={
                "description": "A23 文档检索集合",
                "distance_metric": settings.chroma_distance_metric,  # cosine | l2 | ip
            }
        )

        # 准备批量数据
        ids = []
        embeddings = []
        documents = []
        metadatas = []

        # 加载已有 BM25 数据
        _load_bm25_index()

        # ═══════════════════════════════════════════════════════════════
        # 批量向量编码优化：一次性对所有文本进行编码，减少模型调用次数
        # ═══════════════════════════════════════════════════════════════
        # 先收集所有 chunk 的内容和元数据
        chunk_data_list = []
        for chunk in chunks:
            content = chunk.get("content", "")
            page = chunk.get("page", 0)
            if not content:
                continue
            chunk_data_list.append({
                "chunk_id": chunk.get("chunk_id", f"{file_id}_{len(chunk_data_list)}"),
                "content": content,
                "page": page
            })

        if not chunk_data_list:
            logger.warning(f"文档 {file_id} 没有有效 chunks，跳过索引构建")
            return False

        # 批量编码所有文本
        all_contents = [c["content"] for c in chunk_data_list]
        logger.info(f"开始批量编码 {len(all_contents)} 条文本，batch_size={BATCH_SIZE}")

        # 分批编码，防止内存溢出
        all_embeddings = []
        for i in range(0, len(all_contents), BATCH_SIZE):
            batch = all_contents[i:i + BATCH_SIZE]
            batch_embeddings = model.encode(batch, convert_to_numpy=True)
            all_embeddings.extend(batch_embeddings.tolist())
            logger.debug(f"编码进度: {min(i + BATCH_SIZE, len(all_contents))}/{len(all_contents)}")

        logger.info(f"批量编码完成: {len(all_embeddings)} 条")

        # 组装最终数据
        for idx, chunk_data in enumerate(chunk_data_list):
            ids.append(chunk_data["chunk_id"])
            embeddings.append(all_embeddings[idx])
            documents.append(chunk_data["content"])
            metadatas.append({
                "file_id": file_id,
                "source_file": filename,
                "page": chunk_data["page"],
                "chunk_type": "text"
            })

            # 同步更新 BM25 索引数据
            _bm25_corpus.append(chunk_data["content"])
            _bm25_doc_map[chunk_data["chunk_id"]] = {
                "content": chunk_data["content"],
                "file_id": file_id,
                "source_file": filename,
                "page": chunk_data["page"]
            }

        # 批量写入 ChromaDB
        if ids:
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"ChromaDB 写入完成: {len(ids)} 条")

        # 记录已索引文件
        _indexed_files.add(file_id)

        # 持久化 BM25 索引
        _save_bm25_index()
        logger.info(f"索引构建成功: file_id={file_id}")
        return True

    except Exception as e:
        logger.error(f"索引构建失败: {e}")
        return False


def get_bm25_data() -> tuple:
    """获取 BM25 语料和文档映射，供 hybrid_retriever 使用"""
    _load_bm25_index()
    return _bm25_corpus, _bm25_doc_map


def get_collection():
    """获取 ChromaDB 集合，供 hybrid_retriever 使用"""
    client = _get_chroma_client()
    return client.get_collection("documents")


def delete_index(file_id: str) -> bool:
    """
    删除指定文件的索引（向量 + BM25）

    Args:
        file_id: 要删除的文件ID

    Returns:
        True 成功 / False 失败
    """
    try:
        _load_bm25_index()

        # 1. 从 ChromaDB 删除
        collection = get_collection()
        collection.delete(where={"file_id": file_id})

        # 2. 从 BM25 索引中删除
        new_corpus = []
        new_doc_map = {}
        for chunk_id, info in _bm25_doc_map.items():
            if info.get("file_id") != file_id:
                new_corpus.append(info["content"])
                new_doc_map[chunk_id] = info

        _bm25_corpus = new_corpus
        _bm25_doc_map = new_doc_map
        _indexed_files.discard(file_id)

        # 3. 持久化
        _save_bm25_index()

        logger.info(f"删除索引成功: file_id={file_id}")
        return True

    except Exception as e:
        logger.error(f"删除索引失败: {e}")
        return False


def get_indexed_files() -> list:
    """获取已索引的文件ID列表"""
    _load_bm25_index()
    return list(_indexed_files)


def clear_all_indexes() -> bool:
    """
    清空所有索引（谨慎使用）

    Returns:
        True 成功 / False 失败
    """
    try:
        # 1. 清空 ChromaDB
        collection = get_collection()
        collection.delete(where={})

        # 2. 清空 BM25
        global _bm25_corpus, _bm25_doc_map, _indexed_files
        _bm25_corpus = []
        _bm25_doc_map = {}
        _indexed_files = set()

        # 3. 删除持久化文件
        bm25_path = os.path.join(settings.chroma_path, "bm25_index.pkl")
        if os.path.exists(bm25_path):
            os.remove(bm25_path)

        logger.info("已清空所有索引")
        return True

    except Exception as e:
        logger.error(f"清空索引失败: {e}")
        return False
