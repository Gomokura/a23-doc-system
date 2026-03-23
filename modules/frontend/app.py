"""
A23 智能文档系统 · 前端界面
成员5 · 前端展示与交付
UI风格：Material You (M3) — 大圆角 · 色调表面 · 动态配色
"""

import gradio as gr
import requests
import time
import os
import json

# ============================================================
# ⚙️ 配置区：后端好了把 USE_MOCK 改成 False
# ============================================================
USE_MOCK = True
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# ============================================================
# 🎭 Mock 数据
# ============================================================
MOCK_FILES = [
    {"file_id": "f001", "filename": "采购合同_2024.pdf",  "status": "已索引", "pages": 12},
    {"file_id": "f002", "filename": "季度报告_Q3.docx",   "status": "已索引", "pages": 28},
    {"file_id": "f003", "filename": "财务数据_2024.xlsx", "status": "已索引", "pages": 5},
]
MOCK_ANSWER = {
    "answer": "根据采购合同第3条款，本次合同总金额为 **人民币 258,000 元**，分三期付款：首付30%（77,400元），交货后付50%（129,000元），验收后付尾款20%（51,600元）。",
    "sources": [
        {"filename": "采购合同_2024.pdf", "page": 3, "snippet": "合同总金额为人民币贰拾伍万捌千元整（¥258,000）"},
        {"filename": "采购合同_2024.pdf", "page": 7, "snippet": "付款方式：分三期支付，比例分别为30%、50%、20%"},
    ]
}

# ============================================================
# 🔌 API 函数
# ============================================================
def api_upload(file_obj):
    if USE_MOCK:
        time.sleep(0.8)
        return {"file_id": "f_mock_001", "filename": os.path.basename(file_obj.name)}
    with open(file_obj.name, "rb") as f:
        res = requests.post(f"{API_BASE}/upload", files={"file": f})
    if res.status_code != 200:
        raise Exception(res.json().get("detail", "上传失败"))
    return res.json()

def api_parse(file_id):
    if USE_MOCK:
        return {"task_id": f"task_{file_id}"}
    res = requests.post(f"{API_BASE}/parse", json={"file_id": file_id})
    if res.status_code != 200:
        raise Exception(res.json().get("detail", "解析启动失败"))
    return res.json()

def api_ask(query, file_ids):
    if USE_MOCK:
        time.sleep(1.0)
        return MOCK_ANSWER
    res = requests.post(f"{API_BASE}/ask", json={"query": query, "file_ids": file_ids})
    if res.status_code != 200:
        raise Exception(res.json().get("detail", "问答失败"))
    return res.json()

def api_get_files():
    if USE_MOCK:
        return MOCK_FILES
    res = requests.get(f"{API_BASE}/files")
    return res.json() if res.status_code == 200 else []

def api_get_health():
    if USE_MOCK:
        return {"status": "healthy", "docs_count": 3, "avg_response_ms": 312}
    try:
        res = requests.get(f"{API_BASE}/health", timeout=3)
        return res.json()
    except Exception:
        return {"status": "unreachable"}

def api_fill(template_file, file_ids):
    if USE_MOCK:
        time.sleep(1.2)
        return {"task_id": "fill_001", "download_id": "dl_abc123"}
    with open(template_file.name, "rb") as f:
        res = requests.post(f"{API_BASE}/fill",
                            files={"template": f},
                            data={"file_ids": json.dumps(file_ids)})
    if res.status_code != 200:
        raise Exception(res.json().get("detail", "回填失败"))
    return res.json()

# ============================================================
# 🎨 Material You (M3) CSS
# ============================================================
M3_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

:root {
    --md-primary:             #6750A4;
    --md-on-primary:          #FFFFFF;
    --md-primary-container:   #EADDFF;
    --md-on-primary-container:#21005D;
    --md-secondary:           #625B71;
    --md-secondary-container: #E8DEF8;
    --md-surface:             #FFFBFE;
    --md-surface-variant:     #E7E0EC;
    --md-on-surface:          #1C1B1F;
    --md-on-surface-variant:  #49454F;
    --md-outline:             #79747E;
    --md-outline-variant:     #CAC4D0;
    --md-success-container:   #C3EFAD;
    --md-success:             #386A20;
    --md-error:               #B3261E;
    --md-error-container:     #F9DEDC;
    --md-shadow:   0 1px 2px rgba(0,0,0,.12), 0 2px 6px rgba(0,0,0,.08);
    --md-shadow-2: 0 2px 8px rgba(0,0,0,.14), 0 4px 16px rgba(0,0,0,.10);
}

