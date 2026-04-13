"""通过 HTTP API 测试智能回填端到端流程"""
import sys
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

payload = {
    "template_file_id": "69eb3c13-8fdc-4e12-a461-92da0b1c5dbf",
    "source_file_ids": ["ddd271d7-6021-460f-a815-0871f4de75e6"],
    "max_rows": 5
}

print("=== 测试 POST /fill (智能回填) ===")
print(f"请求体: {json.dumps(payload, ensure_ascii=False, indent=2)}")

try:
    resp = requests.post(f"{BASE_URL}/fill", json=payload, timeout=120)
    print(f"\n状态码: {resp.status_code}")
    print(f"响应: {resp.text}")

    if resp.status_code == 200:
        data = resp.json()
        output_id = data.get("output_file_id")
        download_url = data.get("download_url")
        print(f"\n✅ 回填成功！")
        print(f"output_file_id: {output_id}")
        print(f"download_url: {download_url}")

        # 下载结果文件
        print(f"\n=== 测试 GET {download_url} ===")
        dl_resp = requests.get(f"{BASE_URL}{download_url}", timeout=30)
        print(f"下载状态码: {dl_resp.status_code}")
        if dl_resp.status_code == 200:
            save_path = r"D:\桌面\a23-doc-system\outputs\api_test_result.xlsx"
            with open(save_path, "wb") as f:
                f.write(dl_resp.content)
            print(f"文件已保存: {save_path}")

            # 读取并显示内容
            import pandas as pd
            df = pd.read_excel(save_path)
            print(f"\n回填结果 ({len(df)} 行):")
            print(df.to_string(index=False))
        else:
            print(f"下载失败: {dl_resp.text}")
    else:
        print(f"\n❌ 回填失败: {resp.text}")

except requests.exceptions.ConnectionError:
    print("❌ 无法连接服务器，请确认后端已启动 (uvicorn main:app --reload)")
except Exception as e:
    print(f"❌ 异常: {e}")
    import traceback
    traceback.print_exc()
