"""
文档解析与信息抽取模块 - 负责人: 成员2
函数签名已锁定，不得更改参数名和返回类型
"""

import os
import json
from typing import List, Dict, Any
from loguru import logger
import pdfplumber
from docx import Document
import openpyxl
from openai import OpenAI
from config import settings

def _chunk_text(text: str, file_id: str, page_num: int = 0) -> List[Dict[str, Any]]:
    """内部辅助函数：将文本切分为 50-1000 字的 chunk (严格遵守规范 6.2) [cite: 305]"""
    chunks = []
    chunk_size = 500  # 设定为500字一段，符合50-1000的范围要求 [cite: 305]
    text_length = len(text)

    for i in range(0, text_length, chunk_size):
        chunk_content = text[i:i+chunk_size].strip()
        # 如果最后一段太短（小于50字），拼接到上一段，避免出现极短 chunk [cite: 305]
        if len(chunk_content) < 50 and i != 0:
            if chunks:
                chunks[-1]["content"] += "\n" + chunk_content
            continue

        if chunk_content:
            chunk_id = f"{file_id}_{len(chunks)}"
            chunks.append({
                "chunk_id": chunk_id,
                "content": chunk_content,
                "page": page_num,
                "chunk_type": "text",
                "metadata": {}
            })
    return chunks