* { box-sizing: border-box; }
body, .gradio-container {
    background: var(--md-surface) !important;
    color: var(--md-on-surface) !important;
    font-family: 'Noto Sans SC', sans-serif !important;
}
.gradio-container { max-width: 980px !important; margin: 0 auto !important; }
footer { display: none !important; }

/* Header */
.m3-header {
    background: var(--md-primary-container);
    border-radius: 28px;
    padding: 28px 36px;
    margin: 20px 0 20px;
    display: flex;
    align-items: center;
    gap: 18px;
    box-shadow: var(--md-shadow);
}
.m3-header-icon {
    width: 56px; height: 56px;
    background: var(--md-primary);
    border-radius: 16px;
    display: flex; align-items: center; justify-content: center;
    font-size: 28px; flex-shrink: 0;
}
.m3-header h1 {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
    color: var(--md-on-primary-container) !important;
    margin: 0 0 4px !important;
}
.m3-header p {
    font-size: 0.88rem !important;
    color: var(--md-secondary) !important;
    margin: 0 !important;
}
.m3-badge {
    margin-left: auto;
    background: var(--md-primary);
    color: #fff;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
}

/* Tabs */
.tab-nav { background: var(--md-surface-variant) !important; border-radius: 28px !important; padding: 6px !important; border: none !important; margin-bottom: 8px !important; }
.tab-nav button { border-radius: 22px !important; border: none !important; background: transparent !important; color: var(--md-on-surface-variant) !important; font-weight: 500 !important; padding: 10px 22px !important; transition: all .2s !important; }
.tab-nav button:hover { background: rgba(103,80,164,.10) !important; color: var(--md-primary) !important; }
.tab-nav button.selected { background: var(--md-secondary-container) !important; color: var(--md-on-primary-container) !important; font-weight: 700 !important; box-shadow: var(--md-shadow) !important; }

/* Section label */
.m3-label {
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 1.4px !important;
    text-transform: uppercase !important;
    color: var(--md-secondary) !important;
    margin: 16px 0 8px !important;
}

/* Cards */
.m3-card { background: var(--md-surface) !important; border: 1px solid var(--md-outline-variant) !important; border-radius: 24px !important; padding: 24px !important; box-shadow: var(--md-shadow) !important; margin-bottom: 12px !important; }
.m3-tonal { background: var(--md-primary-container) !important; border: none !important; border-radius: 24px !important; padding: 18px 22px !important; margin-bottom: 12px !important; }

