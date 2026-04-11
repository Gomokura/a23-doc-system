import os
import sys
import psutil
import time
import pytest
from traceback import format_exc

# 💡 动态获取项目根目录，彻底告别写死的绝对路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from modules.parser.document_parser import parse_document

# ⚙️ 配置区域：修改这里来切换要测试的子文件夹
# 例如: "Excel", "word", "pdf", "txt", "md"
TARGET_SUBDIR = "pdf"

def get_test_files(subdir):
    """获取指定目录下所有受支持的文件"""
    folder_path = os.path.join(PROJECT_ROOT, "测试集", subdir)
    if not os.path.exists(folder_path):
        return []

    supported_exts = {'.pdf', '.docx', '.xlsx', '.txt', '.md'}
    files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if os.path.splitext(f)[1].lower() in supported_exts
    ]
    return files

# 动态生成测试列表
TEST_FILES = get_test_files(TARGET_SUBDIR)


@pytest.mark.parametrize("file_path", TEST_FILES)
def test_extreme_chunking_and_oom_protection(file_path):
    """
    针对目录下的每个文件执行极限压力与保真度测试
    """
    # 再次检查文件是否存在（防止扫描后被移动）
    if not os.path.exists(file_path):
        pytest.skip(f"文件未找到: {file_path}")

    filename = os.path.basename(file_path)
    print(f"\n🚀 [正在测试] {filename}")
    print("=" * 80)

    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss / 1024 / 1024

    start_time = time.time()

    try:
        # 生成唯一的file_id
        mock_file_id = f"test_{TARGET_SUBDIR.lower()}_{int(time.time()) % 10000}"

        # 调用解析器
        parsed_data = parse_document(file_path, file_id=mock_file_id)
        chunks = parsed_data.get("chunks", [])

        end_time = time.time()
        end_mem = process.memory_info().rss / 1024 / 1024

        if not chunks:
            pytest.fail("❌ 警告：切块数量为 0！文件可能遭遇解析失败或不支持。")

        print(f"✅ 解析成功! 总耗时: {end_time - start_time:.2f} 秒")
        print(f"⚡ 解析后常驻内存 (RSS): {end_mem:.2f} MB (净增: {end_mem - start_mem:.2f} MB)")

        # 1. 基础分块统计
        lengths = [len(c["content"]) for c in chunks]
        avg_len = sum(lengths) / len(lengths)
        micro_chunks = [l for l in lengths if l < 50]

        print(f"\n📊 语义切块分布统计:")
        print(f" - 产出区块数: {len(chunks)} 块")
        print(f" - 平均字符数: {avg_len:.0f} 字符/块")
        print(f" - 碎片化率 (极短碎句 < 50字): {len(micro_chunks)} 块 ({len(micro_chunks) / len(chunks) * 100:.1f}%)")

        if len(micro_chunks) / len(chunks) > 0.15:
            print("   ⚠️ 碎片警告：递归切块或换行符清洗缺陷，导致语法树断裂！")

        print(f"\n🔍 宏观元数据验证 (Metadata Enrichment):")
        meta_keys = set()
        has_headers = False
        has_pages = False
        for c in chunks:
            meta_keys.update(c.get("metadata", {}).keys())
            if c.get("metadata", {}).get("parent_header"):
                has_headers = True
            if c.get("metadata", {}).get("page", 0) > 0:
                has_pages = True
                
        print(f" - 区块携带标签: {', '.join(meta_keys) if meta_keys else '无'}")
        print(f" - 章节标题提取 (parent_header): {'✅ 成功追踪' if has_headers else '⚠️ 未提取到显著标题'}")
        print(f" - 页码估算提取 (page): {'✅ 成功估算/获取' if has_pages else '⚠️ 未提取有效页码'}")

        # --- 📦 结构保真度质检 (全量/宽限检查) ---
        print("\n🧪 结构保真度详细质检:")

        # 设定抽样规则：如果块数少于 5 块则全部打印，否则打印首、中、尾。
        if len(chunks) <= 5:
            sample_indices = list(range(len(chunks)))
        else:
            sample_indices = [0, len(chunks) // 4, len(chunks) // 2, (len(chunks) * 3) // 4, len(chunks) - 1]

        # 移除重复项并排序
        sample_indices = sorted(list(set(i for i in sample_indices if i < len(chunks))))

        for idx in sample_indices:
            chunk = chunks[idx]
            text = chunk['content']
            meta = chunk['metadata']

            print(f"\n📂 [区块 ID: {chunk['chunk_id']}] | 索引: {idx} | 字符数: {len(text)}")
            print(f"标签详情: {meta}")
            print("┏" + "━" * 80)

            # 尽可能多地输出内容：
            # 如果内容超过 3000 字，为了防止控制台卡死，还是做个极高上限的截断
            if len(text) > 3000:
                print(text[:1500])
                print("\n\n   ... [⚠️ 内容过长，已截断剩余 %d 字符] ... \n\n" % (len(text) - 1500))
                print(text[-500:])
            else:
                # 直接输出完整内容
                print(text)

            print("┗" + "━" * 80)

            # TEDS 语义完整性诊断
            if "|" in text:
                if ("\n" not in text or "---" not in text) and ":" not in text:
                    print("   ⚠️ TEDS 警告: 发现表格符号但缺乏 Markdown 结构或 Key-Value 格式，可能存在断裂！")
                elif "## 表格" in text or "## 降级" in text:
                    print("   ✨ 结构校验: 成功识别到表格语义包裹。")

    except Exception as e:
        print(f"❌ 解析管道崩溃:\n{format_exc()}")
        pytest.fail(f"解析管道崩溃: {e}")