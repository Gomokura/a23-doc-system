"""
数据库初始化与 Session 管理 - 负责人: 成员1
其他成员使用: from db.database import get_db, SessionLocal
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from db.models import Base
from config import settings

# ── 连接池配置 ─────────────────────────────────────────────────
# SQLite 使用 StaticPool（单文件，多线程共享同一连接）
# pool_pre_ping: 每次取连接前发 SELECT 1 探活，防止连接失效
engine = create_engine(
    f"sqlite:///{settings.sqlite_path}",
    connect_args={"check_same_thread": False},  # SQLite 多线程支持
    pool_pre_ping=True,                          # 连接探活
    pool_size=5,                                 # 连接池大小（SQLite 实际为线程锁）
    max_overflow=10,                             # 超出 pool_size 后最多额外创建数
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """启动时自动建表，已存在则跳过"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖注入：获取数据库 Session，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health() -> dict:
    """
    数据库健康检查，供 /health 接口调用。
    返回 {"ok": True/False, "detail": "..."}
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "detail": "connected"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}
