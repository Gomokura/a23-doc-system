# A23 文档理解与多源数据融合系统

> 基于大语言模型的文档理解与多源数据融合系统

---

## 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/a23-doc-system.git
cd a23-doc-system

# 2. 复制环境变量文件并填入 API Key
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY

# 3. 一键启动
bash run.sh
```

启动后访问：
- **API 文档（Swagger）**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

---

## 启动前端

```bash
# 单独启动 Gradio 前端（需后端已启动）
source venv/bin/activate
python modules/frontend/app.py
```

前端地址：http://localhost:7860

---

## 项目结构

```
a23-doc-system/
├── main.py               # FastAPI 主入口【成员1】
├── config.py             # 全局配置【成员1】
├── requirements.txt      # 依赖【成员1维护】
├── run.sh                # 一键启动【成员1】
├── api/                  # 路由层【成员1】
│   ├── upload.py         # /upload /parse
│   ├── query.py          # /ask
│   ├── fill.py           # /fill /download
│   └── files.py          # /files
├── modules/
│   ├── parser/           # 文档解析【成员2】
│   ├── retriever/        # 混合检索与问答【成员3】
│   ├── filler/           # 表格回填【成员4】
│   └── frontend/         # Gradio UI【成员5】
├── db/                   # 数据库
├── tests/
│   └── mock_data.py      # 标准 Mock 数据【所有人使用】
└── docs/                 # 文档
```

---

## 接口总览

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/upload` | 上传文件 |
| POST | `/parse` | 提交解析任务 |
| GET  | `/parse/status/{task_id}` | 查询解析状态 |
| POST | `/ask` | 智能问答 |
| POST | `/fill` | 表格回填 |
| GET  | `/download/{file_id}` | 下载文件 |
| GET  | `/files` | 文档列表 |
| DELETE | `/files/{file_id}` | 删除文档 |
| GET  | `/health` | 健康检查 |

完整接口规范见：[A23 技术规范文档 v1.1]

---

## 分支规范

| 分支 | 用途 | 负责人 |
|------|------|--------|
| `main` | 稳定版本，只由队长合并 | 成员1 |
| `dev` | 集成联调分支 | 成员1 |
| `feat/parser` | 文档解析 | 成员2 |
| `feat/retriever` | 检索与问答 | 成员3 |
| `feat/filler` | 表格回填 | 成员4 |
| `feat/frontend` | 前端展示 | 成员5 |

---

## 团队分工

| 成员 | 身份 | 负责模块 |
|------|------|---------|
| 成员1 | 队长 / 后端主控 | main.py、api/、db/ |
| 成员2 | 文档解析与抽取 | modules/parser/ |
| 成员3 | 检索融合与问答 | modules/retriever/ |
| 成员4 | 表格回填与规则映射 | modules/filler/ |
| 成员5 | 前端展示与交付 | modules/frontend/ |
