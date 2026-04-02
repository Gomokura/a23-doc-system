"""
全局配置 - 负责人: 成员1
所有配置从 .env 文件读取，禁止在代码中硬编码 API Key
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM 配置（使用 Ollama 本地部署，完全免费）
    # 首次使用需先安装 Ollama：https://ollama.com/download
    # 然后在终端运行：ollama pull qwen3:8b
    llm_api_key:  str = "ollama"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model:    str = "qwen3:8b"

    # 👇 -------- 新增：VLM 视觉大模型配置 (专供 PDF 图片解析) -------- 👇
    vlm_api_key: str = "填入你的云端视觉大模型API_KEY"  # 建议用硅基流动等免费/廉价的云端 API
    vlm_base_url: str = "https://api.siliconflow.cn/v1"
    vlm_model: str = "Qwen/Qwen2-VL-72B-Instruct"  # 强大的视觉模型
    # 👆 ----------------------------------------------------------- 👆

    # 嵌入模型（本地运行，Kaggle 可用）
    embed_model: str = "BAAI/bge-small-zh-v1.5"

    # 数据库路径
    chroma_path: str = "./db/chroma"
    sqlite_path: str = "./db/app.db"

    # 文件目录
    upload_dir: str = "./uploads"
    output_dir: str = "./outputs"

    # 文件限制
    max_file_size_mb: int = 50
    allowed_extensions: list = ["pdf", "docx", "xlsx", "txt", "md"]

    # 检索配置
    vector_weight: float = 0.6
    bm25_weight:   float = 0.4
    top_k:         int   = 5

    # ChromaDB 高级配置 ⭐ NEW
    chroma_distance_metric: str = "cosine"  # 距离度量: cosine(余弦) | l2(欧氏) | ip(内积)
    chroma_batch_size: int = 128  # ChromaDB 批量处理大小
    chroma_n_results: int = 10  # 默认检索数量（会乘以 top_k）

    # ReRanker 配置
    reranker_enabled: bool = True  # 是否启用 CrossEncoder 重排序
    reranker_model: str = "Qwen/Qwen3-Reranker-0.6B"  # 中文 CrossEncoder 模型（支持中英文 rerank）
    reranker_top_k: int = 5  # ReRanker 保留结果数

    # BM25S 配置（替代 rank_bm25，冷启动快 5-10 倍，内置持久化）
    # GitHub: https://github.com/xhluca/bm25s | 论文: https://arxiv.org/abs/2407.03618
    bm25s_method: str = "robertson"  # BM25 变体: robertson | atire | bm25l | bm25+ | lucene
    bm25s_k1: float = 1.5
    bm25s_b: float = 0.75

    # MMR Diversity 重排序配置（RRF 之后做，去重+覆盖更多段落）
    # 论文: Carbonell & Goldstein, SIGIR 1998
    mmr_enabled: bool = True  # 是否启用 MMR Diversity
    mmr_lambda: float = 0.7  # λ ∈ [0,1]，1=只看相关性，0=只看多样性，建议 0.6-0.7

    # 混合检索配置
    fusion_method: str = "rrf"  # 融合方法: rrf(倒数排名融合) | linear(线性加权)
    rrf_k: int = 60  # RRF 超参数，默认 60
    query_token_threshold: int = 5  # 查询分词后词数阈值，超过则判定为长查询
    weight_vector_short: float = 0.4  # 短查询时向量检索权重
    weight_bm25_short: float = 0.6  # 短查询时 BM25 权重
    weight_vector_long: float = 0.7  # 长查询时向量检索权重
    weight_bm25_long: float = 0.3  # 长查询时 BM25 权重

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_ttl: int = 3600

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
