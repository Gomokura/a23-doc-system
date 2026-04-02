import copy
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# 让 tests/ 可以从项目根导入 modules/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def retriever_env(tmp_path, monkeypatch):
    """
    为成员3测试准备隔离环境：
    - 独立 chroma 目录
    - 关闭真实 Redis
    - 关闭真实 reranker
    - mock 掉 embedding / Chroma / OpenAI
    """
    from tests.mock_data import MOCK_PARSED_DOC

    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir(parents=True, exist_ok=True)

    # 配置隔离路径
    import config
    monkeypatch.setattr(config.settings, "chroma_path", str(chroma_dir), raising=False)
    monkeypatch.setattr(config.settings, "top_k", 5, raising=False)
    monkeypatch.setattr(config.settings, "reranker_enabled", False, raising=False)
    monkeypatch.setattr(config.settings, "reranker_top_k", 5, raising=False)
    monkeypatch.setattr(config.settings, "llm_api_key", "test-key", raising=False)
    monkeypatch.setattr(config.settings, "llm_base_url", "https://mock.local/v1", raising=False)
    monkeypatch.setattr(config.settings, "llm_model", "mock-model", raising=False)
    monkeypatch.setattr(config.settings, "embed_model", "mock-embed-model", raising=False)
    monkeypatch.setattr(config.settings, "chroma_distance_metric", "cosine", raising=False)

    # 伪造 embedding 模型（与 SentenceTransformer 一致：单条 query 返回 ndarray，可 .tolist()）
    class FakeEmbedModel:
        def encode(self, texts, convert_to_numpy=False):
            import numpy as np

            if isinstance(texts, str):
                vec = self._encode_one(texts)
                return np.array(vec, dtype=float)
            vectors = [self._encode_one(t) for t in texts]
            if convert_to_numpy:
                return np.array(vectors, dtype=float)
            return vectors

        @staticmethod
        def _encode_one(text):
            text = text or ""
            # 三维简单特征，保证不同文本向量不同即可
            return [
                float(len(text)),
                float(text.count("合同") + text.count("金额") + text.count("付款")),
                float(text.count("甲方") + text.count("乙方") + text.count("有效期")),
            ]

    # 伪造 Chroma collection
    class FakeCollection:
        def __init__(self):
            self.rows = []

        def add(self, ids, embeddings, documents, metadatas):
            for i in range(len(ids)):
                self.rows.append({
                    "id": ids[i],
                    "embedding": embeddings[i],
                    "document": documents[i],
                    "metadata": metadatas[i],
                })

        def query(self, query_embeddings, n_results=10, where=None):
            query_vec = query_embeddings[0]
            rows = self.rows

            if where and "file_id" in where and "$in" in where["file_id"]:
                file_ids = set(where["file_id"]["$in"])
                rows = [r for r in rows if r["metadata"].get("file_id") in file_ids]

            scored = []
            for row in rows:
                emb = row["embedding"]
                # 简单 L1 距离，越小越相关
                dist = sum(abs(float(a) - float(b)) for a, b in zip(query_vec, emb))
                scored.append((dist, row))

            scored.sort(key=lambda x: x[0])
            top = scored[:n_results]

            return {
                "ids": [[item[1]["id"] for item in top]],
                "documents": [[item[1]["document"] for item in top]],
                "metadatas": [[item[1]["metadata"] for item in top]],
                "distances": [[item[0] for item in top]],
            }

        def delete(self, where=None):
            if not where:
                self.rows = []
                return

            if "file_id" in where:
                target = where["file_id"]
                self.rows = [r for r in self.rows if r["metadata"].get("file_id") != target]

    class FakeClient:
        def __init__(self):
            self.collection = FakeCollection()

        def get_or_create_collection(self, name, metadata=None):
            return self.collection

        def get_collection(self, name):
            return self.collection

    # Redis mock
    cache_store = {}

    def fake_get_cached_result(key):
        return copy.deepcopy(cache_store.get(key))

    def fake_set_cached_result(key, result, ttl=None):
        cache_store[key] = copy.deepcopy(result)
        return True

    def fake_invalidate_cache(pattern="*"):
        n = len(cache_store)
        cache_store.clear()
        return n

    # OpenAI mock
    class FakeCompletions:
        @staticmethod
        def create(model, messages, temperature=0.3, max_tokens=500, stream=False):
            prompt = messages[0]["content"]
            if stream:
                # 流式测试里没直接调用到这里，但保留兼容
                parts = ["回答: 模拟", "答案", "\n来源: [文档1]"]
                for p in parts:
                    yield SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content=p))]
                    )
            else:
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content="回答: 模拟答案\n来源: [文档1]"
                            )
                        )
                    ]
                )

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key=None, base_url=None):
            self.chat = FakeChat()

    # 导入模块并打补丁
    import modules.retriever.indexer as indexer
    import modules.retriever.hybrid_retriever as hr

    # 重置模块级状态
    indexer._embed_model = None
    indexer._chroma_client = FakeClient()
    indexer._bm25_corpus = []
    indexer._bm25_doc_map = {}
    indexer._bm25_records = []
    indexer._indexed_files = set()

    hr._BM25_CACHE_VALID = False
    hr._BM25_INDEX = None
    hr._BM25_CACHE_KEY = None
    hr._BM25_RECORDS = []
    hr._TOKENIZED_CORPUS = []
    hr._reranker_model = None

    monkeypatch.setattr(indexer, "_get_embed_model", lambda: FakeEmbedModel())
    monkeypatch.setattr(indexer, "_get_chroma_client", lambda: indexer._chroma_client)

    monkeypatch.setattr(hr, "_get_embed_model", lambda: FakeEmbedModel())
    monkeypatch.setattr(hr, "OpenAI", FakeOpenAI)

    import modules.cache.redis_client as redis_client
    monkeypatch.setattr(redis_client, "get_cached_result", fake_get_cached_result)
    monkeypatch.setattr(redis_client, "set_cached_result", fake_set_cached_result)
    monkeypatch.setattr(redis_client, "invalidate_cache", fake_invalidate_cache)

    # 为 hybrid_retriever 内部的局部 import 生效
    monkeypatch.setattr("modules.cache.redis_client.get_cached_result", fake_get_cached_result)
    monkeypatch.setattr("modules.cache.redis_client.set_cached_result", fake_set_cached_result)
    monkeypatch.setattr("modules.cache.redis_client.invalidate_cache", fake_invalidate_cache)

    return {
        "indexer": indexer,
        "hr": hr,
        "mock_doc": copy.deepcopy(MOCK_PARSED_DOC),
        "cache_store": cache_store,
        "chroma_dir": chroma_dir,
    }


