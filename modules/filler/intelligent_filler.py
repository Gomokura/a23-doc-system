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
        # xlsx 模板：直接用 openpyxl 读取表头列名（绕过 LLM 识别）
        if not found:
            from openpyxl.cell.cell import MergedCell
            for sheet in wb.worksheets:
                for row in sheet.iter_rows():
                    row_vals = []
                    for cell in row:
                        if isinstance(cell, MergedCell):
                            continue
                        v = cell.value
                        if v is None:
                            continue
                        v_str = str(v).strip().strip("'").strip()
                        if not v_str:
                            continue
                        row_vals.append(v_str)
                    if row_vals:
                        found.update(row_vals)
                        break
                if found:
                    break

    if found:
        logger.info(f"占位符检测：发现 {len(found)} 个占位符字段: {found}")
        # xlsx 表格模板用智能追加模式（不是单值占位符替换）
        if ext == '.xlsx':
            return {"fields": list(found), "method": "llm"}
        return {"fields": list(found), "method": "placeholder"}

    # ── 无占位符：用 LLM 分析模板表头 ─────────────────────────
    logger.info("模板无占位符，启动 LLM 智能识别表头字段...")
    raw_text = _read_template_text(template_path, ext)
    if not raw_text.strip():
        return {"fields": [], "method": "llm"}

    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        default_headers=settings.openai_default_headers,
        timeout=120,
    )
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
                    row_texts = [str(cell.value).strip().strip("'\"") for cell in row
                                 if cell.value is not None and str(cell.value).strip().strip("'\"")]
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
                import io
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    xls = pd.ExcelFile(path)
                    sheet_texts = []
                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name=sheet_name)
                        df = df.fillna("")
                        # 保留列标题行（CSV 第一行），确保 LLM 能识别每列含义
                        # 格式：每行 "列名1: 值1, 列名2: 值2, ..."
                        csv_buffer = io.StringIO()
                        df.to_csv(csv_buffer, index=False, encoding='utf-8')
                        csv_content = csv_buffer.getvalue().strip()
                        sheet_texts.append(f"[Sheet: {sheet_name}]\n{csv_content}")
                    # 拼接所有 sheet，限制总字符数避免 token 爆炸
                    text = "\n\n".join(sheet_texts)
                    MAX_SOURCE = 15000
                    if len(text) > MAX_SOURCE:
                        text = text[:MAX_SOURCE] + "\n...[内容过长已截断]..."

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

def _extract_values_by_llm(template_fields: list, source_file_paths: list, source_text: str, max_rows: int = 5) -> list:
    """
    从数据源中提取各字段的值，混合策略：
    - xlsx 文件：直接用 pandas 按列名读取（最可靠）
    - 其他文件：用 LLM 从文本中提取（兜底）

    返回格式:
        [{"field_name": "字段名", "values": ["值1", "值2", ...]}, ...]
    """
    if not template_fields:
        return []

    answers = []

    # ── xlsx 文件：直接 pandas 读取 ─────────────────────────────────────────
    xlsx_sources = [p for p in source_file_paths if os.path.splitext(p)[1].lower() == '.xlsx']
    if xlsx_sources:
        import warnings
        import pandas as pd
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

        for xlsx_path in xlsx_sources:
            try:
                xls = pd.ExcelFile(xlsx_path)
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_name)
                    df = df.fillna("")

                    # 清理列名（去除空格和单引号）
                    df.columns = [str(c).strip().strip("'\"").strip() for c in df.columns]

                    # 精确匹配：只接受列名完全相同的字段（忽略大小写、空格差异）
                    for col_name in df.columns:
                        col_clean = col_name.lower().replace(" ", "").replace("_", "").replace("/", "").replace("\\", "")
                        matched = None
                        for tf in template_fields:
                            tf_clean = tf.lower().replace(" ", "").replace("_", "").replace("/", "").replace("\\", "")
                            if col_clean == tf_clean:
                                matched = tf
                                break
                        if not matched:
                            continue
                        field_name = matched
                        col_data = df[col_name].astype(str).tolist()
                        col_data = [v for v in col_data if v not in ("", "nan", "NaN")]
                        if not col_data:
                            continue
                        # 合并到已有答案
                        existing = next((a for a in answers if a["field_name"] == field_name), None)
                        if existing:
                            existing["values"].extend(col_data[:max_rows])
                        else:
                            answers.append({"field_name": field_name, "values": col_data[:max_rows]})
            except Exception as e:
                logger.warning(f"pandas 读取 xlsx 失败 {os.path.basename(xlsx_path)}: {e}")

    # ── 非 xlsx 文件：用 LLM 提取 ─────────────────────────────────────────
    non_xlsx = [p for p in source_file_paths if os.path.splitext(p)[1].lower() != '.xlsx']
    if non_xlsx and source_text.strip():
        llm_answers = _extract_by_llm_from_text(template_fields, source_text, max_rows)
        for la in llm_answers:
            existing = next((a for a in answers if a["field_name"] == la["field_name"]), None)
            if existing:
                existing["values"].extend(la["values"])
            else:
                answers.append(la)

    # 过滤掉"未找到"类占位符，限制每字段最多 max_rows 个值（取前几行，保持行对齐）
    for a in answers:
        a["values"] = [v for v in a["values"] if v not in ("(未找到)", "(提取失败)", "")][:max_rows]

    logger.info(f"字段提取完成，共 {len(answers)} 个字段有值: " + str([(a["field_name"], len(a["values"])) for a in answers]))
    return answers


