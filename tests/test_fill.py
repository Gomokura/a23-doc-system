"""测试回填功能"""
import requests
import json

BASE_URL = "http://localhost:8000"
TEMPLATE_ID = "69eb3c13-8fdc-4e12-a461-92da0b1c5dbf"
DATA_FILE_ID = "ddd271d7-6021-460f-a815-0871f4de75e6"

# 构造回填请求
fill_request = {
    "template_file_id": TEMPLATE_ID,
    "source_file_ids": [DATA_FILE_ID],
    "answers": [
        {"field_name": "国家/地区", "value": "Albania"},
        {"field_name": "大陆", "value": "Europe"},
        {"field_name": "人均GDP", "value": "5353.2"},
        {"field_name": "人口", "value": "2873457"},
        {"field_name": "每日新增数", "value": "0"},
        {"field_name": "死亡数", "value": "0"}
    ]
}

print("发送回填请求...")
print(f"模板ID: {TEMPLATE_ID}")
print(f"数据源: {DATA_FILE_ID}")
print(f"填充字段数: {len(fill_request['answers'])}")

r = requests.post(f"{BASE_URL}/fill", json=fill_request, timeout=60)
print(f"\n状态码: {r.status_code}")
result = r.json()
print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")

if r.status_code == 200 and "output_file_id" in result:
    print(f"\n✅ 回填成功!")
    print(f"输出文件ID: {result['output_file_id']}")
    print(f"下载地址: {BASE_URL}{result['download_url']}")
