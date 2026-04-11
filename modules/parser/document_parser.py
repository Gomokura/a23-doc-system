"""
文档解析与信息抽取模块 - 负责人: 成员2
函数签名已锁定，不得更改参数名和返回类型
"""
import os
import re
from typing import List, Dict, Any, Callable, Optional

from docling.datamodel import pipeline_options
from docling.document_converter import DocumentConverter
from loguru import logger
from config import settings

# 🌟 速度优化核心 1：将高频调用的正则表达式提升到全局作用域并预编译 (C引擎级别)
# 避免每次切块和提取时重复编译正则对象，极大降低 CPU 开销
CHUNK_SPLIT_PATTERN = re.compile(r'(?=\n#{1,4} |\n\n|!\[IMAGE_CHUNK:.*?\]\(.*?\))')
MD_STRIP_PATTERN = re.compile(r'^```[a-zA-Z]*\n|```$', re.IGNORECASE | re.MULTILINE)

def deep_clean_text(text: str) -> str:
    """
    深度算法清洗：打蜡与褪蜡 (Cleaning Pipeline)
    去除不可见乱码，缝合由于排版造成的强制截断，压缩多余换行
    """
    # 匹配常见的页码模式：— 1 —, - 1 -,  1 , 以及单纯的数字行
    PAGE_NUMBER_PATTERN = re.compile(
        r'^\s*[—\-\－]?\s*\d+\s*[—\-\－]?\s*$',
        re.MULTILINE
    )
    if not text:
        return ""
    # 1. 消除乱码与不可见字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # 2. 清理被空格/制表符污染的换行 (将 \n \t \n 净化为 \n\n)
    text = re.sub(r'\n[ \t]+(?=\n)', '\n', text)
    # 3. 排版缝合：处理行末连字符避免因宽度限制截断单词
    text = re.sub(r'([a-zA-Z])-\n([a-zA-Z])', r'\1\2', text)
    # 4. 压缩空白，剔除行首尾多余空格
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 5. 过滤掉像 — 1 — 这样的纯页码行
    # 按行拆分，只保留不是页码的行
    lines = text.split('\n')
    cleaned_lines = [line for line in lines if not PAGE_NUMBER_PATTERN.match(line.strip())]
    text = '\n'.join(cleaned_lines)
    return text.strip()

def inject_markdown_headers(text: str) -> str:
    """
    智能将常见的 TXT/DOCX 中文章节标号替换为 Markdown 标题格式，
    以便 _chunk_text 能正确提取 parent_header
    """
    if not text: return ""
    
    lines = text.split('\n')
    for i, line in enumerate(lines):
        s_line = line.strip()
        # 匹配 "第x章/节/部分 xxx" 或 "一、xxx" 类型的独立短文本行
        if len(s_line) < 50:
            if re.match(r'^第[一二三四五六七八九十百千万0-9]+[章节篇部分条]\s+.*$', s_line):
                lines[i] = f"# {s_line}"
            elif re.match(r'^[一二三四五六七八九十]+\s*、.*$', s_line) or re.match(r'^[0-9]+\s*、.*$', s_line):
                lines[i] = f"## {s_line}"
            elif re.match(r'^（[一二三四五六七八九十]+）.*$', s_line) or re.match(r'^([0-9]+)\.(?!\d).*$', s_line):
                lines[i] = f"### {s_line}"
    return "\n".join(lines)

