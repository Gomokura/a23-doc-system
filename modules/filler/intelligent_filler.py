"""
智能填表模块 - 自动从数据源文档中提取信息并填写模板
支持：无占位符模板（通过 LLM 识别表头）和有占位符模板（{{字段名}}）
"""
import os
import json
import re

from loguru import logger
from openai import OpenAI
from config import settings


# ────────────────────────────────────────────────────────────
# 工具函数：提取模板表头/字段
# ────────────────────────────────────────────────────────────

def extract_template_fields(template_path: str) -> dict:
    """
    从模板文件中提取需要填写的字段。
    优先识别 {{占位符}}，若无占位符则用 LLM 分析表头。
    返回:
        {
            "fields": ["字段1", "字段2", ...],
            "method": "placeholder" | "llm",
        }
    """
    ext = os.path.splitext(template_path)[1].lower()
    placeholder_pattern = re.compile(r'\{\{(.+?)\}\}')
    found = set()

    if ext == '.docx':
        from docx import Document
        doc = Document(template_path)
        for para in doc.paragraphs:
            found.update(placeholder_pattern.findall(para.text))
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        found.update(placeholder_pattern.findall(para.text))

    elif ext == '.xlsx':
        from openpyxl import load_workbook
        wb = load_workbook(template_path, data_only=True)
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value and isinstance(cell.value, str):
                        found.update(placeholder_pattern.findall(cell.value))

    if found:
        logger.info(f"占位符检测：发现 {len(found)} 个占位符字段: {found}")
        return {"fields": list(found), "method": "placeholder"}

    # ── 无占位符：用 LLM 分析模板表头 ─────────────────────────
    logger.info("模板无占位符，启动 LLM 智能识别表头字段...")
    raw_text = _read_template_text(template_path, ext)
    if not raw_text.strip():
        return {"fields": [], "method": "llm"}

    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    prompt = f"""以下是一个待填写的表格/文档模板内容。请识别出其中所有需要填写数据的字段名称。
字段可能是表格列标题、表单标签、空白行前的描述文字等。

要求：
1. 只返回字段名称列表，不包含表头说明或注释行
2. 严格返回 JSON 格式：{{"fields": ["字段名1", "字段名2", ...]}}
3. 字段名保留原文，不要翻译或修改

模板内容：
{raw_text[:4000]}

请直接输出 JSON："""

    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        result = json.loads(resp.choices[0].message.content)
        fields = result.get("fields", [])
        logger.info(f"LLM 识别到 {len(fields)} 个字段: {fields}")
        return {"fields": fields, "method": "llm"}
    except Exception as e:
        logger.error(f"LLM 识别字段失败: {e}")
        return {"fields": [], "method": "llm"}


def _read_template_text(template_path: str, ext: str) -> str:
    """读取模板文件的纯文本内容"""
    try:
        if ext == '.docx':
            from docx import Document
            doc = Document(template_path)
            lines = []
            for para in doc.paragraphs:
                if para.text.strip():
                    lines.append(para.text.strip())
            for table in doc.tables:
                for row in table.rows:
                    row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_texts:
                        lines.append(" | ".join(row_texts))
            return "\n".join(lines)

        elif ext == '.xlsx':
            from openpyxl import load_workbook
            wb = load_workbook(template_path, data_only=True)
            lines = []
            for sheet in wb.worksheets:
                for row in sheet.iter_rows():
                    row_texts = [str(cell.value).strip() for cell in row
                                 if cell.value is not None and str(cell.value).strip()]
                    if row_texts:
                        lines.append(" | ".join(row_texts))
            return "\n".join(lines)
    except Exception as e:
        logger.error(f"读取模板文本失败: {e}")
    return ""


# ────────────────────────────────────────────────────────────
# 工具函数：从数据源文档读取文本
# ────────────────────────────────────────────────────────────

