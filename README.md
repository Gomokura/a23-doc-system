# 基于大语言模型的文档理解与多源数据融合系统

> 支持 Word / Excel / PDF / TXT / Markdown 多格式文档的智能解析、混合检索问答与自动填表。

---

## 技术栈

| 层次 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + TypeScript + Tailwind CSS + Element Plus |
| 后端 | FastAPI + Python 3.11 + SQLite（SQLAlchemy） |
| 向量数据库 | ChromaDB 0.6 |
| 检索算法 | BM25 + 向量检索 + RRF 融合 |
| 文档解析 | PyMuPDF + python-docx + openpyxl + pandas |
| LLM 接口 | SiliconFlow API（Qwen2.5-72B-Instruct） |
| VLM 接口 | SiliconFlow API（Qwen2-VL-72B-Instruct） |
| Embedding | BAAI/bge-m3 |

---

## 快速启动

### 环境要求

- Python 3.11+
- Node.js 18+

### 后端

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. 配置 API Key（编辑 config.py）
# llm_api_key = "your_siliconflow_api_key"

# 3. 启动后端
python main.py
# 或双击 start_backend.bat（Windows）
```

后端地址：http://localhost:8000
API 文档（Swagger）：http://localhost:8000/docs

### 前端

```bash
cd modules/frontend
npm install
npm run dev
```

前端地址：http://localhost:5173

---

## 项目结构

```
a23-doc-system/
├── main.py                        # FastAPI 主入口，注册路由、启动事件
├── config.py                      # 全局配置（API Key、模型名、路径等）
├── errors.py                      # 统一错误码与异常处理
├── requirements.txt               # Python 依赖
├── start_backend.bat              # Windows 一键启动后端
├── CHANGELOG.md                   # 详细变更记录
│
├── api/                           # 路由层（负责人：成员1）
│   ├── upload.py                  # POST /upload  POST /parse  GET /parse/status/{id}
│   │                              # POST /template/placeholders
│   ├── query.py                   # POST /ask
│   ├── fill.py                    # POST /fill/preview  POST /fill  GET /download/{id}
│   ├── document_ops.py            # POST /document  POST /document/preview
│   └── files.py                   # GET /files  DELETE /files/{id}
│
├── modules/
│   ├── parser/                    # 文档解析模块（负责人：成员2）
│   │   ├── document_parser.py     # 两级漏斗解析：PyMuPDF → VLM OCR
│   │   └── chunker.py             # 文本分块（按段落/句子边界）
│   │
│   ├── retriever/                 # 检索与问答模块（负责人：成员3）
│   │   ├── indexer.py             # 向量索引构建（ChromaDB + 维度自动校验）
│   │   ├── bm25_retriever.py      # BM25 关键词检索
│   │   ├── hybrid_retriever.py    # RRF 融合排序
│   │   └── qa_engine.py           # 多源融合问答（冲突检测 + 溯源）
│   │
│   ├── filler/                    # 智能填表模块（负责人：成员4）
│   │   ├── intelligent_filler.py  # 核心：字段提取、行筛选、写入模板
│   │   └── table_filler.py        # 占位符替换（{{字段名}} 模式）
│   │
│   ├── document_ops/              # 文档操作模块（负责人：成员1）
│   │   ├── operation_parser.py    # 自然语言指令解析（规则层 + LLM 层）
│   │   ├── common_operations.py   # 参数归一化 + 操作执行器
│   │   ├── xlsx_operations.py     # Excel 操作实现
│   │   ├── docx_operations.py     # Word 操作实现
│   │   └── pdf_operations.py      # PDF 操作实现
│   │
│   └── frontend/                  # Vue 3 前端（负责人：成员5）
│       ├── src/pages/
│       │   ├── Upload.vue         # 文件上传与解析
│       │   ├── Query.vue          # 智能问答
│       │   ├── Fill.vue           # 智能填表（预览 + 确认）
│       │   └── DocOps.vue         # 文档操作
│       └── src/layout/
│           └── MainContent.vue    # keep-alive 页面状态保留
│
├── db/                            # SQLite 数据库 + ChromaDB 向量库
├── uploads/                       # 上传文件存储
├── outputs/                       # 填表输出文件
└── docs/                          # 设计文档与实验报告
    ├── 关键模块概要设计与创新要点说明.md
    ├── 实验报告.md
    └── 技术亮点与性能优化总结.md
