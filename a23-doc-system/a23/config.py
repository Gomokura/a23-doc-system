"""
全局配置 - 负责人: 成员1
所有配置从 .env 文件读取，禁止在代码中硬编码 API Key
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM 配置（使用 DeepSeek，兼容 OpenAI SDK）
    llm_api_key:  str = "sk-请填入你的DeepSeek-API-Key"
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model:    str = "deepseek-chat"

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

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
