"""
表格回填与下载接口 - 负责人: 成员1（路由层）
回填逻辑由成员4实现: modules/filler/table_filler.py
"""
import uuid
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from db.models import FileRecord, OutputRecord
from errors import AppError

router = APIRouter(tags=["表格回填"])


# ── POST /fill ────────────────────────────────────────────────
@router.post("/fill")
async def fill_table(body: dict, db: Session = Depends(get_db)):
    """
    表格回填接口，支持两种模式：
    - 智能回填（推荐）：传 source_file_ids，系统自动识别模板表头，从数据源提取数据填充
    - 手动回填：传 answers 列表（field_name + value），替换模板中的 {{占位符}}
    """
    template_file_id = body.get("template_file_id")
    source_file_ids = body.get("source_file_ids", [])
    answers = body.get("answers", [])
    max_rows = body.get("max_rows", 5)

    if not template_file_id:
        raise AppError(400, "INVALID_REQUEST", "缺少 template_file_id 字段")
    if not source_file_ids and not answers:
        raise AppError(400, "INVALID_REQUEST", "source_file_ids 和 answers 不能同时为空")

    # 校验模板文件存在
    template = db.query(FileRecord).filter_by(file_id=template_file_id).first()
    if not template:
        raise AppError(404, "FILE_NOT_FOUND", f"模板文件 {template_file_id} 不存在")

    # 校验数据源文件存在且已索引，同时收集文件路径
    source_file_paths = []
    for fid in source_file_ids:
        src = db.query(FileRecord).filter_by(file_id=fid).first()
        if not src:
            raise AppError(404, "FILE_NOT_FOUND", f"数据源文件 {fid} 不存在")
        if src.status != "indexed":
            raise AppError(409, "FILE_NOT_INDEXED", f"数据源文件 {fid} 尚未完成索引，请先解析")
        source_file_paths.append(src.file_path)

    # 生成输出文件路径
    output_id = str(uuid.uuid4())
    os.makedirs(settings.output_dir, exist_ok=True)
    ext = template.file_type
    output_path = os.path.join(settings.output_dir, f"{output_id}.{ext}")

    # ── 选择回填模式 ─────────────────────────────────────────
    if source_file_ids:
        # 智能回填：直接读源文件，让 LLM 自动识别并提取数据
        from modules.filler.intelligent_filler import extract_and_fill
        success = extract_and_fill(
            template_path=template.file_path,
            source_file_paths=source_file_paths,
            output_path=output_path,
            max_rows=max_rows,
        )
    else:
        # 手动回填：用 answers 列表替换占位符
        from modules.filler.table_filler import fill_table as do_fill
        success = do_fill(
            template_path=template.file_path,
            fill_request=body,
            output_path=output_path,
        )
    # ────────────────────────────────────────────────────────

    if not success:
        raise AppError(422, "FILL_FAILED", "表格回填失败，请检查模板格式或数据源")

    # 写入输出记录
    now = datetime.now(timezone.utc).isoformat()
    record = OutputRecord(
        output_id=output_id,
        template_file_id=template_file_id,
        output_path=output_path,
        created_at=now,
    )
    db.add(record)
    db.commit()

    return {
        "output_file_id": output_id,
        "download_url": f"/download/{output_id}",
    }


# ── GET /download/{file_id} ───────────────────────────────────
@router.get("/download/{file_id}")
async def download_file(file_id: str, db: Session = Depends(get_db)):
    """下载生成的文件"""
    record = db.query(OutputRecord).filter_by(output_id=file_id).first()
    if not record or not os.path.exists(record.output_path):
        raise AppError(404, "FILE_NOT_FOUND", f"文件 {file_id} 不存在")

    # 尝试用模板真实文件名拼接下载名
    template_rec = db.query(FileRecord).filter_by(file_id=record.template_file_id).first()
    if template_rec:
        base = os.path.splitext(template_rec.filename)[0]
        ext_part = os.path.splitext(record.output_path)[1]
        download_name = f"filled_{base}{ext_part}"
    else:
        download_name = os.path.basename(record.output_path)

    return FileResponse(
        path=record.output_path,
        filename=download_name,
    )
