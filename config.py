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

    # ReRanker 配置 ⭐ NEW
    reranker_enabled: bool = True  # 是否启用 CrossEncoder 重排序
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # CrossEncoder 模型
    reranker_top_k: int = 5  # ReRanker 保留结果数

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
