"""
文档智能操作交互接口 - yzmlhh
提供自然语言驱动的文档编辑、排版、格式调整、内容提取等操作接口
"""
import os
import uuid
import shutil
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from config import settings
from db.database import get_db
from db.models import FileRecord
from errors import AppError
from modules.document_ops import (
    execute_natural_command,
    parse_operation,
    OperationExecutor,
    WordDocumentOperations,
    ExcelDocumentOperations,
    FormatConverter,
    DocumentMerger,
    DocumentSplitter,
)

router = APIRouter(prefix="/document", tags=["文档智能操作"])


# ─────────────────────────────────────────────────────────────────────────────
# 请求/响应模型
# ─────────────────────────────────────────────────────────────────────────────

class OperationRequest(BaseModel):
    """文档操作请求"""
    file_id: str = Field(..., description="文件ID")
    instruction: str = Field(..., description="自然语言操作指令")
    create_backup: bool = Field(True, description="是否创建备份")


class ContentExtractRequest(BaseModel):
    """内容提取请求"""
    file_id: str = Field(..., description="文件ID")
    extract_type: str = Field("all", description="提取类型: all/paragraphs/tables/headings")


class FormatConvertRequest(BaseModel):
    """格式转换请求"""
    source_file_id: str = Field(..., description="源文件ID")
    target_format: str = Field(..., description="目标格式: pdf/md/csv/xlsx")


class MergeRequest(BaseModel):
    """文档合并请求"""
    file_ids: List[str] = Field(..., description="要合并的文件ID列表")
    output_filename: str = Field(..., description="输出文件名")


class SplitRequest(BaseModel):
    """文档拆分请求"""
    file_id: str = Field(..., description="要拆分的文件ID")
    output_dir: str = Field(..., description="输出目录")


class BatchOperationRequest(BaseModel):
    """批量操作请求"""
    file_id: str = Field(..., description="文件ID")
    instructions: List[str] = Field(..., description="操作指令列表（按顺序执行）")


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _get_file_record(file_id: str, db: Session) -> FileRecord:
    """获取文件记录并校验"""
    record = db.query(FileRecord).filter_by(file_id=file_id).first()
    if not record:
        raise AppError(404, "FILE_NOT_FOUND", f"文件 {file_id} 不存在")
    if not os.path.exists(record.file_path):
        raise AppError(404, "FILE_NOT_FOUND", f"文件不存在: {record.file_path}")
    return record


