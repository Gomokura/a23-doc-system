"""
表格回填模块 - 负责人: 成员4
函数签名已锁定，不得更改
"""
from loguru import logger


def fill_table(template_path: str, fill_request: dict, output_path: str) -> bool:
    """
    根据 FillRequest 将字段填入模板文件

    Args:
        template_path: 模板文件本地路径
        fill_request:  FillRequest dict（规范文档 4.4）
        output_path:   输出文件路径

    Returns:
        True 成功 / False 失败

    支持格式:
        .docx → 占位符格式 {{字段名}}
        .xlsx → 单元格内容为 {{字段名}}
    """
    logger.info(f"开始填表: template={template_path}, output={output_path}")

    # ═══════════════════════════════════════════════════════
    # TODO: 成员4在此实现填表逻辑
    # 参考技术方案：
    #   DOCX → python-docx，遍历段落和表格，替换 {{字段名}}
    #   XLSX → openpyxl，遍历所有单元格，替换 {{字段名}}
    # ═══════════════════════════════════════════════════════

    logger.warning(f"⚠️  fill_table 是空实现，成员4请尽快实现")

    # 临时：直接复制模板文件作为输出（让流程可以跑通）
    import shutil
    try:
        shutil.copy(template_path, output_path)
        return True
    except Exception as e:
        logger.error(f"fill_table 失败: {e}")
        return False