/* Inputs */
input[type=text], textarea {
    background: var(--md-surface-variant) !important;
    border: 2px solid transparent !important;
    border-radius: 16px !important;
    color: var(--md-on-surface) !important;
    padding: 14px 16px !important;
    font-size: 0.95rem !important;
    transition: border-color .2s !important;
}
input[type=text]:focus, textarea:focus { border-color: var(--md-primary) !important; background: #fff !important; }

/* Buttons */
button.gr-button, .gr-button {
    border-radius: 28px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 12px 28px !important;
    border: none !important;
    transition: all .2s !important;
    letter-spacing: .3px !important;
}
button[variant="primary"], .gr-button-primary {
    background: var(--md-primary) !important;
    color: #fff !important;
    box-shadow: var(--md-shadow) !important;
}
button[variant="primary"]:hover { filter: brightness(1.1) !important; box-shadow: var(--md-shadow-2) !important; }
button[variant="secondary"], .gr-button-secondary {
    background: var(--md-secondary-container) !important;
    color: var(--md-on-primary-container) !important;
}

/* Upload zone */
.gr-file { border: 2px dashed var(--md-outline-variant) !important; border-radius: 24px !important; background: var(--md-surface-variant) !important; }
.gr-file:hover { border-color: var(--md-primary) !important; }

/* Answer */
.m3-answer {
    background: var(--md-primary-container);
    border-radius: 20px;
    border-left: 4px solid var(--md-primary);
    padding: 20px 24px;
    color: var(--md-on-primary-container);
    font-size: 1rem;
    line-height: 1.75;
    margin: 8px 0 16px;
}
.m3-source {
    display: flex; gap: 12px; align-items: flex-start;
    background: var(--md-surface-variant);
    border-radius: 14px;
    padding: 12px 16px;
    margin: 6px 0;
    font-size: 0.87rem;
    color: var(--md-on-surface-variant);
}
.m3-page-chip {
    background: var(--md-secondary-container);
    color: var(--md-secondary);
    border-radius: 8px;
    padding: 3px 9px;
    font-size: 0.75rem;
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 2px;
}

/* Stats */
.m3-stats { display: grid; grid-template-columns: repeat(3,1fr); gap: 12px; margin: 8px 0 16px; }
.m3-stat { background: var(--md-surface-variant); border-radius: 20px; padding: 18px; text-align: center; }
.m3-stat-val { font-size: 1.9rem; font-weight: 700; color: var(--md-primary); }
.m3-stat-lbl { font-size: 0.76rem; color: var(--md-on-surface-variant); margin-top: 4px; }

/* Table */
.gr-dataframe table { border-radius: 16px !important; overflow: hidden !important; }
.gr-dataframe thead tr { background: var(--md-secondary-container) !important; }
.gr-dataframe tbody tr:hover { background: rgba(103,80,164,.06) !important; }

/* FAB */
.m3-fab {
    position: fixed; bottom: 28px; right: 28px;
    width: 56px; height: 56px;
    background: var(--md-primary-container);
    color: var(--md-on-primary-container);
    border-radius: 16px; border: none;
    font-size: 22px; font-weight: 700;
    cursor: pointer;
    box-shadow: var(--md-shadow-2);
    transition: all .2s;
    z-index: 999;
}
.m3-fab:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(103,80,164,.35); }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: var(--md-outline-variant); border-radius: 99px; }
"""

# ============================================================
# 🖥️ 业务逻辑
# ============================================================
def do_upload(file_obj):
    if file_obj is None:
        return "⚠️ 请先选择文件", ""
    try:
        up = api_upload(file_obj)
        fid = up["file_id"]
        fname = up.get("filename", "文件")
        api_parse(fid)
        # 模拟进度
        for p in [20, 45, 70, 90, 100]:
            time.sleep(0.5)
        return f"✅ 上传成功：{fname}\n✅ 解析完成，文档已入库！\n🔑 File ID：{fid}", fid
    except Exception as e:
        return f"❌ 错误：{str(e)}", ""

def do_ask(query, file_ids_str):
    if not query.strip():
        return "⚠️ 请输入问题", ""
    try:
        fids = [x.strip() for x in file_ids_str.split(",") if x.strip()]
        res = api_ask(query, fids)
        answer = res.get("answer", "无答案")
        sources = res.get("sources", [])
        src_html = ""
        for s in sources:
            src_html += f"""<div class="m3-source">
  <span class="m3-page-chip">P.{s['page']}</span>
  <div><strong style="color:var(--md-on-surface)">📄 {s['filename']}</strong><br>{s['snippet']}</div>
</div>"""
        return answer, src_html or "<p style='color:var(--md-on-surface-variant);font-size:.9rem'>暂无证据来源</p>"
    except Exception as e:
        return f"❌ {str(e)}", ""

def do_fill(template_file, file_ids_str):
    if template_file is None:
        return "⚠️ 请先上传 Word 模板"
    try:
        fids = [x.strip() for x in file_ids_str.split(",") if x.strip()]
        res = api_fill(template_file, fids)
        return f"✅ 回填完成！\n📥 下载 ID：{res.get('download_id','')}\n（后端联调后可直接下载文件）"
    except Exception as e:
        return f"❌ {str(e)}"

def do_refresh():
    files = api_get_files()
    health = api_get_health()
    rows = [[f["filename"], f["status"], f"{f.get('pages','?')} 页", f["file_id"]] for f in files]
    icon = "🟢" if health.get("status") == "healthy" else "🔴"
    health_html = f"""<div class="m3-stats">
  <div class="m3-stat"><div class="m3-stat-val">{health.get('docs_count', len(files))}</div><div class="m3-stat-lbl">已入库文档</div></div>
  <div class="m3-stat"><div class="m3-stat-val">{health.get('avg_response_ms','—')}<span style="font-size:1rem">ms</span></div><div class="m3-stat-lbl">平均响应</div></div>
  <div class="m3-stat"><div class="m3-stat-val" style="font-size:1.4rem">{icon}</div><div class="m3-stat-lbl">{health.get('status','unknown')}</div></div>
</div>"""
    return rows, health_html

# ============================================================
# 🏗️ Gradio UI
# ============================================================
with gr.Blocks(css=M3_CSS, title="A23 智能文档系统") as demo:

    gr.HTML("""
