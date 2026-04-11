"""
索引构建模块 - 负责人: 成员3
函数签名已锁定，不得更改
"""
import os
import pickle
from typing import Optional, List, Set, Dict, Callable

import numpy as np
import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from config import settings

# ═══════════════════════════════════════════════════════════════════════
# 本地 Ollama Embedding（调用 http://localhost:11434/v1/embeddings）
# ═══════════════════════════════════════════════════════════════════════
class OllamaEmbedder:
    """
    调用本地 Ollama Embedding API，接口与 SentenceTransformer 保持兼容。
    模型: nomic-embed-text（推荐，高质量且 Ollama 内置支持）
    """
    _API_BATCH = 1  # Ollama /v1/embeddings 单次只能接受 1 条

    def __init__(self):
        self._base_url = settings.llm_base_url.rstrip("/v1").rstrip("/")
        self._model = settings.embed_model  # 如 "nomic-embed-text"

    def encode(self, sentences, normalize_embeddings: bool = False,
               convert_to_numpy: bool = True, batch_size: int = None):
        import requests as _requests

        single = isinstance(sentences, str)
        if single:
            sentences = [sentences]

        all_vecs: list = []
        for text in sentences:
            _headers = {}
            if self._base_url and "ngrok" in self._base_url:
                _headers["ngrok-skip-browser-warning"] = "true"

            # /v1/embeddings 为 OpenAI 兼容接口，字段必须是 input，不能用 prompt（prompt 仅用于 /api/embeddings）
            resp = _requests.post(
                f"{self._base_url}/v1/embeddings",
                json={"model": self._model, "input": text},
                headers=_headers,
                timeout=120,
            )
            resp.raise_for_status()
            body = resp.json()
            if "data" in body and body["data"]:
                all_vecs.append(body["data"][0]["embedding"])
            elif "embedding" in body:
                all_vecs.append(body["embedding"])
            else:
                raise ValueError(f"无法解析 Ollama 向量响应: keys={list(body.keys())}")

        arr = np.array(all_vecs, dtype=np.float32)

        if normalize_embeddings:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            arr = arr / norms

        return arr[0] if single else arr


# 全局变量（模块级缓存）
_embed_model: Optional[OllamaEmbedder] = None
_chroma_client: Optional[chromadb.PersistentClient] = None

# 兼容旧逻辑保留
_bm25_corpus: list = []
_bm25_doc_map: dict = {}

# 新增：BM25 有序记录，保证 idx <-> chunk_id 一一对应
_bm25_records: List[Dict] = []

_indexed_files: Set[str] = set()  # 已索引的文件ID集合

# BM25 持久化分词结果，避免冷启动时重复分词
_tokenized_corpus_pkl: List[list] = []  # 已持久化的分词语料

# ⚠️ M3-006 修复: 当前索引数据格式版本号
# 版本变更说明：
#   v0 (无版本字段): 初始版本
#   v1: 当前版本，包含 records + indexed_files + tokenized_corpus
# 当数据结构变更时，递增版本号。加载时版本不匹配则自动重建索引。
INDEX_VERSION = 1


def get_tokenized_corpus_pkl() -> List[list]:
    """导出分词语料，供 hybrid_retriever 复用（避免重复分词）"""
    return _tokenized_corpus_pkl

# ═══════════════════════════════════════════════════════════════════════
# 批量编码配置
# ═══════════════════════════════════════════════════════════════════════
BATCH_SIZE = 32  # 批量编码大小，可根据内存调整


def _get_embed_model() -> OllamaEmbedder:
    """获取或初始化本地 Ollama Embedding 客户端（单例模式）"""
    global _embed_model
    if _embed_model is None:
        logger.info(f"初始化 Ollama Embedding: base_url={settings.llm_base_url}, model={settings.embed_model}")
        _embed_model = OllamaEmbedder()
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


