"""
前端展示模块 - 负责人: 成员5
使用 Gradio Blocks 布局，通过 requests 调用后端 API
"""
import os
import requests
import gradio as gr

# 后端 Base URL，从环境变量读取，默认本地
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


def upload_and_parse(file):
    """上传文件并触发解析"""
    if file is None:
        return "请先选择文件", ""
    try:
        # 上传
        with open(file.name, "rb") as f:
            res = requests.post(f"{API_BASE}/upload", files={"file": f})
        if res.status_code != 200:
            return f"上传失败: {res.json().get('detail')}", ""
        file_id = res.json()["file_id"]

        # 提交解析
        res2 = requests.post(f"{API_BASE}/parse", json={"file_id": file_id})
        if res2.status_code not in (200, 202):
            return f"解析提交失败: {res2.json().get('detail')}", file_id

        task_id = res2.json()["task_id"]
        return f"✅ 上传成功！file_id: {file_id}\n⏳ 解析任务已提交，task_id: {task_id}", file_id
    except Exception as e:
        return f"❌ 错误: {str(e)}", ""


def check_parse_status(task_id):
    """轮询解析状态"""
    if not task_id:
        return "请先上传文件"
    try:
        res = requests.get(f"{API_BASE}/parse/status/{task_id}")
        data = res.json()
        if data["status"] == "done":
            return f"✅ 解析完成！"
        elif data["status"] == "failed":
            return f"❌ 解析失败: {data.get('error')}"
        else:
            return f"⏳ 解析中... 进度: {data.get('progress', 0)}%"
    except Exception as e:
        return f"❌ 错误: {str(e)}"


def ask_question(query, file_ids_str):
    """问答"""
    if not query:
        return "请输入问题", ""
    try:
        file_ids = [x.strip() for x in file_ids_str.split(",") if x.strip()] if file_ids_str else []
        res = requests.post(f"{API_BASE}/ask", json={"query": query, "file_ids": file_ids})
        if res.status_code != 200:
            return f"❌ 错误: {res.json().get('detail')}", ""
        data = res.json()
        answer = data.get("answer", "")
        sources = data.get("sources", [])
        sources_text = "\n\n".join([
            f"📄 来源: {s['source_file']} 第{s['page']}页\n{s['content']}"
            for s in sources
        ])
        return answer, sources_text
    except Exception as e:
        return f"❌ 错误: {str(e)}", ""


def get_file_list():
    """获取已入库文档列表"""
    try:
        res = requests.get(f"{API_BASE}/files")
        files = res.json().get("files", [])
        if not files:
            return "暂无已入库文档"
        return "\n".join([
            f"📄 {f['filename']} | {f['file_type'].upper()} | 状态: {f['status']} | ID: {f['file_id']}"
            for f in files
        ])
    except Exception as e:
        return f"❌ 错误: {str(e)}"


# ════════════════════════════════════════════════════════════
# TODO: 成员5在此完善 UI 布局和交互
# ════════════════════════════════════════════════════════════
with gr.Blocks(title="A23 文档理解与多源数据融合系统") as demo:
    gr.Markdown("# 📚 A23 文档理解与多源数据融合系统")

    with gr.Tab("📤 文档上传"):
        file_input = gr.File(label="上传文档（支持 PDF/DOCX/XLSX/TXT/MD）")
        upload_btn = gr.Button("上传并解析", variant="primary")
        upload_status = gr.Textbox(label="状态", interactive=False)
        file_id_out = gr.Textbox(label="file_id（保存备用）", interactive=False)
        task_id_out = gr.Textbox(label="task_id", visible=False)

        check_btn = gr.Button("刷新解析状态")
        parse_status_out = gr.Textbox(label="解析状态", interactive=False)

        upload_btn.click(upload_and_parse, inputs=file_input, outputs=[upload_status, file_id_out])
        check_btn.click(check_parse_status, inputs=task_id_out, outputs=parse_status_out)

    with gr.Tab("💬 智能问答"):
        query_input = gr.Textbox(label="输入问题", placeholder="例如：合同金额是多少？")
        file_ids_input = gr.Textbox(label="限定文档（file_id，多个用逗号分隔，留空检索全部）")
        ask_btn = gr.Button("提问", variant="primary")
        answer_out = gr.Textbox(label="回答", interactive=False)
        sources_out = gr.Textbox(label="证据来源", interactive=False, lines=5)

        ask_btn.click(ask_question, inputs=[query_input, file_ids_input], outputs=[answer_out, sources_out])

    with gr.Tab("📋 表格回填"):
        gr.Markdown("### 上传模板文件，自动回填字段")
        gr.Markdown("⚠️ 模板中请使用 `{{字段名}}` 格式的占位符")
        # TODO: 成员5完善此Tab的完整交互

    with gr.Tab("🖥️ 系统状态"):
        refresh_btn = gr.Button("刷新文档列表")
        file_list_out = gr.Textbox(label="已入库文档", interactive=False, lines=10)
        refresh_btn.click(get_file_list, outputs=file_list_out)

        health_btn = gr.Button("检查服务状态")
        health_out = gr.Textbox(label="服务状态", interactive=False)

        def check_health():
            try:
                res = requests.get(f"{API_BASE}/health")
                return f"✅ 服务正常: {res.json()}"
            except:
                return "❌ 服务无法连接"

        health_btn.click(check_health, outputs=health_out)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=True)
