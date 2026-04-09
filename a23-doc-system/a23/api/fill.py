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
from main import AppError

router = APIRouter(tags=["表格回填"])


# ── POST /fill ────────────────────────────────────────────────
@router.post("/fill")
async def fill_table(body: dict, db: Session = Depends(get_db)):
    """
    表格回填接口
    请求体: FillRequest JSON（见规范文档 4.4）
    """
    template_file_id = body.get("template_file_id")
    answers = body.get("answers", [])

    if not template_file_id:
        raise AppError(400, "INVALID_REQUEST", "缺少 template_file_id 字段")
    if not answers:
        raise AppError(400, "INVALID_REQUEST", "answers 不能为空")

    # 校验模板文件存在
    template = db.query(FileRecord).filter_by(file_id=template_file_id).first()
    if not template:
        raise AppError(404, "FILE_NOT_FOUND", f"模板文件 {template_file_id} 不存在")

    # 生成输出文件路径
    output_id = str(uuid.uuid4())
    os.makedirs(settings.output_dir, exist_ok=True)
    ext = template.file_type
    output_path = os.path.join(settings.output_dir, f"{output_id}.{ext}")

    # ── 调用成员4的模块 ──────────────────────────────────────
    from modules.filler.table_filler import fill_table as do_fill
    success = do_fill(
        template_path=template.file_path,
        fill_request=body,
        output_path=output_path,
    )
    # ────────────────────────────────────────────────────────

    if not success:
        raise AppError(422, "FILL_FAILED", "表格回填失败，请检查模板格式和占位符")

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

    return FileResponse(
        path=record.output_path,
        filename=os.path.basename(record.output_path),
    )
