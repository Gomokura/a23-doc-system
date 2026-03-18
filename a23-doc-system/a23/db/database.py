"""
数据库初始化与 Session 管理 - 负责人: 成员1
其他成员使用: from db.database import get_db
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base
from config import settings

engine = create_engine(
    f"sqlite:///{settings.sqlite_path}",
    connect_args={"check_same_thread": False},  # SQLite 多线程支持
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """启动时自动建表，已存在则跳过"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖注入：获取数据库 Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