def _rebuild_bm25_views():
    """根据 _bm25_records 重建兼容视图"""
    global _bm25_corpus, _bm25_doc_map
    _bm25_corpus = [r["content"] for r in _bm25_records]
    _bm25_doc_map = {
        r["chunk_id"]: {
            "content": r["content"],
            "file_id": r["file_id"],
            "source_file": r["source_file"],
            "page": r["page"],
        }
        for r in _bm25_records
    }


def _invalidate_retriever_runtime():
    """索引变化后，让 retriever 的 BM25 运行时缓存失效，并清理问答缓存"""
    try:
        from modules.retriever.hybrid_retriever import invalidate_bm25_runtime_cache
        invalidate_bm25_runtime_cache()
    except Exception as e:
        logger.warning(f"BM25 运行时缓存失效失败: {e}")

    try:
        from modules.cache.redis_client import invalidate_cache
        invalidate_cache("*")
    except Exception as e:
        logger.warning(f"问答缓存清理失败: {e}")


def _load_bm25_index() -> bool:
    """从磁盘加载 BM25 索引和已索引文件列表"""
    global _bm25_corpus, _bm25_doc_map, _bm25_records, _indexed_files, _tokenized_corpus_pkl

    # ⚠️ M3-008 修复: 使用语义化的 .bm25 扩展名，区分普通 pickle 文件
    # 优先加载 .bm25（新扩展名），若无则尝试 .pkl（兼容旧版本）
    bm25_path_new = os.path.join(settings.chroma_path, "bm25_index.bm25")
    bm25_path_old = os.path.join(settings.chroma_path, "bm25_index.pkl")
    if os.path.exists(bm25_path_new):
        bm25_path = bm25_path_new
    elif os.path.exists(bm25_path_old):
        bm25_path = bm25_path_old
        logger.info("检测到旧版 .pkl 索引文件，将使用新扩展名 .bm25 保存")
    else:
        return False

    try:
        with open(bm25_path, "rb") as f:
            data = pickle.load(f)

        # ⚠️ M3-006 修复: 版本校验
        # - 无 version 字段（旧版本）→ 触发自动重建
        # - version != INDEX_VERSION → 触发自动重建
        saved_version = data.get("version", 0)
        if saved_version != INDEX_VERSION:
            logger.warning(
                f"BM25 索引版本不匹配 (保存={saved_version}, 当前={INDEX_VERSION})，"
                f"将重新构建索引。常见原因：代码升级后数据结构变更。"
            )
            return False

        _indexed_files = set(data.get("indexed_files", []))
        _tokenized_corpus_pkl = data.get("tokenized_corpus", [])

        # 新格式优先
        if "records" in data:
            _bm25_records = data.get("records", [])
            _rebuild_bm25_views()
        else:
            # 兼容旧格式：corpus + doc_map
            _bm25_corpus = data.get("corpus", [])
            _bm25_doc_map = data.get("doc_map", {})
            _bm25_records = []
            for chunk_id, info in _bm25_doc_map.items():
                _bm25_records.append({
                    "chunk_id": chunk_id,
                    "content": info.get("content", ""),
                    "file_id": info.get("file_id", ""),
                    "source_file": info.get("source_file", ""),
                    "page": info.get("page", 0),
                })
            _rebuild_bm25_views()

        logger.info(
            f"加载 BM25 索引: {len(_bm25_records)} 条记录, "
            f"已索引文件: {len(_indexed_files)} 个, "
            f"已加载分词语料: {len(_tokenized_corpus_pkl)} 条"
        )
        return True

    except Exception as e:
        logger.warning(f"加载 BM25 索引失败: {e}，将重新构建")
        return False


