"""
重建索引脚本：
1. 清理 ChromaDB 中所有旧数据（孤立的 767b8bc2 + 错误的 ddd271d7 旧版本）
2. 用 SQLite 中正确的 file_id 重新解析并索引 COVID xlsx
"""
import sys
sys.path.insert(0, r'D:\桌面\a23-doc-system')

from loguru import logger
from config import settings
from db.database import SessionLocal
from db.models import FileRecord
from modules.parser.document_parser import parse_document
from modules.retriever.indexer import build_index, delete_index, get_bm25_records

# ── Step 1: 使用 indexer 模块的 delete_index 清理旧数据 ──
print("=" * 60)
print("Step 1: 清理旧索引...")
try:
    delete_index("767b8bc2-eb9c-47aa-a16b-1538fdd4e42f")
    print("  已删除孤立 file_id=767b8bc2...")
except Exception as e:
    print(f"  删除 767b8bc2 失败: {e}")

try:
    delete_index("ddd271d7-6021-460f-a815-0871f4de75e6")
    print("  已删除旧 file_id=ddd271d7...")
except Exception as e:
    print(f"  删除 ddd271d7 失败: {e}")

# ── Step 2: 重新解析 COVID xlsx ──
print("\n" + "=" * 60)
print("Step 2: 重新解析 COVID-19 全球数据集 xlsx...")
FILE_ID = "ddd271d7-6021-460f-a815-0871f4de75e6"
FILE_PATH = r'D:\桌面\a23-doc-system\uploads\ddd271d7-6021-460f-a815-0871f4de75e6.xlsx'

try:
    parsed = parse_document(FILE_PATH, FILE_ID)
    chunks = parsed.get('chunks', [])
    print(f"  解析完成! 生成 {len(chunks)} 个 chunks")
    print(f"  摘要: {parsed.get('summary', '')[:100]}")
    if chunks:
        print(f"  第一个 chunk 内容预览:\n{chunks[0]['content'][:300]}")
except Exception as e:
    print(f"  解析失败: {e}")
    sys.exit(1)

# ── Step 3: 重新建索引 ──
print("\n" + "=" * 60)
print("Step 3: 构建索引...")
try:
    ok = build_index(parsed, force_rebuild=True)
    if ok:
        print(f"  索引构建成功!")
        records = get_bm25_records([FILE_ID])
        print(f"  BM25 记录数: {len(records)}")
    else:
        print("  索引构建失败!")
        sys.exit(1)
except Exception as e:
    print(f"  索引构建异常: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# ── Step 4: 更新 SQLite 中的 chunk_count ──
print("\n" + "=" * 60)
print("Step 4: 更新 SQLite chunk_count...")
db = SessionLocal()
try:
    record = db.query(FileRecord).filter_by(file_id=FILE_ID).first()
    if record:
        record.chunk_count = len(chunks)
        record.status = "indexed"
        db.commit()
        print(f"  已更新: filename={record.filename}, chunk_count={len(chunks)}, status=indexed")
    else:
        print("  ERROR: SQLite 中找不到该记录！")
finally:
    db.close()

print("\n" + "=" * 60)
print("全部完成! 现在可以进行智能问答了。")
print(f"COVID xlsx file_id: {FILE_ID}")
print(f"Chunks 数量: {len(chunks)}")