```

---

## 团队分工

| 成员 | 身份 | 负责模块 |
|------|------|---------|
| 成员1 | 队长 / 后端主控 | main.py、api/、db/、document_ops/ |
| 成员2 | 文档解析与抽取 | modules/parser/ |
| 成员3 | 检索融合与问答 | modules/retriever/ |
| 成员4 | 表格回填与规则映射 | modules/filler/ |
| 成员5 | 前端展示与交付 | modules/frontend/ |

---

## 接口总览

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/upload` | 上传文件（docx/xlsx/pdf/txt/md） |
| POST | `/parse` | 提交解析与索引任务（异步） |
| GET  | `/parse/status/{task_id}` | 查询解析状态 |
| GET  | `/files` | 获取已上传文档列表 |
| DELETE | `/files/{file_id}` | 删除文档及其索引 |
| POST | `/ask` | 智能问答（混合检索 + LLM 生成） |
| POST | `/template/placeholders` | 识别模板字段（占位符或 LLM 表头识别） |
| POST | `/fill/preview` | 智能填表预览（提取字段值，不生成文件） |
| POST | `/fill` | 智能填表（生成并保存输出文件） |
| GET  | `/download/{file_id}` | 下载填表结果文件 |
| POST | `/document` | 文档操作（自然语言指令） |
| POST | `/document/preview` | 文档操作预览（dry-run，返回受影响范围） |
| GET  | `/health` | 健康检查 |

---

## 核心功能详解

### 一、文档解析（modules/parser）

- **两级漏斗 PDF 解析**：先用 PyMuPDF 提取文字，提取字符数 ≥ 50 则直接采用（文字型 PDF 零误差）；字符数不足则判定为扫描件，调用云端 VLM（Qwen2-VL-72B）并发 OCR（CONCURRENCY=3），失败自动降级为纯文本兜底
- **多格式支持**：docx（python-docx）、xlsx（pandas）、txt/md（直接读取）
- **ChromaDB 维度自动校验**：构建索引前检测 Embedding 模型输出维度，与上次记录不一致时自动清空重建，解决换模型后必须手动删库的问题

### 二、智能问答（modules/retriever）

- **混合检索**：BM25 关键词检索 + 向量语义检索并行执行，RRF（Reciprocal Rank Fusion）算法融合排序，兼顾精确匹配与语义理解
- **多源融合**：检索多个文档片段后，检测信息冲突并标注，LLM 生成最终答案
- **返回内容**：答案文本 + 置信度分数 + 溯源文件列表

### 三、智能填表（modules/filler）

**行筛选架构（核心创新）：**

```
用户自然语言指令
      ↓
规则层（正则直接解析，0次LLM调用）
      ↓ 规则层无法解析
LLM 解析意图（仅1次调用）→ 结构化 JSON 条件
      ↓
pandas 规则引擎精确执行（不受数据量影响）
```

支持 OR 分组逻辑（多表场景），支持 eq/neq/contains/gt/lt/gte/lte/between/empty 等10种操作符。20000行数据仅需1次LLM调用，彻底消除429限流风险。

**多表分组填写：**
- 解析 docx XML body，按文档顺序提取每个表格及其上方描述段落
- 从用户提示词一次性解析每个表格的独立筛选条件
- 每个表格独立筛选数据后分别填入，支持任意数量的多表模板

**混合数据源提取：**
- xlsx：pandas 精确列名匹配，行对齐提取，支持多 Sheet 合并
- 纯文字 docx：LLM 批量并发提取（BATCH_SIZE=8，每批约2400字，避免中间遗忘），ThreadPoolExecutor 并发8个 worker
- 预览与填表分离：预览一次全量提取，确认后直接写入，不重复调用后端

**写入模板：**
- xlsx：自动识别表头行（非空列最多的行），处理合并单元格，逐行写入
- docx：字段标签后追加值（单值字段）+ 表格行追加（多值字段）

### 四、文档操作（modules/document_ops）

自然语言指令 → 规则层解析（正则，速度快）→ LLM 层解析（复杂指令）→ 参数归一化 → 操作执行

| 文件类型 | 支持操作 |
|---------|---------|
| xlsx | 编辑单元格、格式化（字体/颜色/加粗）、插入/删除行列、条件格式、条件删除、条件筛选 |
| docx | 文本提取、内容替换、段落追加 |
| pdf | 按页提取、关键词检索、大纲获取、摘要生成 |

所有写操作均支持 dry-run 预览（`/document/preview`），返回受影响单元格/行列表，用户确认后再执行。