def _read_source_texts(source_file_paths: list) -> str:
    """
    读取所有数据源文件的文本内容，拼接为一个大字符串供 LLM 检索。
    每个文件前加文件名标记方便溯源。
    """
    all_texts = []
    for path in source_file_paths:
        ext = os.path.splitext(path)[1].lower()
        filename = os.path.basename(path)
        try:
            text = ""
            if ext in ('.txt', '.md'):
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()

            elif ext == '.docx':
                from docx import Document
                doc = Document(path)
                lines = []
                for para in doc.paragraphs:
                    if para.text.strip():
                        lines.append(para.text.strip())
                for table in doc.tables:
                    for row in table.rows:
                        row_texts = [cell.text.replace('\n', ' ').strip() for cell in row.cells]
                        lines.append(" | ".join(row_texts))
                text = "\n".join(lines)

            elif ext == '.xlsx':
                import pandas as pd
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    xls = pd.ExcelFile(path)
                    sheet_texts = []
                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name=sheet_name).fillna("")
                        # 保留完整表格，to_csv 比 to_string 更紧凑，节省 token
                        sheet_texts.append(f"[Sheet: {sheet_name}]\n" + df.to_csv(index=False))
                    text = "\n\n".join(sheet_texts)

            elif ext == '.pdf':
                try:
                    import pdfplumber
                    with pdfplumber.open(path) as pdf:
                        pages = [p.extract_text() or "" for p in pdf.pages]
                    text = "\n".join(pages)
                except Exception:
                    import fitz
                    doc = fitz.open(path)
                    text = "\n".join(page.get_text() for page in doc)
                    doc.close()

            if text.strip():
                all_texts.append(f"=== 文件：{filename} ===\n{text.strip()}")
                logger.info(f"已读取源文件: {filename}，字符数: {len(text)}")

        except Exception as e:
            logger.warning(f"读取源文件 {filename} 失败: {e}")

    return "\n\n".join(all_texts)


# ────────────────────────────────────────────────────────────
# 核心：LLM 提取字段值（返回列表，支持多行）
# ────────────────────────────────────────────────────────────

def _extract_values_by_llm(fields: list, source_text: str, max_rows: int = 5) -> list:
    """
    让 LLM 从源文档文本中提取各字段的值。
    每个字段的值统一用 JSON 数组返回，天然支持多行数据。

    返回格式:
        [{"field_name": "字段名", "values": ["值1", "值2", ...]}, ...]
    """
    if not fields or not source_text.strip():
        return []

    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    MAX_SOURCE = 12000
    if len(source_text) > MAX_SOURCE:
        logger.warning(f"源文本过长({len(source_text)})，截取前 {MAX_SOURCE} 字符")
        source_text = source_text[:MAX_SOURCE] + "\n...[内容过长已截断]..."

    fields_str = "\n".join(f"- {f}" for f in fields)

    prompt = f"""你是一个精准的信息提取助手。请从以下数据源文档中，提取每个字段对应的所有值。

字段列表：
{fields_str}

提取规则：
1. 严格基于文档内容提取，不要编造数据
2. 每个字段的值必须用 JSON 数组表示，即使只有一个值也用数组
3. 如果字段对应表格中的一列，提取该列所有行的值（最多 {max_rows} 行），每行一个元素
4. 如果字段在文档中找不到，返回空数组 []
5. 数组元素只包含纯值，不要加字段名前缀、编号或说明

严格返回如下 JSON 格式（不要有其他文字）：
{{
  "answers": [
    {{"field_name": "字段名1", "values": ["值1", "值2", "值3"]}},
    {{"field_name": "字段名2", "values": ["值A", "值B"]}}
  ]
}}

数据源文档内容：
{source_text}

请直接输出 JSON："""

    try:
        resp = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=4000,
        )
        raw = resp.choices[0].message.content
        result = json.loads(raw)
        answers = result.get("answers", [])

        # 兼容旧格式（value 字符串），统一转成 values 列表
        normalized = []
        for a in answers:
            field_name = a.get("field_name", "")
            if "values" in a:
                vals = a["values"]
                if not isinstance(vals, list):
                    vals = [str(vals)]
            elif "value" in a:
                # 旧格式：尝试按换行拆分
                raw_val = str(a["value"])
                vals = [v.strip() for v in raw_val.split("\n") if v.strip()]
                if not vals:
                    vals = [raw_val]
            else:
                vals = []
            # 过滤掉"未找到"类占位符
            vals = [v for v in vals if v not in ("(未找到)", "(提取失败)", "")]
            normalized.append({"field_name": field_name, "values": vals})

        logger.info(f"LLM 提取完成，共 {len(normalized)} 个字段")
        for a in normalized[:5]:
            logger.info(f"  {a['field_name']}: {len(a['values'])} 行 → {a['values'][:3]}")
        return normalized

    except Exception as e:
        logger.error(f"LLM 提取字段值失败: {e}")
        return [{"field_name": f, "values": []} for f in fields]


