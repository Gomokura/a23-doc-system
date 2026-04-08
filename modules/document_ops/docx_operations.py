"""
文档智能操作交互模块 - Word 文档操作实现
支持：段落编辑、格式调整、内容提取、摘要生成等操作
"""
import os
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from loguru import logger
from openai import OpenAI
from config import settings

try:
    from docx import Document
    from docx.shared import Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# 中文数字转换
# ─────────────────────────────────────────────────────────────────────────────
def chinese_to_number(text: str) -> Optional[int]:
    """将中文数字转换为阿拉伯数字"""
    cn_map = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '第一': 1, '第二': 2, '第三': 3, '第四': 4, '第五': 5,
        '第六': 6, '第七': 7, '第八': 8, '第九': 9, '第十': 10,
        '第1': 1, '第2': 2, '第3': 3, '第4': 4, '第5': 5,
        '第6': 6, '第7': 7, '第8': 8, '第9': 9, '第10': 10,
    }
    
    # 直接匹配
    if text in cn_map:
        return cn_map[text]
    
    # 匹配 "第X段/节/条"
    match = re.match(r'第([一二三四五六七八九十\d]+)[段节条章]', text)
    if match:
        num_text = match.group(1)
        if num_text in cn_map:
            return cn_map[num_text]
        try:
            return int(num_text)
        except:
            pass
    
    # 匹配 "十X" 或 "X十" 格式
    if text.startswith('十'):
        try:
            return 10 + cn_map.get(text[1], 0)
        except:
            return 10
    elif text.endswith('十'):
        try:
            return cn_map.get(text[0], 0) * 10
        except:
            return 10
    
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Word 文档操作类
# ─────────────────────────────────────────────────────────────────────────────
class WordDocumentOperations:
    """
    Word 文档操作类
    提供基于自然语言指令的文档编辑功能
    """
    
    def __init__(self, file_path: str):
        if not DOCX_AVAILABLE:
            raise ImportError("python-docx 未安装，请运行: pip install python-docx")
        
        self.file_path = file_path
        self.doc = Document(file_path)
        self._paragraphs = None  # 缓存
        self._tables = None  # 缓存
    
    def _get_paragraphs(self) -> List:
        """获取所有段落（带缓存）"""
        if self._paragraphs is None:
            self._paragraphs = [p for p in self.doc.paragraphs if p.text.strip()]
        return self._paragraphs
    
    def _get_tables(self) -> List:
        """获取所有表格（带缓存）"""
        if self._tables is None:
            self._tables = list(self.doc.tables)
        return self._tables
    
    def _find_paragraph_by_position(self, position: str) -> Tuple[int, Any]:
        """
        根据位置描述找到对应的段落
        
        Args:
            position: 位置描述，如 "第3段"、"第一段"、"开头"、"结尾"
            
        Returns:
            (paragraph_index, paragraph_object)
        """
        paras = self._get_paragraphs()
        
        if not paras:
            return -1, None
        
        # 开头/开头
        if '开头' in position or '第一' in position:
            return 0, paras[0]
        
        # 结尾/末尾
        if '结尾' in position or '末尾' in position:
            return len(paras) - 1, paras[-1]
        
        # 提取数字
        para_num = chinese_to_number(position)
        if para_num is not None and para_num > 0:
            idx = para_num - 1  # 转0索引
            if idx < len(paras):
                return idx, paras[idx]
        
        return -1, None
    
    # ─────────────────────────────────────────────────────────────────────────
    # 基础操作：读取
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_all_content(self) -> List[Dict[str, Any]]:
        """获取文档所有内容（带结构信息）"""
        result = []
        
        # 添加段落信息
        for idx, para in enumerate(self.doc.paragraphs):
            text = para.text.strip()
            if text:
                result.append({
                    'type': 'paragraph',
                    'index': idx,
                    'content': text,
                    'style': para.style.name if para.style else 'Normal',
                    'is_heading': bool(re.match(r'^#{1,6}\s', text)) or 
                                  bool(re.search(r'标题|heading', para.style.name, re.I)) if para.style else False
                })
        
        # 添加表格信息
        for idx, table in enumerate(self._get_tables()):
            result.append({
                'type': 'table',
                'index': idx,
                'rows': len(table.rows),
                'cols': len(table.columns) if table.rows else 0,
                'preview': self._table_to_text(table, max_rows=3)
            })
        
        return result
    
    def _table_to_text(self, table, max_rows: int = 3) -> str:
        """将表格转换为文本预览"""
        lines = []
        for i, row in enumerate(table.rows):
            if i >= max_rows:
                lines.append("...")
                break
            row_text = " | ".join([cell.text.strip()[:20] for cell in row.cells])
            lines.append(row_text)
        return "\n".join(lines)
    
    # ─────────────────────────────────────────────────────────────────────────
    # 操作：编辑段落
    # ─────────────────────────────────────────────────────────────────────────
    
    def edit_paragraph(self, position: str, new_content: str, old_content: str = None) -> Dict[str, Any]:
        """
        编辑指定段落的内容
        
        Args:
            position: 段落位置描述
            new_content: 新内容
            old_content: 要替换的旧内容（可选）
            
        Returns:
            操作结果
        """
        paras = self._get_paragraphs()
        if not paras:
            return {'success': False, 'message': '文档中没有可编辑的段落'}
        
        # 找到目标段落
        idx, para = self._find_paragraph_by_position(position)
        
        if para is None:
            return {'success': False, 'message': f'未找到"{position}"对应的段落'}
        
        old_text = para.text
        
        # 如果指定了旧内容，精确替换
        if old_content:
            if old_content in old_text:
                new_text = old_text.replace(old_content, new_content)
                para.text = new_text
                self.doc.save(self.file_path)
                return {
                    'success': True,
                    'message': f'已替换第{idx+1}段中的内容',
                    'old_content': old_content,
                    'new_content': new_content
                }
            else:
                return {
                    'success': False,
                    'message': f'未在第{idx+1}段找到"{old_content}"'
                }
        else:
            # 替换整个段落
            para.text = new_content
            self.doc.save(self.file_path)
            return {
                'success': True,
                'message': f'已修改第{idx+1}段内容',
                'old_content': old_text[:50] + ('...' if len(old_text) > 50 else ''),
                'new_content': new_content
            }
    
    def add_paragraph(self, position: str, content: str, style: str = 'Normal') -> Dict[str, Any]:
        """
        添加新段落
        
        Args:
            position: 添加位置（"开头"、"结尾"、"第X段后"）
            content: 段落内容
            style: 样式名称
            
        Returns:
            操作结果
        """
        try:
            # 找到参考段落
            ref_idx = 0
            if '后' in position:
                num = chinese_to_number(position)
                if num:
                    ref_idx = num
            elif '结尾' in position or '末尾' in position:
                ref_idx = len(self._get_paragraphs())
            
            # 创建新段落
            new_para = self.doc.add_paragraph(content)
            if style and style != 'Normal':
                new_para.style = self.doc.styles[style]
            
            self.doc.save(self.file_path)
            
            return {
                'success': True,
                'message': f'已添加新段落',
                'content': content
            }
        except Exception as e:
            return {'success': False, 'message': f'添加段落失败: {str(e)}'}
    
    def delete_paragraph(self, position: str) -> Dict[str, Any]:
        """
        删除指定段落
        
        Args:
            position: 段落位置
            
        Returns:
            操作结果
        """
        paras = self._get_paragraphs()
        idx, para = self._find_paragraph_by_position(position)
        
        if para is None:
            return {'success': False, 'message': f'未找到"{position}"对应的段落'}
        
        old_content = para.text
        
        # 获取段落所在的父元素并删除
        para_element = para._element
        para_element.getparent().remove(para_element)
        
        self.doc.save(self.file_path)
        
        return {
            'success': True,
            'message': f'已删除第{idx+1}段',
            'deleted_content': old_content[:50] + ('...' if len(old_content) > 50 else '')
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # 操作：格式调整
    # ─────────────────────────────────────────────────────────────────────────
    
    def format_paragraph(self, position: str, **format_params) -> Dict[str, Any]:
        """
        格式化段落
        
        Args:
            position: 段落位置
            **format_params: 格式参数（bold, italic, font_size, color, alignment等）
            
        Returns:
            操作结果
        """
        idx, para = self._find_paragraph_by_position(position)
        if para is None:
            return {'success': False, 'message': f'未找到"{position}"对应的段落'}
        
        changed = []
        
        # 加粗
        if format_params.get('bold'):
            for run in para.runs:
                run.bold = True
            changed.append('加粗')
        
        # 倾斜
        if format_params.get('italic'):
            for run in para.runs:
                run.italic = True
            changed.append('倾斜')
        
        # 字号
        font_size = format_params.get('font_size')
        if font_size:
            for run in para.runs:
                run.font.size = Pt(font_size)
            changed.append(f'字号{font_size}')
        
        # 颜色
        color = format_params.get('color')
        if color:
            rgb = RGBColor.from_string(color)
            for run in para.runs:
                run.font.color.rgb = rgb
            changed.append(f'颜色#{color}')
        
        # 对齐
        alignment = format_params.get('alignment')
        if alignment:
            align_map = {
                'left': WD_ALIGN_PARAGRAPH.LEFT,
                'center': WD_ALIGN_PARAGRAPH.CENTER,
                'right': WD_ALIGN_PARAGRAPH.RIGHT,
                '两端对齐': WD_ALIGN_PARAGRAPH.JUSTIFY,
            }
            para.alignment = align_map.get(alignment, WD_ALIGN_PARAGRAPH.LEFT)
            changed.append(f'对齐方式:{alignment}')
        
        # 字体
        font_name = format_params.get('font_name')
        if font_name:
            for run in para.runs:
                run.font.name = font_name
            changed.append(f'字体:{font_name}')
        
        if changed:
            self.doc.save(self.file_path)
            return {
                'success': True,
                'message': f'已对第{idx+1}段设置: {", ".join(changed)}',
                'format_changes': changed
            }
        else:
            return {'success': True, 'message': '未指定任何格式修改'}
    
    # ─────────────────────────────────────────────────────────────────────────
    # 操作：内容提取
    # ─────────────────────────────────────────────────────────────────────────
    
    def extract_content(self, extract_type: str = 'all') -> Dict[str, Any]:
        """
        提取文档内容
        
        Args:
            extract_type: 提取类型 (all, paragraphs, tables, headings)
            
        Returns:
            提取的内容
        """
        if extract_type == 'all' or extract_type == 'paragraphs':
            paragraphs = [p.text.strip() for p in self._get_paragraphs() if p.text.strip()]
            if extract_type == 'paragraphs':
                return {'success': True, 'content': paragraphs}
        
        if extract_type == 'all' or extract_type == 'tables':
            tables = []
            for table in self._get_tables():
                table_data = []
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    table_data.append(row_data)
                tables.append(table_data)
            if extract_type == 'tables':
                return {'success': True, 'content': tables}
        
        if extract_type == 'all' or extract_type == 'headings':
            headings = []
            for para in self.doc.paragraphs:
                style = para.style.name.lower() if para.style else ''
                if 'heading' in style or '标题' in style:
                    headings.append({
                        'level': style,
                        'content': para.text.strip()
                    })
            if extract_type == 'headings':
                return {'success': True, 'content': headings}
        
        # 返回全部内容
        return {
            'success': True,
            'content': {
                'paragraphs': [p.text.strip() for p in self._get_paragraphs()],
                'tables': [
                    [[cell.text.strip() for cell in row.cells] for row in table.rows]
                    for table in self._get_tables()
                ],
                'headings': [
                    {'level': p.style.name, 'content': p.text.strip()}
                    for p in self.doc.paragraphs
                    if p.style and ('heading' in p.style.name.lower() or '标题' in p.style.name)
                ]
            }
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # 操作：替换文本
    # ─────────────────────────────────────────────────────────────────────────
    
    def replace_text(self, old_text: str, new_text: str, replace_all: bool = True) -> Dict[str, Any]:
        """
        替换文本
        
        Args:
            old_text: 要替换的文本
            new_text: 替换为的文本
            replace_all: 是否全部替换
            
        Returns:
            操作结果
        """
        count = 0
        
        # 替换段落中的文本
        for para in self.doc.paragraphs:
            if old_text in para.text:
                para.text = para.text.replace(old_text, new_text)
                count += 1
                if not replace_all:
                    break
        
        # 替换表格中的文本
        for table in self._get_tables():
            for row in table.rows:
                for cell in row.cells:
                    if old_text in cell.text:
                        cell.text = cell.text.replace(old_text, new_text)
                        count += 1
                        if not replace_all:
                            break
        
        if count > 0:
            self.doc.save(self.file_path)
            return {
                'success': True,
                'message': f'已替换 {count} 处',
                'replaced_count': count
            }
        else:
            return {
                'success': False,
                'message': f'未找到"{old_text}"',
                'replaced_count': 0
            }
    
    # ─────────────────────────────────────────────────────────────────────────
    # 操作：生成摘要
    # ─────────────────────────────────────────────────────────────────────────
    
    def generate_summary(self, max_length: int = 500) -> Dict[str, Any]:
        """
        使用 LLM 生成文档摘要
        
        Args:
            max_length: 摘要最大字符数
            
        Returns:
            生成的摘要
        """
        # 收集文档内容
        paragraphs = [p.text.strip() for p in self._get_paragraphs() if p.text.strip()]
        content = "\n\n".join(paragraphs[:20])  # 取前20段
        
        if not content.strip():
            return {'success': False, 'message': '文档内容为空'}
        
        # 调用 LLM 生成摘要
        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        
        prompt = f"""请阅读以下文档内容，生成一个简洁的摘要。

要求：
1. 摘要长度不超过 {max_length} 字
2. 包含文档的核心主题和关键信息
3. 语言简洁明了

文档内容：
{content[:3000]}

请直接输出摘要："""
        
        try:
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=max_length // 2,
            )
            
            summary = response.choices[0].message.content.strip()
            
            return {
                'success': True,
                'summary': summary,
                'source_paragraphs': len(paragraphs)
            }
            
        except Exception as e:
            logger.error(f"生成摘要失败: {e}")
            return {'success': False, 'message': f'生成摘要失败: {str(e)}'}
    
    def close(self):
        """关闭文档"""
        self.doc = None
        self._paragraphs = None
        self._tables = None


# ─────────────────────────────────────────────────────────────────────────────
# 快捷函数
# ─────────────────────────────────────────────────────────────────────────────
def word_edit_paragraph(file_path: str, position: str, new_content: str, 
                        old_content: str = None) -> Dict[str, Any]:
    """编辑 Word 段落"""
    ops = WordDocumentOperations(file_path)
    try:
        return ops.edit_paragraph(position, new_content, old_content)
    finally:
        ops.close()


def word_format_paragraph(file_path: str, position: str, **format_params) -> Dict[str, Any]:
    """格式化 Word 段落"""
    ops = WordDocumentOperations(file_path)
    try:
        return ops.format_paragraph(position, **format_params)
    finally:
        ops.close()


def word_extract_content(file_path: str, extract_type: str = 'all') -> Dict[str, Any]:
    """提取 Word 内容"""
    ops = WordDocumentOperations(file_path)
    try:
        return ops.extract_content(extract_type)
    finally:
        ops.close()


def word_generate_summary(file_path: str, max_length: int = 500) -> Dict[str, Any]:
    """生成 Word 摘要"""
    ops = WordDocumentOperations(file_path)
    try:
        return ops.generate_summary(max_length)
    finally:
        ops.close()


def word_replace_text(file_path: str, old_text: str, new_text: str, 
                     replace_all: bool = True) -> Dict[str, Any]:
    """替换 Word 文本"""
    ops = WordDocumentOperations(file_path)
    try:
        return ops.replace_text(old_text, new_text, replace_all)
    finally:
        ops.close()
