import os
import pytest
from modules.parser.document_parser import parse_document

# =====================================================================
# 🛠️ 配置区：精确指向你的真实测试集路径
# =====================================================================
TEST_DATA_DIR = r"E:\AAAjlu\a23-doc-system\测试集"

# 🌟 参数化测试数据：完全使用你截图里真实的分类和文件名！
TEST_FILES = [
    ("Excel", "2025山东省环境空气质量监测数据信息.xlsx", "xlsx"),
    ("word", "2022~2023年度人力资源和社会保障.docx", "docx"),
    ("txt", "合肥市2024年国民经济和社会发展统计公报.txt", "txt"),
    ("md", "第三次全国工业普查主要数据公报.md", "md"),
    ("pdf", "国家统计局部门预算.pdf", "pdf"),
]


@pytest.mark.parametrize("folder, filename, expected_ext", TEST_FILES)
def test_parse_document_formats(folder, filename, expected_ext):
    """
    统一测试 5 种文档格式的解析是否符合《A23技术规范文档》4.1 的 Schema 规定
    """
    # 1. 组装完整路径
    file_path = os.path.join(TEST_DATA_DIR, folder, filename)

    # 2. 容错防爆：如果本地找不到文件，主动跳过该项测试
    if not os.path.exists(file_path):
        pytest.skip(f"跳过测试：本地找不到文件 {file_path}")

    # 3. 准备 Mock 数据（模拟接口传进来的 file_id）
    mock_file_id = f"test-auto-{expected_ext}-001"

    # 4. 🚀 执行你的核心解析函数
    result = parse_document(file_path, mock_file_id)

    # =====================================================================
    # 🎯 核心断言区 (Assert)：严格质检输出结构
    # =====================================================================

    # 验证基础元数据是否正确
    assert result["file_id"] == mock_file_id, f"[{expected_ext}] file_id 映射错误"
    assert result["file_type"] == expected_ext, f"[{expected_ext}] 文档类型识别错误"

    # 验证大模型是否成功返回了实体和摘要
    assert "entities" in result, f"[{expected_ext}] 缺少 entities 字段"
    assert isinstance(result["entities"], list), f"[{expected_ext}] entities 必须是列表"
    assert "summary" in result, f"[{expected_ext}] 缺少 summary 字段"
    assert isinstance(result["summary"], str), f"[{expected_ext}] summary 必须是字符串"

    # 验证文本切块 (Chunks) 是否成功且符合规范
    assert "chunks" in result, f"[{expected_ext}] 缺少 chunks 字段"
    assert isinstance(result["chunks"], list), f"[{expected_ext}] chunks 必须是列表"
    assert len(result["chunks"]) > 0, f"文件 {filename} 没有解析出任何文本块！"

    # 抽查第一个 chunk 的内部结构是否绝对合法
    first_chunk = result["chunks"][0]
    assert "chunk_id" in first_chunk, "chunk 缺少 chunk_id"
    assert "content" in first_chunk, "chunk 缺少 content"
    assert len(first_chunk["content"]) > 0, "chunk 内容不能为空"
    assert "page" in first_chunk, "chunk 缺少 page 属性"