def _best_match_col(field: str, col_names: list) -> str | None:
    """
    在 col_names 中找到与 field 最匹配的列名（模糊匹配）。
    """
    field_clean = field.lower().replace(" ", "").replace("_", "").replace("/", "").replace("\\", "")
    best_score = 0
    best_col = None
    for col in col_names:
        col_clean = col.lower().replace(" ", "").replace("_", "").replace("/", "").replace("\\", "")
        if col_clean == field_clean:
            return col
        # 计算相似度：共同字符越多分数越高
        common = sum(1 for c in field_clean if c in col_clean)
        score = common / max(len(field_clean), 1)
        if score > best_score and score > 0.5:
            best_score = score
            best_col = col
    return best_col


def _extract_by_llm_from_text(template_fields: list, source_text: str, max_rows: int) -> list:
    """
    让 LLM 从非结构化文本中，根据模板表头字段名提取对应值。
    """
    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        default_headers=settings.openai_default_headers,
        timeout=120,
    )

    MAX_SOURCE = 12000
    if len(source_text) > MAX_SOURCE:
        source_text = source_text[:MAX_SOURCE] + "\n...[内容过长已截断]..."

    fields_str = "\n".join(f"- {f}" for f in template_fields)

    prompt = f"""你是一个表格数据提取助手。已知数据源文档内容，你需要根据【模板表头列名】在数据源中找到对应的值并返回。

模板表头列名（必须严格按这些名称返回答案）：
{fields_str}

提取规则：
1. 严格按照模板表头列名在数据源中查找对应值，不要编造数据
2. 每个列名对应一个 values 数组，即使只有一个值也用数组
3. 如果数据源中某列有多个行的值，取前 {max_rows} 行，每行一个元素
4. 如果某列在数据源中找不到，返回空数组 []
5. values 数组中只包含纯值，不要加前缀、编号或说明文字

严格返回如下 JSON 格式（不要有其他文字）：
{{
  "answers": [
    {{"field_name": "列名1", "values": ["值1", "值2", "值3"]}},
    {{"field_name": "列名2", "values": ["值A", "值B"]}}
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
        logger.info(f"LLM 原始返回: {raw[:500]}")
        result = json.loads(raw)
        answers = result.get("answers", [])

        # 兼容旧格式，统一转成 values 列表
        normalized = []
        for a in answers:
            field_name = a.get("field_name", "")
            if "values" in a:
                vals = a["values"]
                if not isinstance(vals, list):
                    vals = [str(vals)]
            elif "value" in a:
                raw_val = str(a["value"])
                vals = [v.strip() for v in raw_val.split("\n") if v.strip()]
                if not vals:
                    vals = [raw_val]
            else:
                vals = []
            vals = [v for v in vals if v not in ("(未找到)", "(提取失败)", "")]
            normalized.append({"field_name": field_name, "values": vals})

        logger.info(f"LLM 提取完成，共 {len(normalized)} 个字段")
        return normalized

    except Exception as e:
        logger.error(f"LLM 提取字段值失败: {e}")
        return []


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
    - 遍历所有工作表，找到最佳表头行（非空单元格最多的行）
    - 处理合并单元格：只读主格，避免从属格值覆盖
    - 按表头列名模糊匹配字段，逐行写入数据
    """
    from openpyxl import load_workbook
    try:
        wb = load_workbook(template_path)

        # field_name -> [值列表]
        field_map = {a["field_name"]: a["values"] for a in answers}

        # ── 遍历所有工作表，找到最佳表头行 ─────────────────────────
        best_ws = None
        best_header_row = None
        best_header_cells = {}  # col_idx -> 字段名
        best_score = 0

        for ws in wb.worksheets:
            # 收集合并单元格主格集合（只读主格的值）
            merged_master = set()
            for rng in ws.merged_cells.ranges:
                merged_master.add((rng.min_row, rng.min_col))

            # 遍历所有行，找非空单元格最多的行
            for row_idx, row in enumerate(ws.iter_rows(), start=1):
                cells_this_row = []
                for cell in row:
                    if cell.value is None:
                        continue
                    val = str(cell.value).strip().strip("'")
                    if not val:
                        continue
                    # 无合并单元格时，所有单元格都有效；有合并单元格时，只取主格
                    if merged_master and (cell.row, cell.column) not in merged_master:
                        continue
                    cells_this_row.append((cell.column, val))

                # 评分：优先选择非空单元格数最多的行
                # 同时排除只有1-2个单元格的行（可能是标题行而非表头）
                if len(cells_this_row) >= 3 and len(cells_this_row) > best_score:
                    best_score = len(cells_this_row)
                    best_ws = ws
                    best_header_row = row_idx
                    best_header_cells = {col: name for col, name in cells_this_row}

        # 没有找到表头行
        if best_ws is None or best_header_row is None:
            logger.warning("模板中未找到有效表头行，直接追加数据")
            for a in answers:
                for val in a["values"]:
                    wb.active.append([a["field_name"], val])
            wb.save(output_path)
            return True

        logger.info(f"找到表头行: 第{best_header_row}行，列数: {len(best_header_cells)}, 工作表: {best_ws.title}")

        # ── 计算最多需要写几行 ───────────────────────────────────
        max_data_rows = max(
            (len(vals) for vals in field_map.values() if vals),
            default=1
        )
        if max_data_rows == 0:
            logger.warning("所有字段均未提取到值，复制模板原文")
            import shutil
            shutil.copy(template_path, output_path)
            return True

        start_row = best_header_row + 1

        # ── 逐行写入，处理合并单元格 ──────────────────────────────
        # 收集所有合并区域（行范围），避免写入时触发 openpyxl 冲突
        merged_row_ranges = set()
        for rng in best_ws.merged_cells.ranges:
            if rng.min_row >= best_header_row:
                merged_row_ranges.add((rng.min_row, rng.max_row))

        written_cells = set()  # 已写入的 (row, col)

        logger.info(f"字段映射: {field_map}")

        for data_row_offset in range(max_data_rows):
            write_row = start_row + data_row_offset

            # 跳过已合并的行（表头本身可能跨行）
            skip_this_row = False
            for min_r, max_r in merged_row_ranges:
                if min_r <= write_row <= max_r and write_row != min_r:
                    skip_this_row = True
                    break
            if skip_this_row:
                continue

            for col_idx, col_name in best_header_cells.items():
                # 避免重复写入同一单元格
                if (write_row, col_idx) in written_cells:
                    continue

                matched_value = _fuzzy_match_field(col_name, field_map, data_row_offset)
                if matched_value is not None:
                    best_ws.cell(row=write_row, column=col_idx, value=matched_value)
                    written_cells.add((write_row, col_idx))

        wb.save(output_path)
        logger.info(f"XLSX 智能填写完成: {output_path}，工作表={best_ws.title}，"
                    f"表头行={best_header_row}，共写入 {max_data_rows} 行数据")
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
    模糊匹配字段名（忽略大小写、空格、下划线、斜杠），返回对应行的值。

    匹配策略（按优先级）：
    1. 精确匹配（忽略空格后相等）
    2. 包含匹配（清理后列名被字段名包含，或字段名被列名包含）
    3. 子串匹配（任一方包含另一方）

    行索引处理：
    - row_idx < len(values): 返回对应行
    - row_idx >= len(values): 返回最后一个值（重复填充）
    - values 为空或 row_idx < 0: 返回 None
    """
    col_lower = col_name.lower().replace(" ", "").replace("_", "").replace("/", "").replace("\\", "")
    candidates = []

    for field_name, values in field_map.items():
        if not values:
            continue
        field_lower = field_name.lower().replace(" ", "").replace("_", "").replace("/", "").replace("\\", "")

        score = 0
        # 精确匹配（最高优先级）
        if col_lower == field_lower:
            score = 3
        # 清理后相等（忽略所有空白字符）
        elif col_lower == field_lower:
            score = 3
        # 列名包含字段名（列标题更具体）
        elif field_lower and col_lower in field_lower:
            score = 2
        # 字段名包含列名（字段定义更具体）
        elif col_lower and field_lower in col_lower:
            score = 2
        # 子串匹配（任一方在另一方中）
        elif field_lower and col_lower in field_lower:
            score = 1
        else:
            continue

        # 取对应行，如果超出范围则取最后一行（重复填充）
        if row_idx < len(values):
            val = values[row_idx]
        else:
            val = values[-1]  # 超出范围时重复最后一行

        candidates.append((score, field_name, val))

    if not candidates:
        return None

    # 按优先级排序（分数高的在前），返回最佳匹配
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0]

    # 如果有多个候选且分数不同，选最优
    if len(candidates) > 1 and candidates[0][0] > candidates[1][0]:
        return best[2]
    # 如果分数相同但字段不同，返回精确匹配的那个（如果有）
    exact = next((c for c in candidates if c[0] == 3), None)
    if exact:
        return exact[2]
    # 否则返回分数最高的第一个
    return best[2]


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
        if not source_text.strip() and not any(os.path.splitext(p)[1].lower() == '.xlsx' for p in source_file_paths):
            logger.error("数据源文件读取失败或内容为空")
            return False

        # Step 3: 提取字段值（xlsx 直接 pandas 读取，其他文件用 LLM）
        answers = _extract_values_by_llm(fields, source_file_paths, source_text, max_rows=max_rows)
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
