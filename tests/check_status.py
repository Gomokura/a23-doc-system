"""检查ChromaDB状态和SQLite状态"""
import sys
sys.path.insert(0, r'D:\桌面\a23-doc-system')

import chromadb
from config import settings

# ChromaDB
client = chromadb.PersistentClient(path=settings.chroma_path)
col = client.get_collection('documents')
print(f"ChromaDB 总文档数: {col.count()}")

all_meta = col.get(limit=500, include=['metadatas'])
file_ids = {}
for m in all_meta['metadatas']:
    fid = m.get('file_id')
    src = m.get('source_file', '')
    if fid not in file_ids:
        file_ids[fid] = {'count': 0, 'source': src}
    file_ids[fid]['count'] += 1

print("\nChromaDB 中的文件:")
for fid, info in file_ids.items():
    print(f"  file_id={fid}  chunks={info['count']}  src={info['source']}")

# SQLite
from db.database import SessionLocal
from db.models import FileRecord
db = SessionLocal()
records = db.query(FileRecord).all()
print("\nSQLite 中的文件:")
for r in records:
    print(f"  file_id={r.file_id}  filename={r.filename}  status={r.status}  chunks={r.chunk_count}")
db.close()
