"""
数据库 ORM 模型 - 负责人: 成员1
其他成员直接 import 使用，禁止直接写 SQL 字符串
"""
from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class FileRecord(Base):
    """文件元数据表"""
    __tablename__ = "files"

    file_id     = Column(String, primary_key=True)   # UUID，上传时生成
    filename    = Column(String, nullable=False)       # 原始文件名
    file_type   = Column(String, nullable=False)       # pdf/docx/xlsx/txt/md
    file_path   = Column(String, nullable=False)       # uploads/ 本地路径
    status      = Column(String, default="uploaded")   # uploaded/parsed/indexed
    chunk_count = Column(Integer, default=0)           # 解析后写入
    uploaded_at = Column(String, nullable=False)       # ISO8601 时间戳
    parsed_at   = Column(String, nullable=True)        # 解析完成时间
    indexed_at  = Column(String, nullable=True)        # 索引完成时间


class TaskRecord(Base):
    """异步任务状态表"""
    __tablename__ = "tasks"

    task_id    = Column(String, primary_key=True)      # UUID
    file_id    = Column(String, nullable=False)         # 关联 files 表
    task_type  = Column(String, nullable=False)         # parse / index
    status     = Column(String, default="pending")      # pending/processing/done/failed
    progress   = Column(Integer, default=0)             # 0-100
    error_msg  = Column(String, nullable=True)          # 失败原因
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)


class OutputRecord(Base):
    """填表输出文件表"""
    __tablename__ = "outputs"

    output_id        = Column(String, primary_key=True)  # UUID
    template_file_id = Column(String, nullable=False)     # 使用的模板 file_id
    output_path      = Column(String, nullable=False)     # outputs/ 路径
    created_at       = Column(String, nullable=False)