def _chunk_text(text: str, file_id: str, page_num: int = -1, id_offset: int = 0, base_meta: dict = None, state: dict = None) -> List[Dict[str, Any]]:
    """
    基于论文研究改良：Markdown 语义切块 (Semantic Chunking)
    优先按 Markdown 标题 (#, ##) 进行切分，保证逻辑连贯性

    id_offset: 全局 chunk 序号起点。多页 PDF 等对 _chunk_text 多次调用时须传入当前 len(chunks)，
    否则每页都会从 file_id_0 编号，导致 ChromaDB「Expected IDs to be unique」错误。
    """
    chunks = []
    
    if state is None:
        state = {"current_header": "", "char_count": 0}

    # 使用正则按 Markdown 标题、双换行或句号进行初步切分,保证一个完整的章节或一个完整的段落不会被撕裂
    raw_sections = CHUNK_SPLIT_PATTERN.split(text)

    # 🌟 速度优化：使用列表 append 然后 join 替代低效的纯字符串 +=
    current_chunk_lines = []
    current_len = 0
    
    # 用于追踪当前 Chunk 所属的最近一个 Markdown 标题，作为高级 Metadata
    current_header = state.get("current_header", "")
    char_count = state.get("char_count", 0)

    for sec in raw_sections:
        char_count += len(sec)  # 记录处理字符数以估算页码
        sec = sec.strip()
        if not sec: continue
        
        # 探测是否为图片占位符
        img_match = re.match(r'!\[IMAGE_CHUNK:(.*?)\]\((.*?)\)', sec, re.IGNORECASE)
        computed_page = page_num if page_num > 0 else (char_count // 800) + 1

        if img_match:
            img_name = img_match.group(1).strip()
            img_path = img_match.group(2).strip()
            
            # 首先倾倒之前积攒的文本作为 text 块
            if current_chunk_lines:
                chunk_content = "\n\n".join(current_chunk_lines).strip()
                # 针对 PDF 切块：过滤掉行与行之间的空行
                if base_meta and base_meta.get("file_type") == "pdf":
                    chunk_content = re.sub(r'\n{2,}', '\n', chunk_content)
                if chunk_content:
                    meta = base_meta.copy() if base_meta else {}
                    meta.update({
                        "page": computed_page,
                        "parent_header": current_header
                    })
                    chunks.append({
                        "chunk_id": f"{file_id}_{id_offset + len(chunks)}",
                        "content": chunk_content,
                        "page": computed_page,
                        "chunk_type": "text",
                        "metadata": meta
                    })
                current_chunk_lines = []
                current_len = 0
            
            # 插入 Image Chunk 锚点
            meta = base_meta.copy() if base_meta else {}
            meta.update({
                "page": computed_page,
                "parent_header": current_header,
                "image_path": img_path,
                "has_image": True,
                "description": "待下游利用 VLM 异步解析",
                "nearby_text": "此处需要获取上下文"  # 可以在最终组装时根据上一个和下一个元素进行回补
            })
            chunks.append({
                "chunk_id": f"{img_name}",
                "content": f"[图片占位符: {img_name}]",
                "page": computed_page,
                "chunk_type": "image",
                "metadata": meta
            })
            
            # 截断占位符后续可能粘连的文字
            sec = sec[img_match.end():].strip()
            if not sec:
                continue

        sec_len = len(sec)

        # 尝试捕获 Markdown 标题，以丰富后续所有块的上下文
        header_match = re.match(r'^(#{1,6})\s+([^\n]+)', sec)
        if header_match:
            current_header = header_match.group(2).strip()
            state["current_header"] = current_header
            # 将标题本身的长度算入

        # 计算当前物理页码（按每页 800 字符粗略估算，针对没有物理页码概念的txt/md/docx）
        computed_page = page_num if page_num > 0 else (char_count // 800) + 1

        if current_len + sec_len < 800:
            current_chunk_lines.append(sec)
            current_len += sec_len + 2  # +2 for \n\n
        else:
            if current_chunk_lines:
                chunk_content = "\n\n".join(current_chunk_lines).strip()
                if base_meta and base_meta.get("file_type") == "pdf":
                    chunk_content = re.sub(r'\n{2,}', '\n', chunk_content)
                meta = base_meta.copy() if base_meta else {}
                meta.update({
                    "page": computed_page,
                    "parent_header": current_header  # 注入结构化血缘
                })
                chunks.append({
                    "chunk_id": f"{file_id}_{id_offset + len(chunks)}",
                    "content": chunk_content,
                    "page": computed_page,
                    "chunk_type": "text",
                    "metadata": meta
                })
            # 如果某一个表格/段落特别长，直接单独立块
            current_chunk_lines = [sec]
            current_len = sec_len + 2

    if current_chunk_lines:
        computed_page = page_num if page_num > 0 else (char_count // 800) + 1
        chunk_content = "\n\n".join(current_chunk_lines).strip()
        if base_meta and base_meta.get("file_type") == "pdf":
            chunk_content = re.sub(r'\n{2,}', '\n', chunk_content)
        if chunk_content:
            meta = base_meta.copy() if base_meta else {}
            meta.update({
                "page": computed_page,
                "parent_header": current_header
            })
            chunks.append({
                "chunk_id": f"{file_id}_{id_offset + len(chunks)}",
                "content": chunk_content,
                "page": computed_page,
                "chunk_type": "text",
                "metadata": meta
            })

    # 🌟 核心调优：动态关联机制 (Context-Aware Image Anchoring)
    # 为所有的图表/图片提取锚点前后各200个字符作为其专属的 nearby_text，供开发2在构建索引时参考
    for i, c in enumerate(chunks):
        if c.get("chunk_type") == "image":
            prev_text = ""
            next_text = ""
            # 往前找最接近的纯文本块，取其最后200个字符
            for j in range(i - 1, -1, -1):
                if chunks[j].get("chunk_type") == "text":
                    prev_text = chunks[j]["content"][-200:]
                    break
            # 往后找最接近的纯文本块，取其最前200个字符
            for j in range(i + 1, len(chunks)):
                if chunks[j].get("chunk_type") == "text":
                    next_text = chunks[j]["content"][:200]
                    break
            
            context_text = f"{prev_text}\n{next_text}".strip()
            # 注入富元数据
            c["metadata"]["nearby_text"] = context_text if context_text else "无可用上下文文本"

    state["char_count"] = char_count
    return chunks


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
    
    # 构建基础元数据词典
    base_meta = {
        "source_file": filename,
        "file_type": file_type,
        "biz_domain": "default" # 预留宏观业务逻辑打标
    }

    try:
        # 1. 针对不同格式进行底层解析 [cite: 126-130, 304]
        if ext in ['.txt', '.md']:
            _pct(10, "防 OOM 惰性解析 TXT/MD 文件...")
            # 摒弃传统的全量读入，实施 O(1) 内存复杂度的块缓冲生成器模式
            BUFFER_SIZE = 2 * 1024 * 1024  # 2MB 缓冲区
            tracking_state = {"current_header": "", "char_count": 0}
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                buffer = ""
                while True:
                    chunk_raw = f.read(BUFFER_SIZE)
                    if not chunk_raw:
                        if buffer:
                            cleaned = deep_clean_text(buffer)
                            # 注入 Markdown 标题以供提取 parent_header
                            if ext == '.txt':
                                cleaned = inject_markdown_headers(cleaned)
                            chunks.extend(_chunk_text(cleaned, file_id, base_meta=base_meta, id_offset=len(chunks), state=tracking_state))
                        break
                    buffer += chunk_raw
                    # 优先在自然的段落或句号处截断缓冲
                    split_idx = max(buffer.rfind('\n\n'), buffer.rfind('。'))
                    if split_idx != -1 and len(buffer) > BUFFER_SIZE:
                        process_text = buffer[:split_idx+1]
                        cleaned = deep_clean_text(process_text)
                        
                        if ext == '.txt':
                            cleaned = inject_markdown_headers(cleaned)
                            
                        chunks.extend(_chunk_text(cleaned, file_id, base_meta=base_meta, id_offset=len(chunks), state=tracking_state))
                        buffer = buffer[split_idx+1:]
            _pct(30, f"TXT/MD 解析完成，共 {len(chunks)} 块")


        elif ext == '.docx':
            _pct(10, "解析 DOCX 文件...")
            import docx
            from docx.oxml.text.paragraph import CT_P
            from docx.oxml.table import CT_Tbl
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            docx_elements = []
            try:
                # 🛡️ 战术 1: 语义化连续提取 (保证图文表顺序一致)
                doc = docx.Document(file_path)

                # 按文档顺序遍历所有块元素 (段落和表格)
                for child in doc.element.body:
                    if isinstance(child, CT_P):
                        para = Paragraph(child, doc)
                        
                        # 收集段落内的图片，使用类似 PDF 后置统一并发的方式处理
                        blips = para._element.xpath('.//a:blip')
                        if blips:
                            import io
                            from PIL import Image
                            for blip in blips:
                                rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                                if not rId and blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}link'):
                                    rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}link')
                                if rId and rId in doc.part.related_parts:
                                    image_part = doc.part.related_parts[rId]
                                    img_bytes = image_part.blob
                                    try:
                                        with Image.open(io.BytesIO(img_bytes)) as img:
                                            # 过滤无意义的小图（如装饰线、项目符号）
                                            if img.width < 50 or img.height < 50:
                                                continue
                                            
                                            # 🌟 增强过滤机制：长宽比异常的图片多为装饰线或侧边 Logo
                                            aspect_ratio = img.width / img.height
                                            if aspect_ratio > 8 or aspect_ratio < 0.125:
                                                continue
                                                
                                            img_name = f"{file_id}_docx_{rId}.jpg"
                                            img_dir = os.path.join(settings.upload_dir, "images")
                                            os.makedirs(img_dir, exist_ok=True)
                                            img_save_path = os.path.join(img_dir, img_name).replace('\\', '/')
                                            
                                            if img.mode in ("RGBA", "P"):
                                                img = img.convert("RGB")
                                            img.save(img_save_path, format="JPEG", quality=85)
                                            
                                        docx_elements.append({
                                            "type": "image", 
                                            "content": f"\n![IMAGE_CHUNK:{img_name}]({img_save_path})\n"
                                        })
                                    except Exception as img_e:
                                        logger.warning(f"DOCX 图片处理失败，忽略该图片: {img_e}")

                        # 处理文本内容
                        text = para.text.strip()
                        if text:
                            style_name = para.style.name.lower()
                            if 'heading 1' in style_name or '标题 1' in style_name:
                                docx_elements.append({"type": "text", "content": f"# {text}"})
                            elif 'heading 2' in style_name or '标题 2' in style_name:
                                docx_elements.append({"type": "text", "content": f"## {text}"})
                            elif 'heading 3' in style_name or '标题 3' in style_name:
                                docx_elements.append({"type": "text", "content": f"### {text}"})
                            else:
                                docx_elements.append({"type": "text", "content": text})

                    elif isinstance(child, CT_Tbl):
                        table = Table(child, doc)
                        md_table = []
                        for i, row in enumerate(table.rows):
                            row_data = [cell.text.replace('\n', ' ').strip() for cell in row.cells]
                            md_table.append("| " + " | ".join(row_data) + " |")
                            if i == 0:
                                md_table.append("|" + "|".join(["---"] * len(row.cells)) + "|")
                        if md_table:
                            docx_elements.append({"type": "table", "content": "\n" + "\n".join(md_table) + "\n"})

                # 组装最终正文
                docx_md = []
                for e in docx_elements:
                    if e["content"]:
                        docx_md.append(e["content"])

                if docx_md:
                    # 将组装好的纯正 Markdown 送入层级语义切块器
                    cleaned = deep_clean_text("\n\n".join(docx_md))
                    # 注入部分未能被 heading 样式识别但也像标题的文本
                    cleaned = inject_markdown_headers(cleaned)
                    tracking_state = {"current_header": "", "char_count": 0}
                    chunks.extend(_chunk_text(cleaned, file_id, base_meta=base_meta, state=tracking_state))

            except Exception as e:
                logger.warning(f"常规解析异常，启动面向 OOM 防御的底层 XML 或 Extractous(Rust) 降级引擎: {e}")

                # 🛡️ 战术 2: 直接解析底层 ZIP/XML，绕过重量级包装类造成的大批量 Run 节点激存 OOM
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
                    for element in tree.xpath('//*[local-name()="body"]/*'):
                        if element.tag.endswith('}p') or element.tag == 'p':  # 提取段落
                            raw_text = "".join(element.itertext())
                            # 💡 核心修复：将 XML 代码引发的换行和制表符压缩为单空格，保证段落语义连贯
                            text = re.sub(r'\s+', ' ', raw_text).strip()
                            if text:
                                fallback_text.append(text)

                        elif element.tag.endswith('}tbl') or element.tag == 'tbl':  # 提取表格
                            for row in element.xpath('.//*[local-name()="tr"]'):
                                row_data = []
                                for cell in row.xpath('.//*[local-name()="tc"]'):
                                    raw_cell = "".join(cell.itertext())
                                    # 💡 同理，清洗单元格内被污染的空白字符
                                    cell_text = re.sub(r'\s+', ' ', raw_cell).strip()
                                    if cell_text:
                                        row_data.append(cell_text)
                                if row_data:
                                    fallback_text.append(" | ".join(row_data))

                    if fallback_text:
                        # 用纯净的双换行组装，完美适配下方的 _chunk_text 切块引擎
                        cleaned = deep_clean_text("\n\n".join(fallback_text))
                        cleaned = inject_markdown_headers(cleaned)
                        chunks.extend(_chunk_text(cleaned, file_id, base_meta=base_meta))
                    else:
                        raise ValueError("底层 XML 提取内容为空")

                except Exception as ex:
                    raise ValueError(f"DOCX 文件损坏严重，底层解析彻底失败: {str(ex)}")



        elif ext == '.xlsx':
            _pct(10, "高性能结构化解析 XLSX 文件...")
            import warnings

            try:
                # 🛡️ 首选：基于 Rust 绑定的 python-calamine 引擎，解决超大表内存激增 (防OOM)
                from python_calamine import CalamineWorkbook
                wb = CalamineWorkbook.from_path(file_path)
                for sheet_name in wb.sheet_names:
                    sheet_data = wb.get_sheet_by_name(sheet_name).to_python()
                    if not sheet_data or len(sheet_data) < 2: continue
                    
                    # 清洗表头
                    headers = [deep_clean_text(str(x)) if x is not None else "" for x in sheet_data[0]]
                    
                    batch_lines = []
                    start_row = 2
                    
                    for row_idx, row in enumerate(sheet_data[1:], start=2):
                        row_vals = [deep_clean_text(str(x)) if x is not None else "" for x in row]
                        # 核心防撕裂：为每行注入表头冗余，实现 "键值对级包裹 (Key-Value Wrapper)"
                        kv_pairs = [f"{h}: {v}" for h, v in zip(headers, row_vals) if v]
                        if kv_pairs:
                            batch_lines.append(" | ".join(kv_pairs))
                        
                        # 智能分块包裹 (每50行/块)，大幅减少上下文越轨
                        if len(batch_lines) >= 50 or row_idx == len(sheet_data):
                            if batch_lines:
                                chunk_content = f"## 表格区域：{sheet_name}（第 {start_row} 到 {row_idx} 行）\n" + "\n".join(batch_lines)
                                meta = base_meta.copy()
                                meta.update({"sheet": sheet_name, "start_row": start_row, "end_row": row_idx})
                                chunks.append({
                                    "chunk_id": f"{file_id}_{len(chunks)}",
                                    "content": chunk_content,
                                    "page": 0,
                                    "chunk_type": "table",
                                    "metadata": meta
                                })
                            batch_lines = []
                            start_row = row_idx + 1

                if not chunks:
                    raise ValueError("Calamine 引擎提取内容为空")

            except Exception as e:
                logger.warning(f"Calamine解析暂不可用或遭遇假表({e})，启动 Pandas C引擎降级方案...")
                import pandas as pd
                import io
                df = None
                
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
                            total_rows = len(df)
                            ROWS_PER_CHUNK = total_rows if total_rows <= 75 else 50

                            # 速度优化核心 2：彻底消灭 pandas.iterrows() 循环陷阱
                            # 直接利用底层 C 引擎进行全量字符串替换和 CSV 转换，极大降低 CPU 负载
                            df_str = df.astype(str).replace(r'\n', ' ', regex=True)

                            for start in range(0, total_rows, ROWS_PER_CHUNK):
                                end = min(start + ROWS_PER_CHUNK, total_rows)
                                block_lines = [
                                    f"## 表格工作簿：{sheet_name}（第{start + 1}-{end}行，共{total_rows}行）\n",
                                    header_row,
                                    sep_row,
                                ]

                                # C 引擎光速生成 Markdown 行
                                chunk_df = df_str.iloc[start:end]
                                raw_csv = chunk_df.to_csv(sep='|', index=False, header=False)
                                for line in raw_csv.splitlines():
                                    if line.strip():
                                        block_lines.append(f"| {line} |")

                            chunks.append({
                                "chunk_id": f"{file_id}_{len(chunks)}",
                                "content": "\n".join(block_lines),
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
                                    sorted_sep = [',', '\t']
                                    for sep in sorted_sep:
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

                    # 终极拦截与表头注入策略 (降级版)
                    if df is None or df.empty:
                        raise ValueError("终极解析失败：该文件损坏严重或为不支持的加密格式。")
                    
                    df = df.fillna("")
                    headers = [deep_clean_text(str(h)) for h in df.columns]
                    batch_lines = []
                    start_row = 1
                    
                    # 在Pandas降级流中依然保持TEDS高分的键值对转化
                    for i, row in df.iterrows():
                        kv_pairs = [f"{h}: {str(v).strip()}" for h, v in zip(headers, row.values) if str(v).strip()]
                        if kv_pairs:
                            batch_lines.append(" | ".join(kv_pairs))
                        if len(batch_lines) >= 50 or i == len(df) - 1:
                            if batch_lines:
                                chunk_content = f"## 降级表格表单区块（第 {start_row} 到 {i+1} 行）\n" + "\n".join(batch_lines)
                                meta = base_meta.copy()
                                meta.update({"start_row": start_row, "end_row": i+1})
                                chunks.append({
                                    "chunk_id": f"{file_id}_{len(chunks)}",
                                    "content": chunk_content,
                                    "page": 0,
                                    "chunk_type": "table",
                                    "metadata": meta
                                })
                            batch_lines = []
                            start_row = i + 2


        elif ext == '.pdf':
                import fitz  # PyMuPDF
                import base64
                import asyncio
                import nest_asyncio
                import tempfile
                from openai import AsyncOpenAI
                fitz.TOOLS.mupdf_display_errors(False)

                logger.info("PDF 文件：启动 3 级漏斗式多模态分流解析 (PyMuPDF -> Docling -> VLM)...")
                _pct(10, "解析 PDF 文件 (按页路由分类)...")
                try:
                    doc = fitz.open(file_path)
                    total_pages = len(doc)
                    simple_pages = []
                    docling_pages = []
                    vlm_pages = []
                    # 🌟 1. 页面路由分类 (漏斗分流核心逻辑)
                    for i in range(total_pages):
                        page = doc[i]
                        text = page.get_text("text").strip()
                        
                        has_large_image = False
                        for img in page.get_images(full=True):
                            # 高效过滤极小图与细长线
                            w, h = img[2], img[3]
                            if w < 50 or h < 50: continue
                            if w/h > 8 or h/w > 8: continue
                            
                            if w > 400 and h > 400:
                                has_large_image = True
                                break

                        has_tables = False
                        try:
                            if page.find_tables().tables:
                                has_tables = True
                        except:
                            pass

                        # 准确的分类逻辑
                        if has_large_image and len(text) < 100:
                            vlm_pages.append(i)  # 第三道防线：纯大图/扫描件
                        elif has_tables or has_large_image:
                            docling_pages.append(i)  # 第二道防线：有表格或图文混排
                        else:
                            simple_pages.append(i)  # 第一道防线：纯文本页
                    logger.info(
                        f"漏斗路由结果: 纯文本 {len(simple_pages)} 页, Docling {len(docling_pages)} 页, VLM {len(vlm_pages)} 页")

                    # 用于暂存各页解析出的 Markdown，保证最终合并时的顺序正确
                    page_markdowns = {i: "" for i in range(total_pages)}

                    # ⚡ 2. 第一道防线: PyMuPDF 原生极速读取 (占 80%)
                    if simple_pages:
                        logger.info("执行第一道防线：PyMuPDF 极速读取...")
                        for i in simple_pages:
                            blocks = doc[i].get_text("blocks")
                            page_text = ""
                            for b in blocks:
                                if b[6] == 0:  # text block
                                    bt = b[4].strip()
                                    # 处理段落内的硬回车，避免段落和句子被截断成多行
                                    bt = re.sub(r'([^\x00-\xff])\n([^\x00-\xff])', r'\1\2', bt)
                                    bt = re.sub(r'\n', '', bt)
                                    if bt:
                                        page_text += bt + "\n\n"
                            cleaned = deep_clean_text(page_text)
                            cleaned = inject_markdown_headers(cleaned)
                            page_markdowns[i] = cleaned
                        _pct(20, "第一道防线 (纯文本) 解析完成")

                    # 🚀 3. 第二道防线: Docling 处理复杂排版 (占 15%)
                    if docling_pages:
                        logger.info("执行第二道防线：Docling GPU 版面分析...")
                        # 速度优化：只将需要 Docling 的页面抽离成一个临时 PDF，避免它去读整个大文件
                        temp_doc = fitz.open()
                        for i in docling_pages:
                            temp_doc.insert_pdf(doc, from_page=i, to_page=i)
                        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
                            temp_path = tf.name
                        temp_doc.save(temp_path)
                        temp_doc.close()

                        # 🌟 核心修复：使用 Docling 新版 API 调度 GPU
                        try:
                            import torch
                            from docling.datamodel.pipeline_options import AcceleratorOptions, AcceleratorDevice
                            accel_options = AcceleratorOptions()
                            # 如果检测到 GPU，自动开启 CUDA 硬件加速
                            if torch.cuda.is_available():
                                accel_options.device = AcceleratorDevice.CUDA
                            pipeline_options.accelerator_options = accel_options
                        except ImportError:
                            # 兼容性兜底：如果没找到这个包，直接静默，Docling 底层会自动检测 GPU
                            pass

                            converter = DocumentConverter(
                                format_options={
                                    "pdf": getattr(DocumentConverter, "PdfFormatOption", dict)(
                                        pipeline_options=pipeline_options)
                                }
                            )
                            result = converter.convert(temp_path)
                            md_text = result.document.export_to_markdown()
                            if md_text and md_text.strip():
                                # Docling 会把多页合并成一个 MD，我们把它挂在这些页面的第一页上，保证大顺序不错乱
                                cleaned = deep_clean_text(md_text)
                                cleaned = inject_markdown_headers(cleaned)
                                page_markdowns[docling_pages[0]] = cleaned
                        except Exception as docling_e:
                            logger.warning(
                                f"Docling 处理失败 ({docling_e})，将 {len(docling_pages)} 页防线崩溃的数据转移给 VLM 兜底")
                            vlm_pages.extend(docling_pages)  # 完美容错：Docling 崩了交给 VLM

                        finally:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                        _pct(50, "第二道防线 (Docling) 解析完成")

                    # 🧠 4. 第三道防线: VLM 兜底纯扫描件与极端复杂图表 (占 5%)
                    if vlm_pages:
                        logger.info(f"执行第三道防线：保存纯图片/扫描件为待解析锚点并占位 ({len(vlm_pages)} 页)...")
                        for i in vlm_pages:
                            page = doc[i]
                            # 提高像素方便下游异步VLM解析更清楚
                            pix = page.get_pixmap(dpi=150)
                            img_name = f"{file_id}_p{i+1}.jpg"
                            img_dir = os.path.join(settings.upload_dir, "images")
                            os.makedirs(img_dir, exist_ok=True)
                            img_save_path = os.path.join(img_dir, img_name).replace('\\', '/')
                            
                            pix.save(img_save_path)
                            page_markdowns[i] = f"\n![IMAGE_CHUNK:{img_name}]({img_save_path})\n"
                        _pct(80, "第三道防线 (脱机图片落盘占位) 处理完成")
                    doc.close()

                    # 🧩 5. 按页码自然顺序组装所有切块 (保证血缘树不断裂)
                    tracking_state = {"current_header": "", "char_count": 0}
                    for i in range(total_pages):
                        md = page_markdowns[i]
                        if md:
                            chunks.extend(
                                _chunk_text(md, file_id, page_num=i + 1, id_offset=len(chunks), base_meta=base_meta,
                                            state=tracking_state))

                    _pct(90, "PDF 按页组合与语义切块完成")

                except Exception as ve:
                    logger.error(f"PDF 漏斗式解析彻底崩溃，强制执行全篇纯文本盲读: {ve}")
                    doc = fitz.open(file_path)
                    tracking_state = {"current_header": "", "char_count": 0}
                    for i, page in enumerate(doc):
                        blocks = page.get_text("blocks")
                        page_text = ""
                        for b in blocks:
                            if b[6] == 0:
                                bt = b[4].strip()
                                bt = re.sub(r'([^\x00-\xff])\n([^\x00-\xff])', r'\1\2', bt)
                                bt = re.sub(r'\n', '', bt)
                                if bt:
                                    page_text += bt + "\n\n"
                        cleaned = deep_clean_text(page_text)
                        cleaned = inject_markdown_headers(cleaned)
                        if cleaned and cleaned.strip():
                            chunks.extend(_chunk_text(cleaned.strip(), file_id, page_num=i + 1, id_offset=len(chunks),
                                                      base_meta=base_meta, state=tracking_state))
                    doc.close()
        # ═══════════════════════════════════════════════════════
        # 所有格式解析完毕，chunks 收集完成！
        # 下面进入统一的实体和摘要抽取阶段 (使用普通的文本大模型)
        # ═══════════════════════════════════════════════════════

        # 2. 直接返回切分结果，跳过全局大模型实体抽取以提升性能
        logger.info(f"文档切分完毕 (共 {len(chunks)} 块)。直接返回纯文本块供下游向量化...")
        _pct(90, f"文档切分完成（共 {len(chunks)} 块），准备组装结果...")

        # 废弃全量大模型盲抽，这里通过简单拼接生成一个极简摘要
        entities = []
        summary = "暂未生成摘要"
        if chunks:
            # 取第一块的前100字符作为极简摘要
            first_text = chunks[0]["content"].replace("#", "").replace("*", "").replace("\n", " ").strip()
            summary = first_text[:100] + "..." if len(first_text) > 100 else first_text


        # 3. 严格组装返回结果
        parsed_document = {
            "file_id": file_id,
            "filename": filename,
            "file_type": file_type,
            "chunks": chunks,
            "entities": entities,
            "summary": summary,
        }

        logger.success(f"✅ 文件解析完成: {filename}")
        return parsed_document

    except Exception as e:
        logger.error(f"文件解析失败: {str(e)}")
        raise RuntimeError(f"文件解析失败: {str(e)}")


# 用于暂时测试
if __name__ == "__main__":
    import json
    import os

    test_dir = r"E:\AAAjlu\a23-doc-system\测试集\pdf"
    print(f"🚀 开始执行本地真实文件测试，读取目录: {test_dir}")

    if not os.path.exists(test_dir):
        print(f"\n❌ 找不到测试集目录，请检查路径: {test_dir}")
    else:
        for idx, filename in enumerate(os.listdir(test_dir)):
            file_path = os.path.join(test_dir, filename)
            print(f"\n" + "=" * 50)
            print(f"📄 正在测试文件: {filename}")
            mock_file_id = f"test-real-{idx + 1:03d}"

            try:
                result = parse_document(file_path, mock_file_id)
                print(f"🎉 {filename} 解析成功！")

                # 移除了实体相关的打印，只保留切块数量统计
                print(f"📊 统计: 生成 {len(result.get('chunks', []))} 个块。")
                print(f"📝 文档摘要:\n{result.get('summary', '')}")

            except Exception as e:
                print(f"❌ {filename} 解析过程中发生报错: {e}")

        print(f"\n" + "=" * 50)
        print("🏁 所有测试文件处理完毕！")