def _extract_entities_and_summary(chunks: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], str]:
    """内部辅助函数：调用大模型抽取实体和摘要"""
    if not chunks:
        return [], "文档无有效文本内容"

    # 拼接前几个 chunk 的文本给大模型，避免 token 超限
    sample_text = "\n".join([c["content"] for c in chunks[:3]])

    try:
        # 使用 settings 读取大模型配置 [cite: 274-287]
        client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

        # 以上提示词目前跑不出来，会超时，等待更换模型或许有希望
        prompt = f"""
        请阅读以下文档片段，提取该文档的核心元数据（实体）和摘要。
        如果是表格数据，请提取：主题、核心字段名称、涉及的区域、时间范围等宏观信息。
        如果是合同文本，请提取：甲方、乙方、金额、日期等。
        要求严格返回JSON格式，结构如下：
        {{
            "entities": [{{"key": "字段名或元数据名称", "value": "对应的值"}}],
            "summary": "100字以内的文档摘要"
        }}
        文档内容片段：
        {sample_text}
        请直接输出JSON结果：
        {{
        """
        response = client.chat.completions.create(
            model=settings.llm_model,  # 使用 settings 读取模型名称 [cite: 274-287]
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"} # 强制要求返回 JSON
        )
        result = json.loads(response.choices[0].message.content)

        entities = result.get("entities", [])
        # 溯源填充：将抽取的实体默认映射到第一个 chunk_id 上 [cite: 179-184]
        for ent in entities:
            ent["source_chunk_id"] = chunks[0]["chunk_id"]

        return entities, result.get("summary", "无摘要")

    except Exception as e:
        logger.error(f"LLM 抽取实体/摘要失败: {e}")
        return [], "摘要生成失败"


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

    if not os.path.exists(file_path):
        error_msg = f"文件不存在: {file_path}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)

    # 严格匹配规范要求的五种格式 [cite: 304]
    supported_exts = {'.pdf': 'pdf', '.docx': 'docx', '.xlsx': 'xlsx', '.txt': 'txt', '.md': 'md'}
    if ext not in supported_exts:
        error_msg = f"不支持的文件格式: {ext}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    file_type = supported_exts[ext]
    chunks = []

    try:
        # 1. 针对不同格式进行底层解析 [cite: 126-130, 304]
        if ext in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
                chunks.extend(_chunk_text(text, file_id))

        elif ext == '.docx':
            import docx

            docx_text = []
            try:
                # 🛡️ 战术 1: 标准 python-docx 读取 (应对 95% 的标准 Word 文件)
                doc = docx.Document(file_path)
                for para in doc.paragraphs:
                    if para.text.strip():
                        docx_text.append(para.text.strip())

                for table in doc.tables:
                    for row in table.rows:
                        row_data = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                        if row_data:
                            docx_text.append(" | ".join(row_data))

                if docx_text:
                    chunks.extend(_chunk_text("\n".join(docx_text), file_id))

            except Exception as e:
                logger.warning(f"python-docx 解析异常，启动底层 XML 强读引擎: {e}")

                # 🛡️ 战术 2: 绕过规范，直接解压底层 XML 强读（专治 WPS 或转换器生成的残缺 DOCX）
                try:
                    import zipfile
                    from lxml import etree

                    # 将 DOCX 作为 ZIP 文件直接读取
                    with zipfile.ZipFile(file_path, 'r') as z:
                        xml_content = z.read('word/document.xml')

                    tree = etree.fromstring(xml_content)
                    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    w_ns = ns['w']

                    fallback_text = []
                    # 强行遍历底层 XML 的所有正文段落和表格
                    for element in tree.xpath('//w:body/*', namespaces=ns):
                        if element.tag == f"{{{w_ns}}}p":  # 提取段落
                            t_nodes = element.xpath('.//w:t', namespaces=ns)
                            text = "".join([t.text for t in t_nodes if t.text])
                            if text.strip():
                                fallback_text.append(text.strip())

                        elif element.tag == f"{{{w_ns}}}tbl":  # 提取表格
                            for row in element.xpath('.//w:tr', namespaces=ns):
                                row_data = []
                                for cell in row.xpath('.//w:tc', namespaces=ns):
                                    t_nodes = cell.xpath('.//w:t', namespaces=ns)
                                    cell_text = "".join([t.text for t in t_nodes if t.text]).strip()
                                    if cell_text:
                                        row_data.append(cell_text)
                                if row_data:
                                    fallback_text.append(" | ".join(row_data))

                    if fallback_text:
                        chunks.extend(_chunk_text("\n".join(fallback_text), file_id))
                    else:
                        raise ValueError("底层 XML 提取内容为空")

                except Exception as ex:
                    raise ValueError(f"DOCX 文件损坏严重，底层解析彻底失败: {str(ex)}")


        elif ext == '.xlsx':
            try:
                # 尝试使用官方推荐的 openpyxl
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    wb = openpyxl.load_workbook(file_path, data_only=True)
                    for sheet in wb.worksheets:
                        sheet_text = []
                        for row in sheet.iter_rows(values_only=True):
                            row_data = [str(cell) for cell in row if cell is not None]
                            if row_data:
                                sheet_text.append(" | ".join(row_data))
                        if sheet_text:
                            chunks.extend(_chunk_text("\n".join(sheet_text), file_id))
                # 如果遭遇非标准/损坏的Excel文件导致读出空数据，主动抛出异常触发降级
                if not chunks:
                    raise ValueError("openpyxl 提取内容为空")
            except Exception as e:
                logger.warning(f"openpyxl 解析异常，遭遇非标准或假 Excel 文件，启动 pandas 强力降级解析引擎: {e}")
                import pandas as pd
                import io
                df = None
                # 第一级降级：尝试用 pandas 官方标准引擎读取
                try:
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        df = pd.read_excel(file_path)
                except Exception:
                    try:
                        # 很多假 xlsx 其实是古老的 xls 二进制格式，必须呼叫 xlrd 引擎
                        df = pd.read_excel(file_path, engine='xlrd')
                    except Exception:
                        pass

                if df is None or df.empty:
                    df = None
                    # 读取原始字节，暴力绕过所有底层编码崩溃！
                    try:
                        with open(file_path, 'rb') as f:
                            raw_bytes = f.read()

                        # 第二级降级：网页表格 (HTML)
                        for enc in ['utf-8', 'gbk']:
                            try:
                                decoded_str = raw_bytes.decode(enc, errors='ignore')
                                if '<table' in decoded_str.lower():
                                    df = pd.read_html(io.StringIO(decoded_str))[0]
                                    break
                            except Exception:
                                pass

                        # 第三级降级：CSV/TSV，使用 errors='replace' 强行替换毒字符
                        if df is None:
                            for enc in ['utf-8', 'gbk', 'utf-16']:
                                # 这里是精髓：遇到乱码字符直接替换，绝不报错
                                decoded_str = raw_bytes.decode(enc, errors='replace')
                                for sep in [',', '\t']:
                                    try:
                                        temp_df = pd.read_csv(io.StringIO(decoded_str), sep=sep, on_bad_lines='skip',
                                                              low_memory=False)
                                        # 只要能切出2列以上，就认为是成功对齐了
                                        if len(temp_df.columns) > 1:
                                            df = temp_df
                                            break
                                    except Exception:
                                        pass
                                if df is not None:
                                    break
                    except Exception as fatal_e:
                        logger.error(f"暴力读取字节流失败: {fatal_e}")

                # 终极拦截
                if df is None or df.empty:
                    raise ValueError("终极解析失败：该文件损坏严重或为不支持的加密格式。")
                # 不用 iterrows，直接调用底层的 C 引擎转换为竖线分隔的字符串，耗时从几分钟缩短到 0.1 秒！
                sheet_text = df.to_csv(index=False, sep='|')
                if sheet_text and sheet_text.strip():
                    chunks.extend(_chunk_text(sheet_text, file_id))

        elif ext == '.pdf':
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        chunks.extend(_chunk_text(text, file_id, page_num=i+1))

        # 2. 调用大模型抽取关键实体与摘要 [cite: 179-186]
        logger.info(f"文档读取完毕，成功切分为 {len(chunks)} 个 chunks。正在调用大模型提取信息...")
        entities, summary = _extract_entities_and_summary(chunks)

        # 3. 严格组装返回结果，遵守 4.1 Schema 规范 [cite: 165-187, 299]
        parsed_document = {
            "file_id": file_id,
            "filename": filename,
            "file_type": file_type,
            "chunks": chunks,
            "entities": entities,
            "summary": summary
        }

        logger.success(f"✅ 文件解析与抽取完成: {filename} | 提取实体数: {len(entities)}")
        return parsed_document

    except Exception as e:
        logger.error(f"文件解析失败: {str(e)}")
        raise RuntimeError(f"文件解析失败: {str(e)}")