def test_build_index_success(retriever_env):
    indexer = retriever_env["indexer"]
    mock_doc = retriever_env["mock_doc"]

    ok = indexer.build_index(mock_doc, force_rebuild=True)
    assert ok is True

    indexed_files = indexer.get_indexed_files()
    assert mock_doc["file_id"] in indexed_files

    bm25_records = indexer.get_bm25_records()
    assert len(bm25_records) == len(mock_doc["chunks"])
    assert bm25_records[0]["chunk_id"] == mock_doc["chunks"][0]["chunk_id"]


def test_bm25_search_supports_file_filter(retriever_env):
    indexer = retriever_env["indexer"]
    hr = retriever_env["hr"]

    doc1 = retriever_env["mock_doc"]
    doc2 = copy.deepcopy(retriever_env["mock_doc"])
    doc2["file_id"] = "mock-file-002"
    doc2["filename"] = "另一份合同.pdf"
    for i, chunk in enumerate(doc2["chunks"]):
        chunk["chunk_id"] = f"mock-file-002_{i}"
        chunk["content"] = f"第二份文件：{chunk['content']}"

    assert indexer.build_index(doc1, force_rebuild=True) is True
    assert indexer.build_index(doc2, force_rebuild=True) is True

    scores_all, _ = hr._bm25_search("合同金额")
    scores_doc1, _ = hr._bm25_search("合同金额", file_ids=[doc1["file_id"]])
    scores_doc2, _ = hr._bm25_search("合同金额", file_ids=[doc2["file_id"]])

    assert len(scores_all) >= len(scores_doc1)
    assert all(k.startswith("mock-file-001_") for k in scores_doc1.keys())
    assert all(k.startswith("mock-file-002_") for k in scores_doc2.keys())


