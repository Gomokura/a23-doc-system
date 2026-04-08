"""
文档智能操作交互模块 - 操作指令解析器
基于自然语言处理技术，将用户指令解析为可执行的操作
支持：Word文档编辑、排版、格式调整、内容提取等操作
"""
import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from loguru import logger
from openai import OpenAI
from config import settings


# ─────────────────────────────────────────────────────────────────────────────
# 操作类型枚举
# ─────────────────────────────────────────────────────────────────────────────
class OperationType:
    """支持的操作类型"""
    # Word 文档操作
    EDIT_PARAGRAPH = "edit_paragraph"           # 编辑段落内容
    FORMAT_PARAGRAPH = "format_paragraph"       # 格式化段落
    ADD_PARAGRAPH = "add_paragraph"              # 添加段落
    DELETE_PARAGRAPH = "delete_paragraph"       # 删除段落
    EXTRACT_CONTENT = "extract_content"         # 提取内容
    GENERATE_SUMMARY = "generate_summary"       # 生成摘要
    REPLACE_TEXT = "replace_text"               # 替换文本
    
    # Excel 操作
    EDIT_CELL = "edit_cell"                     # 编辑单元格
    FORMAT_CELL = "format_cell"                 # 格式化单元格
    ADD_ROW = "add_row"                         # 添加行
    ADD_COLUMN = "add_column"                   # 添加列
    DELETE_ROW = "delete_row"                   # 删除行
    DELETE_COLUMN = "delete_column"             # 删除列
    EXTRACT_TABLE = "extract_table"             # 提取表格
    CALCULATE = "calculate"                     # 计算
    
    # 通用操作
    CONVERT_FORMAT = "convert_format"           # 格式转换
    MERGE_DOCUMENTS = "merge_documents"         # 合并文档
    SPLIT_DOCUMENT = "split_document"           # 拆分文档
    UNKNOWN = "unknown"                         # 未知操作


# ─────────────────────────────────────────────────────────────────────────────
# 操作参数结构
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Operation:
    """解析后的操作对象"""
    operation_type: str
    confidence: float
    parameters: Dict[str, Any]
    original_instruction: str
    reasoning: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# 操作模式字典 - 用于快速匹配