<div class="m3-header">
  <div class="m3-header-icon">📚</div>
  <div>
    <h1 class="m3-header">A23 智能文档系统</h1>
    <p class="m3-header">基于大语言模型的文档理解与多源数据融合系统</p>
  </div>
  <div class="m3-badge">Material You ✦</div>
</div>""")

    with gr.Tabs(elem_classes="tab-nav"):

        # ── Tab 1 ──────────────────────────
        with gr.Tab("📤  文档上传"):
            gr.HTML('<p class="m3-label">上传文档并触发解析入库</p>')
            with gr.Row():
                with gr.Column(scale=3):
                    t1_file = gr.File(label="拖拽或点击上传", file_types=[".pdf",".docx",".xlsx"])
                with gr.Column(scale=1, min_width=160):
                    t1_btn = gr.Button("🚀 上传并解析", variant="primary", size="lg")
                    gr.HTML('<p style="font-size:.78rem;color:var(--md-on-surface-variant);margin-top:6px;text-align:center">PDF · DOCX · XLSX</p>')
            t1_status = gr.Textbox(label="状态日志", lines=4, interactive=False, placeholder="等待上传...")
            t1_fid    = gr.Textbox(label="File ID（问答时粘贴使用）", interactive=False, placeholder="上传后自动填入")
            t1_btn.click(do_upload, [t1_file], [t1_status, t1_fid])

        # ── Tab 2 ──────────────────────────
        with gr.Tab("💬  智能问答"):
            gr.HTML('<p class="m3-label">输入问题，获取答案与溯源证据</p>')
            with gr.Row():
                with gr.Column(scale=4):
                    t2_query = gr.Textbox(label="你的问题", placeholder="例：合同总金额是多少？付款方式是什么？", lines=2)
                with gr.Column(scale=2):
                    t2_fids  = gr.Textbox(label="File ID（可选）", placeholder="留空则搜索全部文档")
            t2_btn = gr.Button("🔍 开始问答", variant="primary", size="lg")
            gr.HTML('<p class="m3-label" style="margin-top:18px">回答</p>')
            t2_answer  = gr.Markdown(elem_classes="m3-answer")
            gr.HTML('<p class="m3-label">证据来源</p>')
            t2_sources = gr.HTML('<p style="color:var(--md-on-surface-variant);font-size:.9rem">问答后显示</p>')
            t2_btn.click(do_ask, [t2_query, t2_fids], [t2_answer, t2_sources])

        # ── Tab 3 ──────────────────────────
        with gr.Tab("📋  表格回填"):
            gr.HTML('<p class="m3-label">上传 Word 模板，自动提取数据并填入</p>')
            with gr.Row():
                with gr.Column(scale=3):
                    t3_tmpl = gr.File(label="Word 模板（.docx）", file_types=[".docx"])
                with gr.Column(scale=2):
                    t3_fids = gr.Textbox(label="数据来源 File ID", placeholder="多个用逗号分隔", lines=3)
            t3_btn    = gr.Button("⚡ 一键回填", variant="primary", size="lg")
            t3_status = gr.Textbox(label="回填状态", lines=4, interactive=False, placeholder="等待操作...")
            gr.HTML("""<div class="m3-tonal">
  <p style="margin:0;font-size:.87rem;color:var(--md-on-primary-container)">
    💡 <strong>提示：</strong>模板中使用 <code>{{字段名}}</code> 作为占位符，系统自动从已入库文档提取对应数据填入。
  </p></div>""")
            t3_btn.click(do_fill, [t3_tmpl, t3_fids], [t3_status])

        # ── Tab 4 ──────────────────────────
        with gr.Tab("🖥️  系统状态"):
            gr.HTML('<p class="m3-label">已入库文档 · 服务健康状态</p>')
            t4_btn     = gr.Button("🔄 刷新状态", variant="secondary")
            gr.HTML('<p class="m3-label" style="margin-top:12px">服务指标</p>')
            t4_health  = gr.HTML('<p style="color:var(--md-on-surface-variant);font-size:.9rem">点击刷新查看</p>')
            gr.HTML('<p class="m3-label">已入库文档</p>')
            t4_table   = gr.Dataframe(headers=["文件名","状态","页数","File ID"], datatype=["str","str","str","str"], interactive=False)
            t4_btn.click(do_refresh, [], [t4_table, t4_health])

    gr.HTML('<button class="m3-fab" onclick="window.scrollTo({top:0,behavior:\'smooth\'})">↑</button>')

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True)