def test_hybrid_retrieve_can_merge_bm25_only_candidates(retriever_env, monkeypatch):
    """
    验证真正的并集融合：
    向量候选只返回 chunk0；
    BM25 给 chunk1 很高分；
    最终结果里应该能看到 chunk1 被补进来。
    """
    indexer = retriever_env["indexer"]
    hr = retriever_env["hr"]
    mock_doc = retriever_env["mock_doc"]

    assert indexer.build_index(mock_doc, force_rebuild=True) is True

    def fake_vector_search(query, query_embedding, file_ids):
        return [{
            "chunk_id": mock_doc["chunks"][0]["chunk_id"],
            "content": mock_doc["chunks"][0]["content"],
            "source_file": mock_doc["filename"],
            "page": 1,
            "distance": 0.1,
            "vector_score": 0.95,
        }]

    def fake_bm25_search(query, file_ids=None):
        return (
            {
                mock_doc["chunks"][0]["chunk_id"]: 1.0,
                mock_doc["chunks"][1]["chunk_id"]: 5.0,  # BM25-only 强相关
            },
            {
                mock_doc["chunks"][0]["chunk_id"]: {
                    "content": mock_doc["chunks"][0]["content"],
                    "file_id": mock_doc["file_id"],
                    "source_file": mock_doc["filename"],
                    "page": 1,
                },
                mock_doc["chunks"][1]["chunk_id"]: {
                    "content": mock_doc["chunks"][1]["content"],
                    "file_id": mock_doc["file_id"],
                    "source_file": mock_doc["filename"],
                    "page": 2,
                },
            }
        )

    monkeypatch.setattr(hr, "_vector_search", fake_vector_search)
    monkeypatch.setattr(hr, "_bm25_search", fake_bm25_search)
    monkeypatch.setattr(hr, "rerank_chunks", lambda q, chunks, top_k=None: chunks[: (top_k or 5)])

    top_chunks = hr._hybrid_retrieve("付款方式是什么", [mock_doc["file_id"]])
    chunk_ids = [c["chunk_id"] for c in top_chunks]

    assert mock_doc["chunks"][0]["chunk_id"] in chunk_ids
    assert mock_doc["chunks"][1]["chunk_id"] in chunk_ids


def test_retrieve_and_answer_returns_valid_schema(retriever_env, monkeypatch):
    hr = retriever_env["hr"]
    indexer = retriever_env["indexer"]
    mock_doc = retriever_env["mock_doc"]

    assert indexer.build_index(mock_doc, force_rebuild=True) is True

    # 为了让结果稳定，禁用 rerank 波动
    monkeypatch.setattr(hr, "rerank_chunks", lambda q, chunks, top_k=None: chunks[: (top_k or 5)])

    result = hr.retrieve_and_answer(
        query="合同金额是多少？",
        file_ids=[mock_doc["file_id"]],
        scenario="contract"
    )

    assert isinstance(result, dict)
    assert result["query"] == "合同金额是多少？"
    assert "answer" in result
    assert "sources" in result
    assert "confidence" in result
    assert "fusion" in result

    assert isinstance(result["sources"], list)
    assert len(result["sources"]) > 0

    first = result["sources"][0]
    assert {"chunk_id", "content", "source_file", "page"} <= set(first.keys())


def test_delete_index_invalidates_bm25_runtime_cache(retriever_env):
    indexer = retriever_env["indexer"]
    hr = retriever_env["hr"]
    mock_doc = retriever_env["mock_doc"]

    assert indexer.build_index(mock_doc, force_rebuild=True) is True

    # 先触发一次 BM25 运行时缓存
    scores_before, _ = hr._bm25_search("合同金额", file_ids=[mock_doc["file_id"]])
    assert len(scores_before) > 0
    assert hr._BM25_CACHE_VALID is True

    # 删除索引后，缓存应该被失效
    assert indexer.delete_index(mock_doc["file_id"]) is True
    assert hr._BM25_CACHE_VALID is False

    scores_after, _ = hr._bm25_search("合同金额", file_ids=[mock_doc["file_id"]])
    assert scores_after == {}


def test_clear_all_indexes_works(retriever_env):
    indexer = retriever_env["indexer"]
    mock_doc = retriever_env["mock_doc"]

    assert indexer.build_index(mock_doc, force_rebuild=True) is True
    assert len(indexer.get_bm25_records()) > 0

    assert indexer.clear_all_indexes() is True
    assert indexer.get_bm25_records() == []
    assert indexer.get_indexed_files() == []