# ────────────────────────────────────────────────────────────
# 核心：写入填充值到模板文件
# ────────────────────────────────────────────────────────────

def _write_to_template(template_path: str, answers: list, output_path: str, method: str) -> bool:
    """
    将提取的字段值写入模板文件。
    - placeholder 模式：替换 {{字段名}}（answers 需转换为旧格式）
    - llm 模式：在对应表头列下方按行追加数据
    """
    ext = os.path.splitext(template_path)[1].lower()

    if method == "placeholder":
        # table_filler 用旧格式 {"answers": [{"field_name":..., "value":...}]}
        # 占位符场景每个字段只有一个值，取第一个
        legacy_answers = [
            {"field_name": a["field_name"], "value": a["values"][0] if a["values"] else ""}
            for a in answers
        ]
        from modules.filler.table_filler import fill_table
        return fill_table(template_path, {"answers": legacy_answers}, output_path)

    if ext == '.xlsx':
        return _write_xlsx_smart(template_path, answers, output_path)
    elif ext == '.docx':
        return _write_docx_smart(template_path, answers, output_path)
    else:
        import shutil
        shutil.copy(template_path, output_path)
        return True


def _write_xlsx_smart(template_path: str, answers: list, output_path: str) -> bool:
    """
    智能填写 Excel：
    - 找到表头行，按表头列名模糊匹配字段
    - 每个字段的 values 列表逐行写入表头行下方
    """
    from openpyxl import load_workbook
    try:
        wb = load_workbook(template_path)
        ws = wb.active

        # field_name -> [值列表]
        field_map = {a["field_name"]: a["values"] for a in answers}

        # ── 找表头行：第一个有内容的行 ──────────────────────────
        header_row_idx = None
        header_cells = {}  # col_idx -> 字段名
        for row_idx, row in enumerate(ws.iter_rows(), start=1):
            non_empty = [(cell.column, str(cell.value).strip()) for cell in row
                         if cell.value and str(cell.value).strip()]
            if non_empty:
                header_row_idx = row_idx
                for col_idx, col_name in non_empty:
                    header_cells[col_idx] = col_name
                break

        # 没有表头：直接追加 field + value
        if header_row_idx is None:
            for a in answers:
                for val in a["values"]:
                    ws.append([a["field_name"], val])
            wb.save(output_path)
            return True

        # ── 计算最多需要写几行 ────────────────────────────────
        max_data_rows = max(
            (len(vals) for vals in field_map.values() if vals),
            default=1
        )
        if max_data_rows == 0:
            logger.warning("所有字段均未提取到值，复制模板原文")
            import shutil
            shutil.copy(template_path, output_path)
            return True

        start_row = header_row_idx + 1

        # ── 逐行写入 ──────────────────────────────────────────
        for data_row_offset in range(max_data_rows):
            write_row = start_row + data_row_offset
            for col_idx, col_name in header_cells.items():
                matched_value = _fuzzy_match_field(col_name, field_map, data_row_offset)
                if matched_value is not None:
                    ws.cell(row=write_row, column=col_idx, value=matched_value)

        wb.save(output_path)
        logger.info(f"XLSX 智能填写完成: {output_path}，共写入 {max_data_rows} 行数据")
        return True

    except Exception as e:
        logger.error(f"XLSX 智能填写失败: {e}")
        import shutil
        shutil.copy(template_path, output_path)
        return False


