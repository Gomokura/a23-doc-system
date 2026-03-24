"""
表格回填模块 - 负责人: 成员4
函数签名已锁定，不得更改
"""
import os

from docx import Document
from loguru import logger
from openpyxl import load_workbook


def fill_docx(template_path: str, answers: list, output_path: str) -> bool:
    """
    内部子函数：填充DOCX模板占位符
    :param template_path: 模板文件路径
    :param answers: 回填数据列表（fill_request['answers']）
    :param output_path: 输出文件路径
    :return: 填充成功返回True，失败返回False
    """
    try:
        doc = Document(template_path)
        # 构建字段名-值的映射表
        field_map = {a["field_name"]: a["value"] for a in answers}

        # 遍历文档段落替换占位符
        for para in doc.paragraphs:
            for key, val in field_map.items():
                placeholder = f"{{{{{key}}}}}"
                if placeholder in para.text:
                    for run in para.runs:
                        run.text = run.text.replace(placeholder, val)

        # 遍历文档表格替换占位符
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for key, val in field_map.items():
                        placeholder = f"{{{{{key}}}}}"
                        if placeholder in cell.text:
                            # 替换单元格文本，保留原有格式
                            cell_text = cell.text.replace(placeholder, val)
                            cell.paragraphs[0].runs[0].text = cell_text

        doc.save(output_path)
        logger.info(f"DOCX模板填充完成，输出文件：{output_path}")
        return True
    except Exception as e:
        logger.error(f"DOCX模板填充失败：{str(e)}")
        return False


def fill_xlsx(template_path: str, answers: list, output_path: str) -> bool:
    """
    内部子函数：填充XLSX模板占位符
    :param template_path: 模板文件路径
    :param answers: 回填数据列表（fill_request['answers']）
    :param output_path: 输出文件路径
    :return: 填充成功返回True，失败返回False
    """
    try:
        wb = load_workbook(template_path)
        # 构建字段名-值的映射表
        field_map = {a["field_name"]: a["value"] for a in answers}

        # 遍历所有工作表、行、单元格替换占位符
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        for key, val in field_map.items():
                            placeholder = f"{{{{{key}}}}}"
                            if placeholder in cell.value:
                                cell.value = cell.value.replace(placeholder, val)

        wb.save(output_path)
        logger.info(f"XLSX模板填充完成，输出文件：{output_path}")
        return True
    except Exception as e:
        logger.error(f"XLSX模板填充失败：{str(e)}")
        return False


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

    # 1. 基础参数校验
    if not os.path.exists(template_path):
        logger.error(f"模板文件不存在：{template_path}")
        return False
    if not fill_request or not isinstance(fill_request.get("answers"), list):
        logger.error("FillRequest格式错误，answers必须为非空列表")
        return False
    if not output_path:
        logger.error("输出文件路径不能为空")
        return False

    # 2. 提取回填数据
    answers = fill_request["answers"]

    # 3. 按文件类型执行填充逻辑
    file_suffix = template_path.rsplit(".", 1)[-1].lower()
    if file_suffix == "docx":
        fill_success = fill_docx(template_path, answers, output_path)
    elif file_suffix == "xlsx":
        fill_success = fill_xlsx(template_path, answers, output_path)
    else:
        logger.error(f"不支持的文件格式：{file_suffix}，仅支持 docx / xlsx")
        return False

    if fill_success:
        logger.info(f"填表完成: output={output_path}")
        return True
    logger.error(f"填表失败: template={template_path}")
    return False