def _save_bm25_index(tokenized_corpus: list = None) -> bool:
    """持久化 BM25 索引到磁盘（包含分词结果以加速冷启动）"""
    # ⚠️ M3-008 修复: 使用语义化的 .bm25 扩展名
    bm25_path = os.path.join(settings.chroma_path, "bm25_index.bm25")
    try:
        with open(bm25_path, "wb") as f:
            pickle.dump({
                "version": INDEX_VERSION,  # ⚠️ M3-006 修复: 写入版本号
                "records": _bm25_records,
                "indexed_files": list(_indexed_files),
                "tokenized_corpus": tokenized_corpus if tokenized_corpus is not None else [],
            }, f)
        logger.info(f"BM25 索引已持久化: {bm25_path}, 分词语料 {len(tokenized_corpus) if tokenized_corpus else 0} 条, 版本 v{INDEX_VERSION}")
        return True
    except Exception as e:
        logger.error(f"持久化 BM25 索引失败: {e}")
        return False


def build_index(parsed_doc: dict, force_rebuild: bool = False,
                progress_callback: Optional[Callable[[int, str], None]] = None) -> bool:
    """
    将 ParsedDocument 写入向量数据库（ChromaDB）和 BM25 索引

    Args:
        parsed_doc: ParsedDocument dict（规范文档 4.1）
        force_rebuild: 是否强制重建（忽略增量检查）
        progress_callback: 可选，进度回调，接受 (percent: int, message: str)
                          percent 范围 70-100
    Returns:
        True 成功 / False 失败
    """
    _report = progress_callback or (lambda pct, msg: None)

    def _pct(p: int, m: str):
        _report(p, m)

    file_id = parsed_doc.get("file_id", "unknown")
    filename = parsed_doc.get("filename", "unknown")
    chunks = parsed_doc.get("chunks", [])

    logger.info(f"开始构建索引: file_id={file_id}, chunks数量={len(chunks)}")
    _pct(71, f"开始构建索引（{len(chunks)} 块）...")

    if not chunks:
        logger.warning(f"文档 {file_id} 没有 chunks，跳过索引构建")
        return False

    if not force_rebuild:
        _load_bm25_index()
        if file_id in _indexed_files:
            logger.info(f"文件 {file_id} 已索引，跳过（使用 force_rebuild=True 强制重建）")
            return True

    try:
        model = _get_embed_model()

        # ⚠️ M3-007 修复: 统一使用 get_collection() 获取 collection
        # 避免 get_or_create_collection 在重复调用时不更新元数据
        collection = get_collection()

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        _load_bm25_index()

        # 强制重建且该文件曾写入过索引：必须先删旧向量/BM25，否则会与 collection.add 叠旧数据或残留错误正文
        if force_rebuild and file_id in _indexed_files:
            logger.info(f"强制重建索引：先删除 file_id={file_id} 的旧向量与 BM25 记录")
            delete_index(file_id)

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

        all_contents = [c["content"] for c in chunk_data_list]
        logger.info(f"开始批量编码 {len(all_contents)} 条文本，batch_size={BATCH_SIZE}")

        all_embeddings = []
        for i in range(0, len(all_contents), BATCH_SIZE):
            batch = all_contents[i:i + BATCH_SIZE]
            batch_embeddings = model.encode(batch, convert_to_numpy=True)
            all_embeddings.extend(batch_embeddings.tolist())
            pct = 71 + int((i + BATCH_SIZE) / len(all_contents) * 18)
            _pct(min(89, pct), f"编码进度 {min(i + BATCH_SIZE, len(all_contents))}/{len(all_contents)}...")

        logger.info(f"批量编码完成: {len(all_embeddings)} 条")

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

            _bm25_records.append({
                "chunk_id": chunk_data["chunk_id"],
                "content": chunk_data["content"],
                "file_id": file_id,
                "source_file": filename,
                "page": chunk_data["page"],
            })

        if ids:
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"ChromaDB 写入完成: {len(ids)} 条")
            _pct(90, "ChromaDB 写入完成，正在持久化索引...")

        _indexed_files.add(file_id)

        _rebuild_bm25_views()
        _save_bm25_index()
        _invalidate_retriever_runtime()

        logger.info(f"索引构建成功: file_id={file_id}")
        return True

    except Exception as e:
        logger.error(f"索引构建失败: {e}")
        return False