# ─────────────────────────────────────────────────────────────────────────────
OPERATION_PATTERNS = {
    OperationType.EDIT_PARAGRAPH: [
        r"修改.*内容", r"编辑.*段落", r"把.*改成", r"将.*改为",
        r"编辑.*文字", r"修改.*文字", r"更改.*内容"
    ],
    OperationType.FORMAT_PARAGRAPH: [
        r"设置.*字体", r"修改.*字号", r"改变.*颜色",
        r"加粗.*", r"倾斜.*", r"设置.*样式",
        r".*字体.*", r".*字号.*", r".*颜色.*"
    ],
    OperationType.ADD_PARAGRAPH: [
        r"添加.*段落", r"新增.*内容", r"插入.*文字",
        r"添加.*章节", r"在.*后添加"
    ],
    OperationType.DELETE_PARAGRAPH: [
        r"删除.*段落", r"移除.*内容", r"清除.*文字"
    ],
    OperationType.EXTRACT_CONTENT: [
        r"提取.*内容", r"获取.*信息", r"查找.*数据",
        r"搜索.*内容", r"找出.*信息"
    ],
    OperationType.GENERATE_SUMMARY: [
        r"生成.*摘要", r"总结.*内容", r"概括.*要点",
        r"提炼.*主题", r"提取.*主旨", r"写.*摘要"
    ],
    OperationType.REPLACE_TEXT: [
        r"替换.*为", r"把.*替换成", r"全部替换",
        r"批量替换"
    ],
    OperationType.EDIT_CELL: [
        r"修改.*单元格", r"编辑.*表格.*内容", r"填写.*表格",
        r"把.*改成", r"将.*改为", r"设置.*单元格"
    ],
    OperationType.FORMAT_CELL: [
        r"设置.*单元格.*格式", r"修改.*单元格.*样式"
    ],
    OperationType.ADD_ROW: [
        r"添加.*行", r"新增.*数据行", r"插入.*行"
    ],
    OperationType.EXTRACT_TABLE: [
        r"提取.*表格", r"导出.*数据", r"获取.*表格",
        r"提取.*工作表", r"提取.*数据", r"提取.*内容",
        r"获取.*工作表", r"提取.*工作表"
    ],
    OperationType.CONVERT_FORMAT: [
        r"转换.*格式", r"将.*转为", r"导出.*为",
        r"另存为.*格式"
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# 意图识别与参数提取
# ─────────────────────────────────────────────────────────────────────────────
class OperationParser:
    """
    操作指令解析器
    使用规则匹配 + LLM 辅助解析
    """
    
    def __init__(self):
        self.client = None
    
    def _get_client(self) -> OpenAI:
        if self.client is None:
            self.client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url
            )
        return self.client
    
    def parse(self, instruction: str, file_type: str = "docx") -> Operation:
        """
        解析用户指令
        
        Args:
            instruction: 自然语言指令
            file_type: 文件类型 (docx/xlsx/txt)
            
        Returns:
            Operation: 解析后的操作对象
        """
        logger.info(f"[操作解析] 收到指令: {instruction}")
        
        # 1. 规则快速匹配
        matched_type, confidence = self._rule_based_match(instruction, file_type)
        
        # 2. 如果规则匹配度高，直接用规则结果
        if confidence >= 0.8:
            params = self._extract_parameters_by_rules(instruction, matched_type)
            return Operation(
                operation_type=matched_type,
                confidence=confidence,
                parameters=params,
                original_instruction=instruction,
                reasoning="规则匹配"
            )
        
        # 3. 规则匹配度低，使用 LLM 辅助解析
        operation_type, llm_confidence, llm_params, reasoning = self._llm_assisted_parse(
            instruction, file_type
        )
        
        # 4. 综合决策：取置信度更高的结果
        if llm_confidence > confidence:
            return Operation(
                operation_type=operation_type,
                confidence=llm_confidence,
                parameters=llm_params,
                original_instruction=instruction,
                reasoning=reasoning
            )
        else:
            params = self._extract_parameters_by_rules(instruction, matched_type)
            return Operation(
                operation_type=matched_type,
                confidence=confidence,
                parameters=params,
                original_instruction=instruction,
                reasoning="规则匹配"
            )
    
    def _rule_based_match(self, instruction: str, file_type: str) -> tuple:
        """
        基于规则的意图匹配
        
        Returns:
            (operation_type, confidence)
        """
        instruction_lower = instruction.lower()
        
        # 根据文件类型选择匹配模式
        relevant_patterns = {}
        if file_type == "docx":
            for op_type, patterns in OPERATION_PATTERNS.items():
                if op_type not in [OperationType.EDIT_CELL, OperationType.ADD_ROW, 
                                    OperationType.EXTRACT_TABLE, OperationType.ADD_COLUMN]:
                    relevant_patterns[op_type] = patterns
        elif file_type in ["xlsx", "xls"]:
            for op_type, patterns in OPERATION_PATTERNS.items():
                if op_type in [OperationType.EDIT_CELL, OperationType.FORMAT_CELL,
                               OperationType.ADD_ROW, OperationType.ADD_COLUMN,
                               OperationType.EXTRACT_TABLE, OperationType.CALCULATE]:
                    relevant_patterns[op_type] = patterns
        else:
            relevant_patterns = OPERATION_PATTERNS
        
        best_match = OperationType.UNKNOWN
        best_score = 0.0
        
        for op_type, patterns in relevant_patterns.items():
            for pattern in patterns:
                if re.search(pattern, instruction_lower):
                    score = len(pattern) / 20.0  # 模式越长，匹配越精确
                    if score > best_score:
                        best_score = score
                        best_match = op_type
        
        return best_match, min(best_score * 1.2, 0.95)
    
    def _extract_parameters_by_rules(self, instruction: str, operation_type: str) -> Dict:
        """
        基于规则提取操作参数
        """
        params = {}
        
        # 提取段落/位置信息
        para_match = re.search(r'第[一二三四五六七八九十\d]+[段节条章]', instruction)
        if para_match:
            params['position'] = para_match.group()
        
        # 提取具体内容
        content_match = re.search(r'把[""""](.+?)["""]', instruction)
        if content_match:
            params['old_content'] = content_match.group(1)
        
        # 提取新内容
        new_content_match = re.search(r'改成[""""](.+?)["""]', instruction)
        if new_content_match:
            params['new_content'] = new_content_match.group(1)
        else:
            new_content_match = re.search(r'改为[""""](.+?)["""]', instruction)
            if new_content_match:
                params['new_content'] = new_content_match.group(1)
        
        # 提取数值参数
        font_size_match = re.search(r'(\d+)[号点]?字', instruction)
        if font_size_match:
            params['font_size'] = int(font_size_match.group(1))
        
        # 提取格式参数
        if '加粗' in instruction:
            params['bold'] = True
        if '倾斜' in instruction or '斜体' in instruction:
            params['italic'] = True
        
        # 提取颜色
        color_map = {
            '红色': 'FF0000', '蓝色': '0000FF', '绿色': '00FF00',
            '黑色': '000000', '白色': 'FFFFFF', '黄色': 'FFFF00'
        }
        for color_name, color_code in color_map.items():
            if color_name in instruction:
                params['color'] = color_code
                break
        
        return params
    
    def _llm_assisted_parse(self, instruction: str, file_type: str) -> tuple:
        """
        LLM 辅助解析
        
        Returns:
            (operation_type, confidence, parameters, reasoning)
        """
        prompt = f"""你是一个文档操作指令解析专家。请分析用户的自然语言指令，判断用户想要执行什么操作。

支持的文档操作类型：
## Word文档操作 (docx)
- edit_paragraph: 编辑段落内容（如"把第三段改成XXX"）
- format_paragraph: 格式化段落（如"把第一段加粗"）
- add_paragraph: 添加新段落（如"在开头添加一段"）
- delete_paragraph: 删除段落（如"删除第二段"）
- extract_content: 提取内容（如"提取所有表格"、"提取段落"）
- generate_summary: 生成摘要（如"总结文档内容"）
- replace_text: 替换文本（如"把所有的A替换成B"）

## Excel操作 (xlsx)
- edit_cell: 编辑单元格（如"把A1改成100"、"修改B2为新值"）
- format_cell: 格式化单元格（如"将C列设为红色背景"）
- add_row: 添加行（如"在第3行后添加新行"）
- add_column: 添加列
- delete_row: 删除行
- delete_column: 删除列
- extract_table: 提取表格数据（如"提取工作表数据"、"获取表格内容"、"提取第一个工作表"、提取工作表）
- calculate: 数据计算（如"计算A��总和"）

## 通用操作
- convert_format: 格式转换
- unknown: 无法识别的操作

请返回JSON格式：
{{
    "operation_type": "操作类型",
    "confidence": 0.0-1.0的置信度,
    "parameters": {{}},
    "reasoning": "判断理由"
}}

用户指令：{instruction}
文件类型：{file_type}

请直接输出JSON，不要有其他内容："""
        
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=500,
            )
            
            raw = response.choices[0].message.content or "{}"

            # 清理 JSON 响应
            raw = re.sub(r'^```json\n?|```$', '', raw, flags=re.MULTILINE).strip()
            result = json.loads(raw)
            
            return (
                result.get("operation_type", OperationType.UNKNOWN),
                float(result.get("confidence", 0.5)),
                result.get("parameters", {}),
                result.get("reasoning", "LLM解析")
            )
            
        except Exception as e:
            logger.warning(f"LLM辅助解析失败: {e}")
            return OperationType.UNKNOWN, 0.0, {}, "解析失败"


# ─────────────────────────────────────────────────────────────────────────────
# 单例访问
# ─────────────────────────────────────────────────────────────────────────────
_parser_instance: Optional[OperationParser] = None


def get_operation_parser() -> OperationParser:
    """获取解析器单例"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = OperationParser()
    return _parser_instance


def parse_operation(instruction: str, file_type: str = "docx") -> Operation:
    """快捷解析函数"""
    parser = get_operation_parser()
    return parser.parse(instruction, file_type)
