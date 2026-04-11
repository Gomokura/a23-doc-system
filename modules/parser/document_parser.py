"""
文档解析与信息抽取模块 - 负责人: 成员2
函数签名已锁定，不得更改参数名和返回类型
"""

import os
import json
from typing import List, Dict, Any, Callable, Optional
from loguru import logger
from openai import OpenAI
from config import settings
import re

def _chunk_text(text: str, file_id: str, page_num: int = 0, id_offset: int = 0) -> List[Dict[str, Any]]:
    """
    基于论文研究改良：Markdown 语义切块 (Semantic Chunking)
    优先按 Markdown 标题 (#, ##) 进行切分，保证逻辑连贯性

    id_offset: 全局 chunk 序号起点。多页 PDF 等对 _chunk_text 多次调用时须传入当前 len(chunks)，
    否则每页都会从 file_id_0 编号，导致 ChromaDB「Expected IDs to be unique」错误。
    """
    chunks = []

    # 使用正则按 Markdown 标题或双换行进行初步切分,保证一个完整的章节或一个完整的表格不会被撕裂
    raw_sections = re.split(r'(?=\n#{1,4} |\n\n)', text)

    current_chunk = ""
    for sec in raw_sections:
        sec = sec.strip()
        if not sec: continue

        if len(current_chunk) + len(sec) < 800:
            current_chunk += sec + "\n\n"
        else:
            if current_chunk.strip():
                chunks.append({
                    "chunk_id": f"{file_id}_{id_offset + len(chunks)}",
                    "content": current_chunk.strip(),
                    "page": page_num,
                    "chunk_type": "text",
                    "metadata": {}
                })
            # 如果某一个表格/段落特别长，直接单独立块
            current_chunk = sec + "\n\n"

    if current_chunk.strip():
        chunks.append({
            "chunk_id": f"{file_id}_{id_offset + len(chunks)}",
            "content": current_chunk.strip(),
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
    # 如果 chunk 数量少于等于3个，直接全给；否则取头、中、尾三个最具代表性的段落
    # 1. 抽样逻辑保持不变 (头、中、尾)
    if len(chunks) <= 3:
        sampled_chunks = chunks
    else:
        mid_idx = len(chunks) // 2
        sampled_chunks = [chunks[0], chunks[mid_idx], chunks[-1]]

    # 2. 拼接文本
    sample_text = "\n".join([c["content"] for c in sampled_chunks])

    # 3. 加入 Token 防爆阀门
    # 大多数开源 LLM 处理 5000-8000 个中文字符是极其轻松且便宜的。
    # 如果拼装后的文本超过 6000 字，直接暴力截断前 6000 字喂给模型。
    # 截断的文本足够它看出这是什么文档、有什么关键字段了。
    MAX_CHARS = 6000
    if len(sample_text) > MAX_CHARS:
        logger.warning(f"抽样文本长度({len(sample_text)})超过阈值，启动截断保护，截取前 {MAX_CHARS} 字符...")
        sample_text = sample_text[:MAX_CHARS] + "\n\n...[内容过长，已被截断]..."

    try:
        # 使用 settings 读取大模型配置
        client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

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

        logger.info(f"===> 正在向文本大模型 {settings.llm_model} 发起实体抽取请求...")
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        logger.info("===> 大模型返回实体结果成功！")

        # 兼容 qwen3 思考模式：回复内容可能在 reasoning 字段而非 content
        raw_content = response.choices[0].message.content
        raw_reasoning = getattr(response.choices[0].message, "reasoning", None) or ""
        if not raw_content and raw_reasoning:
            raw_content = raw_reasoning
            logger.warning("content 字段为空，已从 reasoning 字段提取回复（qwen3 思考模式）")

        result = json.loads(raw_content)
        entities = result.get("entities", [])
        summary = result.get("summary", "摘要生成失败")

        # 精准溯源逻辑 (Source Mapping),不再粗暴映射到第一个 chunk，而是遍历抽样 chunk，寻找实体值的真实出处
        for entity in entities:
            if not isinstance(entity, dict) or "key" not in entity:
                continue

            val = str(entity.get("value", ""))
            found_chunk_id = sampled_chunks[0]["chunk_id"]  # 兜底默认值

            # 如果值有效，去 chunk 文本里找它具体在哪一段
            if val and val not in ["未明确", "未提及", "无"]:
                for c in sampled_chunks:
                    if val in c["content"]:
                        found_chunk_id = c["chunk_id"]
                        break

            entity["source_chunk_id"] = found_chunk_id
        return entities, summary

    except Exception as e:
        logger.error(f"LLM 抽取实体/摘要失败: {e}")
        return [], "摘要生成失败"


def parse_document(file_path: str, file_id: str,
                  progress_callback: Optional[Callable[[int, str], None]] = None) -> dict:
    """
    解析文档，返回 ParsedDocument dict（严格遵守规范文档 4.1 Schema）

    Args:
        file_path: 文件本地路径（uploads/ 目录下）
        file_id:   文件唯一ID（由上传接口生成）
        progress_callback: 可选，进度回调函数，接受 (percent: int, message: str)
                          例: progress_callback(20, "解析 DOCX 中...")
                          会在关键阶段被调用，便于外部（如 _run_parse）向数据库回传进度
    Returns:
        ParsedDocument dict

    Raises:
        ValueError:   不支持的文件格式
        RuntimeError: 解析失败（文件损坏/加密等）
    """
    _report = progress_callback or (lambda pct, msg: None)

    def _pct(p: int, m: str):
        _report(p, m)
        logger.debug(f"[parse_document] progress={p}: {m}")

    logger.info(f"开始解析文件: {file_path}, file_id: {file_id}")
    _pct(5, "开始解析...")

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
            _pct(10, "解析 TXT/MD 文件...")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
                if text:
                    chunks.extend(_chunk_text(text, file_id))
            _pct(30, f"TXT/MD 解析完成，共 {len(chunks)} 块")


        elif ext == '.docx':
            _pct(10, "解析 DOCX 文件...")
            import docx

            docx_md = []
            try:
                # 🛡️ 战术 1: 语义化提取 (保留标题层级和标准表格)
                doc = docx.Document(file_path)

                # 1. 提取段落并识别标题级数
                for para in doc.paragraphs:
                    text = para.text.strip()
                    if not text: continue
                    style_name = para.style.name.lower()
                    if 'heading 1' in style_name or '标题 1' in style_name:
                        docx_md.append(f"# {text}")
                    elif 'heading 2' in style_name or '标题 2' in style_name:
                        docx_md.append(f"## {text}")
                    elif 'heading 3' in style_name or '标题 3' in style_name:
                        docx_md.append(f"### {text}")
                    else:
                        docx_md.append(text)

                # 2. 提取表格为标准的 Markdown 格式
                for table in doc.tables:
                    md_table = []
                    for i, row in enumerate(table.rows):
                        # 清理单元格内的换行符，防止破坏 Markdown 结构
                        row_data = [cell.text.replace('\n', ' ').strip() for cell in row.cells]
                        md_table.append("| " + " | ".join(row_data) + " |")
                        # 补充表头下方的分隔线
                        if i == 0:
                            md_table.append("|" + "|".join(["---"] * len(row.cells)) + "|")
                    if md_table:
                        docx_md.append("\n" + "\n".join(md_table) + "\n")
                if docx_md:
                    # 将组装好的纯正 Markdown 送入语义切块器
                    chunks.extend(_chunk_text("\n\n".join(docx_md), file_id))

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
            _pct(10, "解析 XLSX 文件...")
            import pandas as pd
            import warnings

            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    # 使用 pandas 一次性读取所有的 sheet
                    xls = pd.ExcelFile(file_path)
                    for sheet_name in xls.sheet_names:
                        df = pd.read_excel(xls, sheet_name=sheet_name)
                        if df.empty:
                            continue
                        # 填充空值，避免出现 nan 影响大模型判断
                        df = df.fillna("")
                        headers = df.columns.tolist()
                        header_row = "| " + " | ".join([str(h).replace('\n', ' ') for h in headers]) + " |"
                        sep_row = "|" + "|".join(["---"] * len(headers)) + "|"

                        # 按行数分块：每 50 行一个 chunk，每块都带表头，让 LLM 知道列含义
                        ROWS_PER_CHUNK = 50
                        total_rows = len(df)
                        for start in range(0, total_rows, ROWS_PER_CHUNK):
                            end = min(start + ROWS_PER_CHUNK, total_rows)
                            block_lines = [
                                f"## 表格工作簿：{sheet_name}（第{start+1}-{end}行，共{total_rows}行）\n",
                                header_row,
                                sep_row,
                            ]
                            for _, row in df.iloc[start:end].iterrows():
                                row_data = [str(item).replace('\n', ' ').strip() for item in row]
                                block_lines.append("| " + " | ".join(row_data) + " |")
                            block_md = "\n".join(block_lines)
                            chunks.append({
                                "chunk_id": f"{file_id}_{len(chunks)}",
                                "content": block_md,
                                "page": 0,
                                "chunk_type": "text",
                                "metadata": {"sheet": sheet_name, "row_start": start, "row_end": end}
                            })

                if not chunks:
                    raise ValueError("常规引擎提取内容为空")

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
            import fitz  # PyMuPDF
            import base64
            import re

            # 屏蔽底层的底层红字警告
            fitz.TOOLS.mupdf_display_errors(False)
            logger.info("PDF 文件：尝试视觉大模型解析，失败则降级为文本提取...")

            _pct(10, "解析 PDF 文件...")
            vlm_ok = False
            try:
                from openai import OpenAI as _VLMClient
                # 优先用 Ollama 的视觉模型（库名如 qwen2.5vl:3b，勿写成 qwen2.5-vl）
                _vlm_client = _VLMClient(
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                )
                # PDF 页 OCR：优先 pdf_vlm_model（如 qwen2.5vl:3b），避免与问答共用大体量模型导致 OOM
                vlm_model = (getattr(settings, "pdf_vlm_model", None) or "").strip() or settings.llm_model

                doc = fitz.open(file_path)
                total_pages = len(doc)
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=150)
                    b64_img = base64.b64encode(pix.tobytes("png")).decode("utf-8")
                    prompt_text = (
                        "请将这张图片中的文档内容完美转换为标准的Markdown格式。\n"
                        "要求：\n"
                        "1. 严格保留所有的表格结构（使用Markdown表格表示）。\n"
                        "2. 严格保留所有的标题层级（使用#表示）。\n"
                        "3. 如果有公式，请尽量使用LaTeX语法。\n"
                        "4. 不要包含任何开场白或解释性废话，只输出Markdown正文。"
                    )

                    response = _vlm_client.chat.completions.create(
                        model=vlm_model,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}},
                                    {"type": "text", "text": prompt_text}
                                ]
                            }
                        ],
                        timeout=60,
                    )
                    page_md = response.choices[0].message.content.strip()
                    page_md = re.sub(r'^```markdown\n|```$', '', page_md, flags=re.IGNORECASE | re.MULTILINE).strip()
                    if page_md:
                        chunks.extend(
                            _chunk_text(page_md, file_id, page_num=i + 1, id_offset=len(chunks))
                        )
                    _pct(10 + int((i + 1) / total_pages * 30), f"PDF VLM 解析第 {i+1}/{total_pages} 页...")
                doc.close()
                vlm_ok = True
                logger.info("PDF VLM 解析成功！")
                _pct(40, f"PDF VLM 解析完成，共 {len(chunks)} 块")

            except Exception as ve:
                logger.warning(f"Ollama VLM 解析失败，降级为文本提取: {ve}")
                # 降级：使用纯文本提取
                try:
                    doc = fitz.open(file_path)
                    for i, page in enumerate(doc):
                        text = page.get_text("text")
                        if text and text.strip():
                            chunks.extend(
                                _chunk_text(text.strip(), file_id, page_num=i + 1, id_offset=len(chunks))
                            )
                    doc.close()
                    logger.info(f"PDF 文本提取完成: {len(chunks)} 块")
                except Exception as te:
                    logger.error(f"PDF 文本提取也失败: {te}")
                    raise RuntimeError(f"PDF 解析失败: VLM错误={ve}, 文本错误={te}")

        # ═══════════════════════════════════════════════════════
        # 所有格式解析完毕，chunks 收集完成！
        # 下面进入统一的实体和摘要抽取阶段 (使用普通的文本大模型)
        # ═══════════════════════════════════════════════════════

        # 2. 调用普通文本大模型抽取关键实体与摘要
        logger.info(f"文档切分完毕 (共 {len(chunks)} 块)。正在调用普通文本大模型提取实体和摘要...")

        _pct(50, f"文档切分完成（共 {len(chunks)} 块），正在调用大模型提取实体和摘要...")

        # 你的 _extract_entities_and_summary 函数内部使用的是 settings.llm_model，完美解耦！
        entities, summary = _extract_entities_and_summary(chunks)

        _pct(65, "实体和摘要提取完成，正在组装结果...")

        # 3. 严格组装返回结果
        parsed_document = {
            "file_id": file_id,
            "filename": filename,
            "file_type": file_type,
            "chunks": chunks,
            "entities": entities,
            "summary": summary
        }

        logger.success(f"✅ 文件解析完成: {filename} | 提取实体数: {len(entities)}")
        return parsed_document

    except Exception as e:
        logger.error(f"文件解析失败: {str(e)}")
        raise RuntimeError(f"文件解析失败: {str(e)}")