def _write_docx_smart(template_path: str, answers: list, output_path: str) -> bool:
    """
    智能填写 Word：
    - 在字段标签后追加第一个值（单值字段）
    - 在表格表头下方逐行追加多值数据
    """
    from docx import Document
    try:
        doc = Document(template_path)
        field_map = {a["field_name"]: a["values"] for a in answers}

        # ── 段落：字段标签后填第一个值 ─────────────────────────
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            for field_name, values in field_map.items():
                if not values:
                    continue
                if (field_name in text and
                        (text.endswith(field_name) or
                         text.endswith(field_name + "：") or
                         text.endswith(field_name + ":"))):
                    value = values[0]
                    if para.runs:
                        para.runs[-1].text += str(value)
                    else:
                        para.add_run(str(value))

        # ── 表格：按表头逐行追加多值数据 ───────────────────────
        for table in doc.tables:
            if len(table.rows) == 0:
                continue
            header_row = table.rows[0]
            headers = [cell.text.strip() for cell in header_row.cells]

            max_rows = max(
                (len(vals) for vals in field_map.values() if vals),
                default=0
            )
            for row_idx in range(max_rows):
                new_row = table.add_row()
                for i, cell in enumerate(new_row.cells):
                    if i < len(headers):
                        matched = _fuzzy_match_field(headers[i], field_map, row_idx)
                        if matched is not None:
                            cell.text = str(matched)

        doc.save(output_path)
        logger.info(f"DOCX 智能填写完成: {output_path}")
        return True

    except Exception as e:
        logger.error(f"DOCX 智能填写失败: {e}")
        import shutil
        shutil.copy(template_path, output_path)
        return False


def _fuzzy_match_field(col_name: str, field_map: dict, row_idx: int):
    """
    模糊匹配字段名（忽略大小写、空格、下划线），返回对应行的值。
    field_map: {field_name: [值列表]}
    """
    col_lower = col_name.lower().replace(" ", "").replace("_", "").replace("/", "").replace("\\", "")
    for field_name, values in field_map.items():
        if not values:
            continue
        field_lower = field_name.lower().replace(" ", "").replace("_", "").replace("/", "").replace("\\", "")
        if col_lower == field_lower or col_lower in field_lower or field_lower in col_lower:
            if row_idx < len(values):
                return values[row_idx]
            # 超出范围时不重复最后一个值（避免数据错位）
    return None


# ────────────────────────────────────────────────────────────
# 主入口
# ────────────────────────────────────────────────────────────

def extract_and_fill(
    template_path: str,
    source_file_paths: list,
    output_path: str,
    max_rows: int = 50,
) -> bool:
    """
    智能填表主入口：
    1. 分析模板，识别需要填写的字段（占位符或 LLM 表头识别）
    2. 读取所有数据源文件
    3. 用 LLM 从数据源中提取各字段的值（JSON 数组格式，支持多行）
    4. 将提取的值按行写回模板，保存到 output_path

    Args:
        template_path:      模板文件路径（.docx 或 .xlsx）
        source_file_paths:  数据源文件路径列表
        output_path:        填写完成后的输出路径
        max_rows:           表格类字段最多提取行数（默认50，足够覆盖大多数场景）

    Returns:
        True  成功 / False 失败
    """
    logger.info(f"[智能填表] 开始 | 模板: {os.path.basename(template_path)} | "
                f"数据源: {len(source_file_paths)} 个文件")

    try:
        # Step 1: 识别模板字段
        field_info = extract_template_fields(template_path)
        fields = field_info["fields"]
        method = field_info["method"]

        if not fields:
            logger.warning("模板中未识别到任何字段，将直接复制模板文件")
            import shutil
            shutil.copy(template_path, output_path)
            return True

        logger.info(f"识别到 {len(fields)} 个字段（方法: {method}）: {fields}")

        # Step 2: 读取所有数据源
        source_text = _read_source_texts(source_file_paths)
        if not source_text.strip():
            logger.error("数据源文件读取失败或内容为空")
            return False

        # Step 3: LLM 提取字段值（返回列表格式）
        answers = _extract_values_by_llm(fields, source_text, max_rows=max_rows)
        if not answers:
            logger.error("字段值提取失败，answers 为空")
            return False

        # 统计有效提取数
        filled = sum(1 for a in answers if a.get("values"))
        logger.info(f"提取结果：{filled}/{len(answers)} 个字段有数据")

        # Step 4: 写入模板
        success = _write_to_template(template_path, answers, output_path, method)

        if success:
            logger.success(f"[智能填表] 完成 ✅ | 输出: {output_path}")
        else:
            logger.error("[智能填表] 写入模板失败")

        return success

    except Exception as e:
        logger.error(f"[智能填表] 异常: {e}")
        return False
