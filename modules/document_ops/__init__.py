"""
文档智能操作交互模块
基于自然语言处理技术，将用户指令解析为可执行的操作

主要功能：
1. 解析自然语言指令 → 操作类型 + 参数
2. 执行文档操作（编辑、格式、内容提取等）
3. 支持 Word、Excel 和 PDF 文档

使用示例：
    from modules.document_ops import execute_natural_command

    # 执行自然语言命令
    result = execute_natural_command(
        file_path="test.docx",
        instruction="把第二段加粗并改成红色"
    )
"""

# 导出主要接口
from .operation_parser import (
    OperationType,
    Operation,
    OperationParser,
    parse_operation,
    get_operation_parser,
)

from .docx_operations import (
    WordDocumentOperations,
    chinese_to_number,
    word_edit_paragraph,
    word_format_paragraph,
    word_extract_content,
    word_generate_summary,
    word_replace_text,
    word_format_heading,
    word_edit_heading,
    word_delete_heading,
)

from .xlsx_operations import (
    ExcelDocumentOperations,
    excel_get_content,
    excel_edit_cell,
    excel_add_row,
    excel_extract_table,
    excel_batch_fill,
)

from .pdf_operations import (
    PDFDocumentOperations,
    pdf_extract_text,
    pdf_extract_page,
)

from .common_operations import (
    OperationExecutor,
    FormatConverter,
    DocumentMerger,
    DocumentSplitter,
    execute_natural_command,
)

__all__ = [
    # 解析器
    'OperationType',
    'Operation',
    'OperationParser',
    'parse_operation',
    'get_operation_parser',
    # Word 操作
    'WordDocumentOperations',
    'chinese_to_number',
    'word_edit_paragraph',
    'word_format_paragraph',
    'word_extract_content',
    'word_generate_summary',
    'word_replace_text',
    'word_format_heading',
    'word_edit_heading',
    'word_delete_heading',
    # Excel 操作
    'ExcelDocumentOperations',
    'excel_get_content',
    'excel_edit_cell',
    'excel_add_row',
    'excel_extract_table',
    'excel_batch_fill',
    # PDF 操作
    'PDFDocumentOperations',
    'pdf_extract_text',
    'pdf_extract_page',
    # 通用操作
    'OperationExecutor',
    'FormatConverter',
    'DocumentMerger',
    'DocumentSplitter',
    'execute_natural_command',
]
