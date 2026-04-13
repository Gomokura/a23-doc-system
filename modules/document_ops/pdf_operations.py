"""
文档智能操作交互模块 - PDF 文档操作实现
支持：文本提取、页面提取、摘要生成等操作
"""
import os
import re
from typing import Dict, List, Optional, Any
from loguru import logger

try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


class PDFDocumentOperations:
    """
    PDF 文档操作类
    提供基于自然语言的 PDF 内容提取功能
    """

    def __init__(self, file_path: str):
        if not PDF_AVAILABLE:
            raise ImportError("PyMuPDF 未安装，请运行: pip install pymupdf")

        self.file_path = file_path
        self.doc = fitz.open(file_path)

    def get_metadata(self) -> Dict[str, Any]:
        """获取 PDF 元数据"""
        try:
            meta = self.doc.metadata
            return {
                'success': True,
                'title': meta.get('title', ''),
                'author': meta.get('author', ''),
                'subject': meta.get('subject', ''),
                'creator': meta.get('creator', ''),
                'producer': meta.get('producer', ''),
                'pages': len(self.doc),
            }
        except Exception as e:
            return {'success': False, 'message': f'获取元数据失败: {str(e)}'}

    def extract_text(self, page_start: int = None, page_end: int = None) -> Dict[str, Any]:
        """
        提取 PDF 文本内容

        Args:
            page_start: 起始页（从1开始），None表示从头开始
            page_end: 结束页，None表示到最后一页

        Returns:
            提取的文本内容
        """
        try:
            total_pages = len(self.doc)
            start = (page_start - 1) if page_start else 0
            end = page_end if page_end else total_pages

            # 边界处理
            start = max(0, min(start, total_pages - 1))
            end = max(start + 1, min(end, total_pages))

            text_blocks = []
            for page_num in range(start, end):
                page = self.doc[page_num]
                text = page.get_text("text").strip()
                if text:
                    text_blocks.append(f"--- 第 {page_num + 1} 页 ---\n{text}")

            full_text = "\n\n".join(text_blocks)

            return {
                'success': True,
                'text': full_text,
                'page_start': start + 1,
                'page_end': end,
                'total_pages': total_pages,
                'char_count': len(full_text)
            }
        except Exception as e:
            return {'success': False, 'message': f'提取文本失败: {str(e)}'}

    def extract_page(self, page_num: int) -> Dict[str, Any]:
        """
        提取指定页面的完整内容

        Args:
            page_num: 页码（从1开始）

        Returns:
            页面内容
        """
        try:
            if page_num < 1 or page_num > len(self.doc):
                return {'success': False, 'message': f'页码超出范围 (1-{len(self.doc)})'}

            page = self.doc[page_num - 1]
            text = page.get_text("text").strip()

            # 获取页面中的图片信息
            images = []
            for img in page.get_images(full=True):
                images.append({
                    'width': img[2],
                    'height': img[3],
                    'xref': img[0]
                })

            # 获取表格信息（如果有）
            tables = []
            try:
                table_instances = page.find_tables().tables
                for tbl in table_instances:
                    tables.append({
                        'bbox': tbl.bbox,
                        'rows': len(tbl.extract()),
                        'cols': len(tbl.extract()[0]) if tbl.extract() else 0
                    })
            except Exception:
                pass

            return {
                'success': True,
                'page_num': page_num,
                'text': text,
                'images_count': len(images),
                'tables_count': len(tables),
                'char_count': len(text)
            }
        except Exception as e:
            return {'success': False, 'message': f'提取页面失败: {str(e)}'}

    def extract_by_keyword(self, keyword: str, context_chars: int = 200) -> Dict[str, Any]:
        """
        根据关键词搜索并提取包含该关键词的段落

        Args:
            keyword: 搜索关键词
            context_chars: 上下文字符数

        Returns:
            匹配的段落列表
        """
        try:
            results = []
            for page_num in range(len(self.doc)):
                page = self.doc[page_num]
                text = page.get_text("text")

                if keyword in text:
                    # 找到关键词位置
                    start = 0
                    while True:
                        pos = text.find(keyword, start)
                        if pos == -1:
                            break

                        # 提取上下文
                        context_start = max(0, pos - context_chars)
                        context_end = min(len(text), pos + len(keyword) + context_chars)
                        context = text[context_start:context_end]

                        # 添加省略号标记
                        prefix = "..." if context_start > 0 else ""
                        suffix = "..." if context_end < len(text) else ""

                        results.append({
                            'page': page_num + 1,
                            'keyword': keyword,
                            'context': prefix + context + suffix,
                            'position': pos
                        })

                        start = pos + 1

            return {
                'success': True,
                'keyword': keyword,
                'matches': len(results),
                'results': results
            }
        except Exception as e:
            return {'success': False, 'message': f'搜索失败: {str(e)}'}

    def get_outline(self) -> Dict[str, Any]:
        """
        获取 PDF 大纲（书签/目录）

        Returns:
            大纲结构
        """
        try:
            outline = []
            for item in self.doc.get_toc():
                level = item[0]
                title = item[1]
                page = item[2] if len(item) > 2 else 0
                outline.append({
                    'level': level,
                    'title': title,
                    'page': page
                })

            return {
                'success': True,
                'outline': outline,
                'count': len(outline)
            }
        except Exception as e:
            return {'success': False, 'message': f'获取大纲失败: {str(e)}'}

    def close(self):
        """关闭 PDF 文档"""
        if self.doc:
            self.doc.close()
            self.doc = None


# ─────────────────────────────────────────────────────────────────────────────
# 便捷函数
# ─────────────────────────────────────────────────────────────────────────────
def pdf_extract_text(file_path: str, page_start: int = None, page_end: int = None) -> Dict[str, Any]:
    """提取 PDF 文本内容"""
    ops = PDFDocumentOperations(file_path)
    try:
        return ops.extract_text(page_start, page_end)
    finally:
        ops.close()


def pdf_extract_page(file_path: str, page_num: int) -> Dict[str, Any]:
    """提取指定页面"""
    ops = PDFDocumentOperations(file_path)
    try:
        return ops.extract_page(page_num)
    finally:
        ops.close()


def pdf_get_outline(file_path: str) -> Dict[str, Any]:
    """获取 PDF 大纲"""
    ops = PDFDocumentOperations(file_path)
    try:
        return ops.get_outline()
    finally:
        ops.close()
