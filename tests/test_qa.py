"""测试智能问答功能"""
import requests
import json

BASE_URL = "http://localhost:8000"
FILE_ID = "ddd271d7-6021-460f-a815-0871f4de75e6"

def test_ask(question, file_ids=None):
    payload = {"query": question}
    if file_ids:
        payload["file_ids"] = file_ids
    print(f"\n{'='*60}")
    print(f"问题: {question}")
    print(f"文件: {file_ids}")
    r = requests.post(f"{BASE_URL}/ask", json=payload, timeout=120)
    print(f"状态码: {r.status_code}")
    data = r.json()
    if "answer" in data:
        print(f"回答: {data['answer']}")
        if data.get("sources"):
            print(f"来源数量: {len(data['sources'])}")
            print(f"第一个来源片段: {data['sources'][0]['content'][:200]}")
    else:
        print(f"原始响应: {json.dumps(data, ensure_ascii=False, indent=2)}")

if __name__ == "__main__":
    # 先检查文件状态
    r = requests.get(f"{BASE_URL}/files")
    files = r.json().get("files", [])
    print("已索引文件列表:")
    for f in files:
        print(f"  - {f['filename']} | {f['file_id']} | status={f['status']} | chunks={f['chunk_count']}")

    # 测试问答
    test_ask("这个数据集里有几个国家？", [FILE_ID])
    test_ask("数据集包含哪些字段或列？", [FILE_ID])
    test_ask("中国的新冠死亡数据是多少？", [FILE_ID])
