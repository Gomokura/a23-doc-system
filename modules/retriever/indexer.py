"""
索引构建模块 - 负责人: 成员3
函数签名已锁定，不得更改
"""
import os
import pickle
from typing import Optional

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
    """从磁盘加载 BM25 索引"""
    global _bm25_corpus, _bm25_doc_map
    bm25_path = os.path.join(settings.chroma_path, "bm25_index.pkl")
    if os.path.exists(bm25_path):
        try:
            with open(bm25_path, "rb") as f:
                data = pickle.load(f)
                _bm25_corpus = data.get("corpus", [])
                _bm25_doc_map = data.get("doc_map", {})
            logger.info(f"加载 BM25 索引: {len(_bm25_corpus)} 条文档")
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
                "doc_map": _bm25_doc_map
            }, f)
        logger.info(f"BM25 索引已持久化: {bm25_path}")
        return True
    except Exception as e:
        logger.error(f"持久化 BM25 索引失败: {e}")
        return False


def build_index(parsed_doc: dict) -> bool:
    """
    将 ParsedDocument 写入向量数据库（ChromaDB）和 BM25 索引

    Args:
        parsed_doc: ParsedDocument dict（规范文档 4.1）

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

    try:
        # 初始化模型和客户端
        model = _get_embed_model()
        client = _get_chroma_client()

        # 获取或创建集合
        collection = client.get_or_create_collection(
            name="documents",
            metadata={"description": "A23 文档检索集合"}
        )

        # 准备批量数据
        ids = []
        embeddings = []
        documents = []
        metadatas = []

        # 加载已有 BM25 数据
        _load_bm25_index()

        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", f"{file_id}_{len(ids)}")
            content = chunk.get("content", "")
            page = chunk.get("page", 0)

            if not content:
                continue

            # 生成向量嵌入
            embedding = model.encode(content).tolist()

            ids.append(chunk_id)
            embeddings.append(embedding)
            documents.append(content)
            metadatas.append({
                "file_id": file_id,
                "source_file": filename,
                "page": page,
                "chunk_type": chunk.get("chunk_type", "text")
            })

            # 同步更新 BM25 索引数据
            _bm25_corpus.append(content)
            _bm25_doc_map[chunk_id] = {
                "content": content,
                "file_id": file_id,
                "source_file": filename,
                "page": page
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
