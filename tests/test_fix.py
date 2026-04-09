"""测试修复后的全库检索文件名"""
import urllib.request as u
import json, sys

def test(query, file_ids):
    d = json.dumps({"query": query, "file_ids": file_ids}).encode("utf-8")
    req = u.Request("http://localhost:8000/ask", d, {"Content-Type": "application/json"})
    try:
        resp = u.urlopen(req, timeout=40)
        res = json.loads(resp.read())
        sources = res.get("sources", [])
        print(f"[query={query!r}, file_ids={file_ids}]")
        print(f"  answer: {res.get('answer','')[:80]}")
        print(f"  sources({len(sources)}):")
        for s in sources[:3]:
            print(f"    - {s.get('source_file','')} (page={s.get('page','')})")
        print(f"  confidence: {res.get('confidence')}")
    except Exception as e:
        print(f"ERROR: {e}")
    print()

# 全库检索（file_ids=[]）
test("COVID全球数据", [])

# 看文件列表
d2 = u.urlopen("http://localhost:8000/files", timeout=10)
files = json.loads(d2.read()).get("files", [])
print("=== 文件列表 ===")
for f in files:
    print(f"  {f['filename']} status={f['status']} id={f['file_id'][:8]}")