# # --- 在 document_parser.py 文件最底部加上这段 ---  用于暂时测试
# if __name__ == "__main__":
#     import json
#     import os
#
#     # 1. 指定你的真实测试集目录 (使用 r 前缀防止路径里的 \ 被转义)
#     test_dir = r"E:\AAAjlu\a23-doc-system\测试集\txt"
#
#     print(f"🚀 开始执行本地真实文件测试，读取目录: {test_dir}")
#
#     if not os.path.exists(test_dir):
#         print(f"\n❌ 找不到测试集目录，请检查路径: {test_dir}")
#     else:
#         # 2. 遍历测试目录下的所有文件
#         for idx, filename in enumerate(os.listdir(test_dir)):
#             file_path = os.path.join(test_dir, filename)
#
#             print(f"\n" + "=" * 50)
#             print(f"📄 正在测试文件: {filename}")
#
#             # 给每个文件生成一个假的 file_id 用于测试
#             mock_file_id = f"test-real-{idx + 1:03d}"
#
#             try:
#                 # 调用你的核心解析函数
#                 result = parse_document(file_path, mock_file_id)
#
#                 print(f"🎉 {filename} 解析成功！")
#                 print(
#                     f"📊 统计: 生成了 {len(result.get('chunks', []))} 个文本块(chunks), 提取了 {len(result.get('entities', []))} 个实体。")
#
#                 # 为了防止终端输出太长刷屏，这里只打印实体和摘要看看大模型的效果
#                 # 如果你想看完整的 chunks 文本，可以把下面这行的注释解开
#                 print("\n💡 提取到的实体:")
#                 print(json.dumps(result.get("entities", []), ensure_ascii=False, indent=2))
#                 print(f"\n📝 文档摘要:\n{result.get('summary', '')}")
#
#             except Exception as e:
#                 print(f"❌ {filename} 解析过程中发生报错: {e}")
#
#         print(f"\n" + "=" * 50)
#         print("🏁 所有测试文件处理完毕！")