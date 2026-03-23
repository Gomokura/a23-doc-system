# 检索融合与问答模块说明文档

> **负责人**：成员3
> **所属分支**：`feat/retriever`
> **最后更新**：2026-03-19

---

## 1. 模块概述

本模块负责**文档检索**与**智能问答**两大核心功能，是连接「文档解析」与「大模型问答」的中间链路。

### 1.1 核心职责

```
文件上传/解析 → 索引构建 → 检索融合 → LLM 问答 → 返回结果
```

### 1.2 模块结构

```
modules/retriever/
├── indexer.py           # 索引构建：向量入库 + BM25 维护
└── hybrid_retriever.py # 混合检索 + 冲突检测 + LLM 问答
```

---

## 2. 索引构建（indexer.py）

### 2.1 功能说明

`build_index()` 将解析后的文档写入两个索引：

| 索引类型 | 工具 | 存储路径 |
|----------|------|----------|
| 向量索引 | ChromaDB + `BAAI/bge-small-zh-v1.5` | `db/chroma/` |
| BM25 索引 | `rank_bm25.BM25Okapi` | `db/chroma/bm25_index.pkl` |

### 2.2 向量索引流程

1. 对每个 chunk 的文本内容，用 Sentence-Transformers 编码为 512 维向量
2. 批量写入 ChromaDB 持久化集合 `documents`
3. metadata 记录：`file_id`、`source_file`、`page`、`chunk_type`

### 2.3 BM25 索引流程

1. 所有 chunk 内容存入 `_bm25_corpus`（列表）
2. 同步维护 `_bm25_doc_map`（chunk_id → 元信息）
3. 每次 `build_index` 调用后，持久化到 `bm25_index.pkl`
4. 启动时自动从磁盘加载，无须重建

### 2.4 关键配置

```python
# config.py
embed_model = "BAAI/bge-small-zh-v1.5"  # 中文嵌入模型
chroma_path = "./db/chroma"              # 向量数据库路径
```

---

## 3. 混合检索与问答（hybrid_retriever.py）

### 3.1 检索流程

```
用户 query
    │
    ├── 向量检索 ─── ChromaDB.query() ──── 权重 60%
    │                    │
    │                    └── 余弦相似度（1 / (1 + distance)）
    │
    └── BM25 检索 ─── rank_bm25 ───────── 权重 40%
                         │
                         └── TF-IDF 得分
                             
    两种得分各自归一化后加权求和，按最终得分排序取 TOP 5
```

### 3.2 混合得分公式

```
hybrid_score = vector_score × 0.6 + bm25_score_norm × 0.4
```

- `vector_score`：向量余弦相似度
- `bm25_score_norm`：BM25 得分做 Min-Max 归一化

### 3.3 Prompt 设计

```
你是一个专业的文档问答助手。请根据以下参考文档，回答用户的问题。

## 参考文档
[文档1]
<content>

## 用户问题
<query>

## 回答要求
1. 基于参考文档内容回答，不要编造信息
2. 如果文档中没有相关内容，请明确说明
3. 回答要准确、简洁、有条理
4. 在回答中引用相关文档来源

## 回答格式
回答: <你的回答>
来源: <列出参考的文档编号>
```

### 3.4 场景化 Prompt

| 场景 | Prompt 特点 |
|------|-------------|
| 合同审核 | 增加「识别合同金额、甲乙双方、违约条款」要求 |
| 报表分析 | 增加「数据对比、趋势描述」要求 |
| 法规查询 | 增加「引用法条、说明适用范围」要求 |

---

## 4. 多源冲突检测与融合

### 4.1 问题场景

当多个文档都包含与 query 相关的内容时，可能出现：
- **事实冲突**：不同文档对同一事实描述不一致
- **数值冲突**：合同金额、日期等数值不一致
- **优先级冲突**：同一字段在不同模板中定义不同

### 4.2 冲突检测逻辑

```
对于每个关键实体（key）：
    收集所有相关 chunks 中该实体的值
    if 值的种类 > 1：
        标记为冲突，返回 {conflict: true, values: [...]}
```

### 4.3 冲突融合策略

| 策略 | 适用场景 | 规则 |
|------|----------|------|
| 优先高置信度 | 有明显得分差异 | 选择 hybrid_score 最高的 chunk 对应值 |
| 优先权威来源 | 有主从文档 | 优先使用主文档（如原始合同 > 摘要） |
| 保留全部 | 无法判断 | 在答案中标注「存在冲突」，并列出场源 |

---

## 5. 与上下游接口

### 5.1 上游：文档解析（成员2）

```python
# 调用方：api/upload.py → modules/parser/document_parser.py
parsed_doc = {
    "file_id": "...",
    "filename": "...",
    "chunks": [
        {
            "chunk_id": "...",
            "content": "...",
            "page": 1,
            "chunk_type": "text"
        }
    ]
}

# 调用成员3的接口
from modules.retriever.indexer import build_index
build_index(parsed_doc)
```

### 5.2 上游：API 路由（成员1）

```python
# api/query.py
from modules.retriever.hybrid_retriever import retrieve_and_answer

result = retrieve_and_answer(query=query, file_ids=file_ids)
# result = {query, answer, sources, confidence}
```

### 5.3 返回格式（规范文档 4.3）

```json
{
    "query": "合同金额是多少？",
    "answer": "根据合同文件，合同总金额为人民币500万元整...",
    "sources": [
        {
            "chunk_id": "file001_0",
            "content": "合同金额为人民币500万元整",
            "source_file": "测试合同.pdf",
            "page": 1
        }
    ],
    "confidence": 0.92
}
```

---

## 6. 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `vector_weight` | 0.6 | 向量检索权重 |
| `bm25_weight` | 0.4 | BM25 检索权重 |
| `top_k` | 5 | 返回的最多 chunk 数 |
| `embed_model` | `BAAI/bge-small-zh-v1.5` | 嵌入模型 |
| `llm_model` | `qwen3:8b`（Ollama 本地） | LLM 模型，通过 Ollama 部署 |
| `llm_base_url` | `http://localhost:11434/v1` | Ollama 服务地址 |

---

## 7. 目录结构（成员3负责部分）

```
a23-doc-system/
├── modules/
│   └── retriever/
│       ├── indexer.py           ✅ 已实现
│       └── hybrid_retriever.py  ✅ 已实现
├── docs/
│   ├── retriever-module.md      ✅ 本文档
│   └── 技术亮点与性能优化总结.md
└── tests/
    ├── mock_data.py              ✅ 成员1维护
    └── test_retriever_accuracy.py ✅ 准确率测试（见本文档附录）
```

---

## 附录：测试方法

```bash
# 启动服务后，运行准确率测试
cd a23-doc-system
python -m tests.test_retriever_accuracy
```

测试用例会：
1. 用 Mock 数据构建索引
2. 批量执行测试问答
3. 对比标准答案，计算准确率/召回率
4. 输出测试报告
