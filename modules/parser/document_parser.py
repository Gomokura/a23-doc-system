"""
文档解析与信息抽取模块 - 负责人: 成员2
函数签名已锁定，不得更改参数名和返回类型
"""
from loguru import logger


def parse_document(file_path: str, file_id: str) -> dict:
    """
    解析文档，返回 ParsedDocument dict（严格遵守规范文档 4.1 Schema）

    Args:
        file_path: 文件本地路径（uploads/ 目录下）
        file_id:   文件唯一ID（由上传接口生成）

    Returns:
        ParsedDocument dict

    Raises:
        ValueError:   不支持的文件格式
        RuntimeError: 解析失败（文件损坏/加密等）
    """
    logger.info(f"开始解析文件: {file_path}, file_id: {file_id}")

    # ═══════════════════════════════════════════════════════
    # TODO: 成员2在此实现解析逻辑
    # 参考技术方案：
    #   PDF   → pdfplumber 或 unstructured
    #   DOCX  → python-docx
    #   XLSX  → openpyxl
    #   TXT   → 直接读取
    #   MD    → 直接读取
    # ═══════════════════════════════════════════════════════

    # 目前返回 Mock 数据，成员2完成后替换此 return
    from tests.mock_data import MOCK_PARSED_DOC
    import copy
    mock = copy.deepcopy(MOCK_PARSED_DOC)
    mock["file_id"] = file_id
    mock["filename"] = file_path.split("/")[-1]
    logger.warning(f"⚠️  parse_document 仍在使用 Mock 数据，成员2请尽快实现")
    return mock