def get_bm25_data() -> tuple:
    """兼容旧逻辑：返回 corpus 和 doc_map"""
    _load_bm25_index()
    return _bm25_corpus, _bm25_doc_map


def get_bm25_records(file_ids: Optional[list] = None) -> List[Dict]:
    """返回 BM25 有序记录，可按 file_id 过滤"""
    _load_bm25_index()
    if not file_ids:
        return list(_bm25_records)
    file_id_set = set(file_ids)
    return [r for r in _bm25_records if r.get("file_id") in file_id_set]


def get_collection():
    """获取 ChromaDB 集合，供 hybrid_retriever 使用"""
    # ⚠️ M3-007 修复: 分离 get 和 create 操作，
    # 先尝试获取，若不存在则创建；获取后显式更新元数据（而非依赖 get_or_create）
    client = _get_chroma_client()
    try:
        collection = client.get_collection("documents")
    except Exception:
        # collection 不存在时 get_collection 抛出异常，此时创建
        logger.info("ChromaDB collection 'documents' 不存在，创建新集合")
        collection = client.create_collection(
            name="documents",
            metadata={
                "description": "A23 文档检索集合",
                "distance_metric": settings.chroma_distance_metric,
            }
        )

    # ⚠️ M3-007 修复: 显式更新元数据
    # ChromaDB 的 get_or_create_collection 在 collection 已存在时不更新 metadata，
    # 故改为分离操作 + 手动 update（若 ChromaDB 版本支持）
    _update_collection_metadata(collection, {
        "description": "A23 文档检索集合",
        "distance_metric": settings.chroma_distance_metric,
    })
    return collection


def _update_collection_metadata(collection, metadata: dict):
    """
    尝试更新 collection 元数据。
    ChromaDB 0.4.x 开始支持 modify()，旧版本直接跳过（有兼容逻辑）。
    """
    try:
        # 部分 ChromaDB 版本支持直接设置
        if hasattr(collection, "modify") and callable(getattr(collection, "modify")):
            collection.modify(metadata=metadata)
            logger.debug(f"Collection 元数据已更新: {metadata}")
        else:
            logger.debug("当前 ChromaDB 版本不支持 modify()，元数据更新跳过（不影响功能）")
    except TypeError:
        # modify() 不接受 keyword 参数时尝试 positional
        try:
            collection.modify(metadata)
        except Exception as e:
            logger.debug(f"Collection metadata update failed (non-critical): {e}")
    except Exception as e:
        logger.debug(f"Collection metadata update failed (non-critical): {e}")


def delete_index(file_id: str) -> bool:
    """
    删除指定文件的索引（向量 + BM25）

    Args:
        file_id: 要删除的文件ID

    Returns:
        True 成功 / False 失败
    """
    try:
        global _bm25_records, _indexed_files

        _load_bm25_index()

        collection = get_collection()
        collection.delete(where={"file_id": file_id})

        _bm25_records = [r for r in _bm25_records if r.get("file_id") != file_id]
        _indexed_files.discard(file_id)

        _rebuild_bm25_views()
        _save_bm25_index()
        _invalidate_retriever_runtime()

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
        global _bm25_corpus, _bm25_doc_map, _bm25_records, _indexed_files, _tokenized_corpus_pkl

        collection = get_collection()
        collection.delete(where={})

        _bm25_corpus = []
        _bm25_doc_map = {}
        _bm25_records = []
        _indexed_files = set()
        _tokenized_corpus_pkl = []

        bm25_path = os.path.join(settings.chroma_path, "bm25_index.pkl")
        if os.path.exists(bm25_path):
            os.remove(bm25_path)

        _invalidate_retriever_runtime()

        logger.info("已清空所有索引")
        return True

    except Exception as e:
        logger.error(f"清空索引失败: {e}")
        return False