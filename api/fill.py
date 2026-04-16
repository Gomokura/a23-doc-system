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


# ── POST /fill/preview ───────────────────────────────────────
@router.post("/fill/preview", summary="智能回填预览（只提取字段值，不生成文件）")
async def fill_preview(body: dict, db: Session = Depends(get_db)):
    """
    返回每个字段的提取结果供用户预览和编辑，不写文件。
    前端确认后再调用 POST /fill 生成文件。

    返回格式:
    {
      "fields": [
        {"field_name": "姓名", "values": ["张三", "李四"], "method": "llm"},
        ...
      ]
    }
    """
    template_file_id = body.get("template_file_id")
    source_file_ids  = body.get("source_file_ids", [])
    max_rows         = body.get("max_rows", 50)
    user_instruction = body.get("user_instruction", "")

    if not template_file_id:
        raise AppError(400, "INVALID_REQUEST", "缺少 template_file_id 字段")
    if not source_file_ids:
        raise AppError(400, "INVALID_REQUEST", "source_file_ids 不能为空")

    template = db.query(FileRecord).filter_by(file_id=template_file_id).first()
    if not template:
        raise AppError(404, "FILE_NOT_FOUND", f"模板文件 {template_file_id} 不存在")

    source_file_paths = []
    for fid in source_file_ids:
        src = db.query(FileRecord).filter_by(file_id=fid).first()
        if not src:
            raise AppError(404, "FILE_NOT_FOUND", f"数据源文件 {fid} 不存在")
        if src.status != "indexed":
            raise AppError(409, "FILE_NOT_INDEXED", f"数据源文件 {fid} 尚未完成索引，请先解析")
        source_file_paths.append(src.file_path)

    from modules.filler.intelligent_filler import preview_fill
    result = preview_fill(
        template_path=template.file_path,
        source_file_paths=source_file_paths,
        max_rows=max_rows,
        user_instruction=user_instruction,
    )

    if result is None:
        raise AppError(422, "PREVIEW_FAILED", "字段提取失败，请检查模板格式或数据源")

    return {"fields": result}


# ── POST /fill ────────────────────────────────────────────────
@router.post("/fill", summary="表格回填（生成文件）")
async def fill_table(body: dict, db: Session = Depends(get_db)):
    """
    表格回填接口，支持三种模式：
    1. 预览确认后回填：传 answers（含 values 列表）
    2. 全自动智能回填：传 source_file_ids
    3. 占位符手动回填：传 answers（含单 value 字符串）
    """
    template_file_id = body.get("template_file_id")
    source_file_ids  = body.get("source_file_ids", [])
    answers          = body.get("answers", [])
    max_rows         = body.get("max_rows", 50)
    fill_rows        = body.get("fill_rows", 0)
    fill_rows        = fill_rows if fill_rows and fill_rows > 0 else 99999  # 0=不限制
    user_instruction = body.get("user_instruction", "")

    if not template_file_id:
        raise AppError(400, "INVALID_REQUEST", "缺少 template_file_id 字段")
    if not source_file_ids and not answers:
        raise AppError(400, "INVALID_REQUEST", "source_file_ids 和 answers 不能同时为空")

    template = db.query(FileRecord).filter_by(file_id=template_file_id).first()
    if not template:
        raise AppError(404, "FILE_NOT_FOUND", f"模板文件 {template_file_id} 不存在")

    source_file_paths = []
    for fid in source_file_ids:
        src = db.query(FileRecord).filter_by(file_id=fid).first()
        if not src:
            raise AppError(404, "FILE_NOT_FOUND", f"数据源文件 {fid} 不存在")
        if src.status != "indexed":
            raise AppError(409, "FILE_NOT_INDEXED", f"数据源文件 {fid} 尚未完成索引，请先解析")
        source_file_paths.append(src.file_path)

    output_id = str(uuid.uuid4())
    os.makedirs(settings.output_dir, exist_ok=True)
    ext = template.file_type
    output_path = os.path.join(settings.output_dir, f"{output_id}.{ext}")

    # ── 选择回填模式 ─────────────────────────────────────────
    if answers:
        # 模式1/3：用户已有 answers（预览确认后，或手动占位符模式）
        # 判断是多值模式还是单值占位符模式
        has_values_list = any("values" in a for a in answers)
        if has_values_list:
            # 预览确认后的多行回填
            normalized = []
            for a in answers:
                fn = a.get("field_name", "")
                if not fn:
                    continue
                if "values" in a:
                    vals = a["values"] if isinstance(a["values"], list) else [str(a["values"])]
                else:
                    vals = [str(a.get("value", ""))]
                normalized.append({"field_name": fn, "values": vals})

            from modules.filler.intelligent_filler import write_answers_to_template
            success = write_answers_to_template(
                template_path=template.file_path,
                answers=normalized,
                output_path=output_path,
                source_file_paths=source_file_paths,
                user_instruction=user_instruction,
            )
        else:
            # 单值占位符替换
            from modules.filler.table_filler import fill_table as do_fill
            success = do_fill(
                template_path=template.file_path,
                fill_request=body,
                output_path=output_path,
            )

    elif source_file_ids:
        # 模式2：全自动智能回填
        from modules.filler.intelligent_filler import extract_and_fill
        success = extract_and_fill(
            template_path=template.file_path,
            source_file_paths=source_file_paths,
            output_path=output_path,
            max_rows=fill_rows,
            user_instruction=user_instruction,
        )
    else:
        raise AppError(400, "INVALID_REQUEST", "参数错误")

    if not success:
        raise AppError(422, "FILL_FAILED", "表格回填失败，请检查模板格式或数据源")

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
@router.get("/download/{file_id}", summary="下载回填生成的文件")
async def download_file(file_id: str, db: Session = Depends(get_db)):
    """下载生成的文件，强制触发浏览器下载（attachment 模式，不在线预览）"""
    record = db.query(OutputRecord).filter_by(output_id=file_id).first()
    if not record or not os.path.exists(record.output_path):
        raise AppError(404, "FILE_NOT_FOUND", f"文件 {file_id} 不存在")

    template_rec = db.query(FileRecord).filter_by(file_id=record.template_file_id).first()
    if template_rec:
        base = os.path.splitext(template_rec.filename)[0]
        ext_part = os.path.splitext(record.output_path)[1]
        download_name = f"filled_{base}{ext_part}"
    else:
        download_name = os.path.basename(record.output_path)

    ext = os.path.splitext(record.output_path)[1].lower()
    mime_map = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf":  "application/pdf",
    }
    media_type = mime_map.get(ext, "application/octet-stream")

    return FileResponse(
        path=record.output_path,
        filename=download_name,
        media_type=media_type,
        content_disposition_type="attachment",
    )