# 用于暂时测试
if __name__ == "__main__":
    import json
    import os

    # 1. 指定你的真实测试集目录 (使用 r 前缀防止路径里的 \ 被转义)
    test_dir = r"E:\AAAjlu\a23-doc-system\测试集\pdf"

    print(f"🚀 开始执行本地真实文件测试，读取目录: {test_dir}")

    if not os.path.exists(test_dir):
        print(f"\n❌ 找不到测试集目录，请检查路径: {test_dir}")
    else:
        # 2. 遍历测试目录下的所有文件
        for idx, filename in enumerate(os.listdir(test_dir)):
            file_path = os.path.join(test_dir, filename)

            print(f"\n" + "=" * 50)
            print(f"📄 正在测试文件: {filename}")

            # 给每个文件生成一个假的 file_id 用于测试
            mock_file_id = f"test-real-{idx + 1:03d}"

            try:
                # 调用你的核心解析函数
                result = parse_document(file_path, mock_file_id)

                print(f"🎉 {filename} 解析成功！")
                print(
                    f"📊 统计: 生成了 {len(result.get('chunks', []))} 个文本块(chunks), 提取了 {len(result.get('entities', []))} 个实体。")

                # 为了防止终端输出太长刷屏，这里只打印实体和摘要看看大模型的效果
                # 如果你想看完整的 chunks 文本，可以把下面这行的注释解开
                print("\n💡 提取到的实体:")
                print(json.dumps(result.get("entities", []), ensure_ascii=False, indent=2))
                print(f"\n📝 文档摘要:\n{result.get('summary', '')}")

            except Exception as e:
                print(f"❌ {filename} 解析过程中发生报错: {e}")

        print(f"\n" + "=" * 50)
        print("🏁 所有测试文件处理完毕！")