def _create_backup(file_path: str) -> str:
    """创建文件备份"""
    backup_dir = os.path.join(settings.upload_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    filename = os.path.basename(file_path)
    backup_path = os.path.join(backup_dir, f"{uuid.uuid4()}_{filename}")
    shutil.copy2(file_path, backup_path)
    return backup_path


def _get_output_path(filename: str = None) -> str:
    """生成输出文件路径"""
    os.makedirs(settings.output_dir, exist_ok=True)
    if filename:
        return os.path.join(settings.output_dir, filename)
    return os.path.join(settings.output_dir, f"{uuid.uuid4()}")


# ─────────────────────────────────────────────────────────────────────────────
# 核心接口：自然语言文档操作
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/operate", summary="自然语言文档操作")
async def operate_document(body: OperationRequest, db: Session = Depends(get_db)):
    """
    使用自然语言指令操作文档
    
    支持的操作类型：
    - 编辑段落：将指定段落的内容修改为新内容
    - 格式调整：设置字体、字号、颜色、加粗、倾斜等
    - 添加内容：在指定位置添加新段落
    - 删除内容：删除指定段落
    - 内容提取：提取文档中的段落、表格、标题等
    - 生成摘要：使用AI生成文档摘要
    - 替换文本：批量替换文档中的指定文本
    
    示例指令：
    - "把第二段改成'这是新的内容'"
    - "将第三段加粗并设置为红色"
    - "在文档开头添加一段'这是新段落'"
    - "删除最后一段"
    - "提取所有表格内容"
    - "生成500字的摘要"
    - "把所有的'北京'替换成'上海'"
    """
    # 获取文件记录
    record = _get_file_record(body.file_id, db)
    
    # 创建备份
    backup_path = None
    if body.create_backup:
        backup_path = _create_backup(record.file_path)
    
    # 解析指令
    operation = parse_operation(body.instruction, record.file_type)
    
    if operation.operation_type == "unknown":
        return {
            "success": False,
            "message": "无法理解该操作指令，请尝试更清晰的描述",
            "instruction": body.instruction,
            "backup_path": backup_path
        }
    
    # 执行操作
    executor = OperationExecutor(record.file_path, record.file_type)
    try:
        result = executor.execute(operation)
        
        return {
            "success": result.get("success", False),
            "message": result.get("message", "操作完成"),
            "operation_type": operation.operation_type,
            "confidence": operation.confidence,
            "reasoning": operation.reasoning,
            "instruction": body.instruction,
            "result": result,
            "backup_path": backup_path
        }
    except Exception as e:
        raise AppError(500, "OPERATION_FAILED", f"操作执行失败: {str(e)}")
    finally:
        executor.close()


class PreviewRequest(BaseModel):
    """预览操作请求（不需要真实文件）"""
    instruction: str = Field(..., description="自然语言操作指令")
    file_type: Optional[str] = Field("docx", description="文件类型: docx/xlsx")


@router.post("/preview", summary="预览操作结果")
async def preview_operation(body: PreviewRequest, db: Session = Depends(get_db)):
    """
    预览操作结果（不实际修改文件）

    返回解析后的操作类型和参数，用于确认操作
    注意：此接口不需要真实文件ID，仅用于解析指令

    示例请求：
    {
        "instruction": "把第二段改成'新内容'",
        "file_type": "docx"
    }
    """
    # 解析指令（不验证文件）
    operation = parse_operation(body.instruction, body.file_type)

    return {
        "instruction": body.instruction,
        "file_type": body.file_type,
        "parsed_operation": {
            "type": operation.operation_type,
            "confidence": operation.confidence,
            "parameters": operation.parameters,
            "reasoning": operation.reasoning
        },
        "supported": operation.operation_type != "unknown"
    }


# ─────────────────────────────────────────────────────────────────────────────
# 内容提取接口
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/extract", summary="提取文档内容")
async def extract_content(body: ContentExtractRequest, db: Session = Depends(get_db)):
    """
    提取文档内容
    
    extract_type 选项：
    - all: 提取全部内容（段落+表格+标题）
    - paragraphs: 仅提取段落
    - tables: 仅提取表格
    - headings: 仅提取标题
    """
    record = _get_file_record(body.file_id, db)
    
    try:
        if record.file_type == "docx":
            ops = WordDocumentOperations(record.file_path)
            try:
                result = ops.extract_content(body.extract_type)
            finally:
                ops.close()
        elif record.file_type in ("xlsx",):
            ops = ExcelDocumentOperations(record.file_path)
            try:
                result = ops.get_all_content()
            finally:
                ops.close()
        else:
            raise AppError(400, "UNSUPPORTED_TYPE", f"不支持的文件类型: {record.file_type}")
        
        return {
            "success": True,
            "file_id": body.file_id,
            "filename": record.filename,
            "file_type": record.file_type,
            "content": result.get("content", result),
            "extract_type": body.extract_type
        }
    except ImportError as e:
        raise AppError(500, "MODULE_ERROR", f"缺少必要的库: {str(e)}")
    except Exception as e:
        raise AppError(500, "EXTRACT_FAILED", f"提取失败: {str(e)}")


@router.post("/summarize", summary="生成文档摘要")
async def summarize_document(file_id: str, max_length: int = 500, 
                            db: Session = Depends(get_db)):
    """
    使用AI生成文档摘要
    
    Args:
        file_id: 文件ID
        max_length: 摘要最大字符数（默认500）
    """
    record = _get_file_record(file_id, db)
    
    if record.file_type != "docx":
        raise AppError(400, "UNSUPPORTED_TYPE", "目前仅支持 Word 文档的摘要生成")
    
    try:
        ops = WordDocumentOperations(record.file_path)
        try:
            result = ops.generate_summary(max_length)
        finally:
            ops.close()
        
        return {
            "success": result.get("success", False),
            "file_id": file_id,
            "filename": record.filename,
            "summary": result.get("summary", result.get("message", "")),
            "source_paragraphs": result.get("source_paragraphs", 0)
        }
    except Exception as e:
        raise AppError(500, "SUMMARIZE_FAILED", f"生成摘要失败: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# 格式转换接口
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/convert", summary="文档格式转换")
async def convert_format(body: FormatConvertRequest, db: Session = Depends(get_db)):
    """
    转换文档格式
    
    支持的转换：
    - docx → md (Markdown)
    - docx → pdf (需要 LibreOffice)
    - xlsx → csv
    - csv → xlsx
    """
    record = _get_file_record(body.source_file_id, db)
    
    output_filename = f"converted_{uuid.uuid4()}.{body.target_format}"
    output_path = _get_output_path(output_filename)
    
    try:
        ext = record.file_type.lower()
        target = body.target_format.lower()
        
        if ext == "docx" and target == "md":
            result = FormatConverter.docx_to_markdown(record.file_path, output_path)
        elif ext == "docx" and target == "pdf":
            result = FormatConverter.docx_to_pdf(record.file_path, output_path)
        elif ext in ("xlsx",) and target == "csv":
            result = FormatConverter.xlsx_to_csv(record.file_path, output_path)
        elif target == "csv" and ext == "csv":
            result = FormatConverter.csv_to_xlsx(record.file_path, output_path)
        else:
            raise AppError(400, "UNSUPPORTED_CONVERSION", 
                          f"不支持的转换: {ext} → {target}")
        
        if result.get("success"):
            return {
                "success": True,
                "source_file": record.filename,
                "target_format": body.target_format,
                "output_path": output_path,
                "download_url": f"/document/download_result?path={output_filename}"
            }
        else:
            return {
                "success": False,
                "message": result.get("message", "转换失败")
            }
    
    except AppError:
        raise
    except Exception as e:
        raise AppError(500, "CONVERT_FAILED", f"转换失败: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# 文档合并/拆分接口
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/merge", summary="合并多个文档")
async def merge_documents(body: MergeRequest, db: Session = Depends(get_db)):
    """
    将多个文档合并为一个
    
    注意：合并的文档格式必须相同
    """
    if len(body.file_ids) < 2:
        raise AppError(400, "INSUFFICIENT_FILES", "至少需要2个文件才能合并")
    
    # 获取所有文件记录
    file_paths = []
    file_type = None
    
    for file_id in body.file_ids:
        record = _get_file_record(file_id, db)
        file_paths.append(record.file_path)
        if file_type is None:
            file_type = record.file_type
        elif record.file_type != file_type:
            raise AppError(400, "TYPE_MISMATCH", "合并的文件必须格式相同")
    
    # 生成输出路径
    output_filename = f"{body.output_filename}.{file_type}"
    output_path = _get_output_path(output_filename)
    
    try:
        if file_type == "docx":
            result = DocumentMerger.merge_docx(file_paths, output_path)
        elif file_type in ("xlsx",):
            result = DocumentMerger.merge_xlsx(file_paths, output_path)
        elif file_type in ("txt", "md"):
            result = DocumentMerger.merge_markdown(file_paths, output_path)
        else:
            raise AppError(400, "UNSUPPORTED_TYPE", f"不支持合并格式: {file_type}")
        
        if result.get("success"):
            return {
                "success": True,
                "merged_count": result.get("merged_count", 0),
                "output_path": output_path,
                "download_url": f"/document/download_result?path={output_filename}"
            }
        else:
            return {
                "success": False,
                "message": result.get("message", "合并失败")
            }
    
    except AppError:
        raise
    except Exception as e:
        raise AppError(500, "MERGE_FAILED", f"合并失败: {str(e)}")


@router.post("/split", summary="拆分文档")
async def split_document(body: SplitRequest, db: Session = Depends(get_db)):
    """
    将一个大文档拆分为多个小文档
    
    拆分方式：
    - docx: 按段落数拆分（每50段一个文件）
    - xlsx: 按行数拆分（每1000行一个文件）
    """
    record = _get_file_record(body.file_id, db)
    
    # 生成输出目录
    output_dir = os.path.join(settings.output_dir, "splits", 
                             f"{uuid.uuid4()}_{record.filename}")
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        ext = record.file_type
        
        if ext == "docx":
            result = DocumentSplitter.split_docx_by_paragraphs(
                record.file_path, output_dir
            )
        elif ext in ("xlsx",):
            result = DocumentSplitter.split_xlsx_by_rows(
                record.file_path, output_dir
            )
        else:
            raise AppError(400, "UNSUPPORTED_TYPE", f"不支持拆分格式: {ext}")
        
        if result.get("success"):
            return {
                "success": True,
                "file_count": result.get("file_count", 0),
                "output_dir": output_dir,
                "output_files": [
                    f"/document/download_result?path=../splits/{os.path.basename(output_dir)}/{os.path.basename(f)}"
                    for f in result.get("output_files", [])
                ]
            }
        else:
            return {
                "success": False,
                "message": result.get("message", "拆分失败")
            }
    
    except AppError:
        raise
    except Exception as e:
        raise AppError(500, "SPLIT_FAILED", f"拆分失败: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# 批量操作接口
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/batch", summary="批量执行操作")
async def batch_operations(body: BatchOperationRequest, db: Session = Depends(get_db)):
    """
    批量执行多个操作指令
    
    指令按顺序执行，遇到失败会停止
    """
    record = _get_file_record(body.file_id, db)
    
    # 创建备份
    backup_path = _create_backup(record.file_path)
    
    results = []
    
    for i, instruction in enumerate(body.instructions):
        operation = parse_operation(instruction, record.file_type)
        
        if operation.operation_type == "unknown":
            return {
                "success": False,
                "message": f"第 {i+1} 条指令无法识别: {instruction}",
                "completed_count": i,
                "results": results,
                "backup_path": backup_path
            }
        
        executor = OperationExecutor(record.file_path, record.file_type)
        try:
            result = executor.execute(operation)
            results.append({
                "index": i + 1,
                "instruction": instruction,
                "operation_type": operation.operation_type,
                "result": result
            })
            
            if not result.get("success", False):
                return {
                    "success": False,
                    "message": f"第 {i+1} 条指令执行失败: {result.get('message')}",
                    "completed_count": i,
                    "results": results,
                    "backup_path": backup_path
                }
        finally:
            executor.close()
    
    return {
        "success": True,
        "message": f"成功执行 {len(results)} 条指令",
        "completed_count": len(results),
        "results": results,
        "backup_path": backup_path
    }


# ─────────────────────────────────────────────────────────────────────────────
# 文件下载接口
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/download_result")
async def download_result(path: str, db: Session = Depends(get_db)):
    """
    下载操作结果文件
    """
    # 安全检查：只允许下载 output_dir 下的文件
    safe_path = os.path.normpath(os.path.join(settings.output_dir, path))
    
    if not safe_path.startswith(os.path.abspath(settings.output_dir)):
        raise AppError(400, "INVALID_PATH", "无效的路径")
    
    if not os.path.exists(safe_path):
        raise AppError(404, "FILE_NOT_FOUND", "文件不存在")
    
    return FileResponse(
        path=safe_path,
        filename=os.path.basename(safe_path)
    )


# ─────────────────────────────────────────────────────────────────────────────
# 操作历史记录
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/supported_operations/{file_type}", summary="查询支持的操作")
async def get_supported_operations(file_type: str):
    """
    获取指定文件类型支持的操作列表
    """
    docx_ops = [
        {"type": "edit_paragraph", "name": "编辑段落", "description": "修改指定段落的内容"},
        {"type": "format_paragraph", "name": "格式调整", "description": "设置字体、颜色、加粗等"},
        {"type": "add_paragraph", "name": "添加段落", "description": "在指定位置添加新段落"},
        {"type": "delete_paragraph", "name": "删除段落", "description": "删除指定段落"},
        {"type": "extract_content", "name": "内容提取", "description": "提取段落、表格、标题等"},
        {"type": "generate_summary", "name": "生成摘要", "description": "AI生成文档摘要"},
        {"type": "replace_text", "name": "文本替换", "description": "批量替换文档中的文本"},
    ]
    
    xlsx_ops = [
        {"type": "edit_cell", "name": "编辑单元格", "description": "修改指定单元格的值"},
        {"type": "format_cell", "name": "格式化单元格", "description": "设置单元格样式"},
        {"type": "add_row", "name": "添加行", "description": "在指定位置添加新行"},
        {"type": "add_column", "name": "添加列", "description": "在指定位置添加新列"},
        {"type": "extract_table", "name": "提取表格", "description": "提取表格数据"},
        {"type": "calculate", "name": "数据计算", "description": "执行公式计算"},
    ]
    
    operations = {
        "docx": docx_ops,
        "xlsx": xlsx_ops,
    }
    
    return {
        "file_type": file_type,
        "operations": operations.get(file_type, []),
        "format_conversions": [
            {"from": "docx", "to": "md"},
            {"from": "docx", "to": "pdf"},
            {"from": "xlsx", "to": "csv"},
            {"from": "csv", "to": "xlsx"},
        ]
    }
