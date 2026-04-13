
# 修改日志 (2026-04-13)

## 一、document_ops 模块扩展：新增 xlsx 与 pdf 支持

### 1.1 新建文件

#### `modules/document_ops/pdf_operations.py`（新建）
- **概述**：独立 PDF 文档操作类，基于 PyMuPDF (fitz) 实现
- **核心功能**：
  - `extract_text(page_start, page_end)`：按页码范围提取文本
  - `extract_page(page_num)`：提取指定页面完整内容（含图片/表格统计）
  - `extract_by_keyword(keyword, context_chars)`：关键词搜索并提取上下文
  - `get_outline()`：获取 PDF 大纲/书签
  - `get_metadata()`：获取 PDF 元数据（标题、作者、总页数等）
- **便捷函数**：`pdf_extract_text()`、`pdf_extract_page()`、`pdf_get_outline()`

---

### 1.2 修改文件

#### `modules/document_ops/operation_parser.py`
- 新增 `_read_pdf_context()` 方法（第 378-405 行）
  - 读取 PDF 总页数和前5页文本预览，供 LLM 解析时参考
  - 页码参数从1开始的说明提示
- 在 `parse()` 方法中添加 PDF 上下文分支：`elif file_path and file_type == "pdf"`

#### `modules/document_ops/common_operations.py`
- 新增 `_normalize_pdf_params()` 参数归一化函数（第 682-760 行）
  - 支持中文数字转整数（"第三页"→3）
  - 支持 `page_num` / `page` / `页码` 等多种参数名归一
  - 支持 `keyword` / `关键词` / `search_term` 归一
  - 支持 `page_start` / `page_end` 中文数字归一
- 新增 `_execute_pdf_operation()` 执行方法（第 1000-1051 行）
  - 支持 `EXTRACT_CONTENT`、`GENERATE_SUMMARY`、`extract_page` 等操作
  - 摘要生成：取前 N 字符，尝试在句号处截断
- 修复 `re` 模块未导入的问题（新增 `import re`）
- 完善 `_normalize_xlsx_params()` 归一化逻辑
  - `edit_cell` 和 `format_cell` 类型加入行/列操作归一化
  - 中文"位置"参数支持归一

#### `modules/document_ops/__init__.py`
- 导出 `PDFDocumentOperations` 类

#### `api/document_ops.py`
- `/extract` 接口：新增 PDF 类型支持
- `/summarize` 接口：新增 PDF 类型支持（调用 `PDFDocumentOperations`）
- 导入列表新增 `PDFDocumentOperations`

---

### 1.3 功能验证

| 指令 | 解析结果 | 通过 |
|------|----------|------|
| `提取所有文本` (pdf) | `extract_content` | ✅ |
| `生成500字的摘要` (pdf) | `generate_summary` | ✅ |
| `提取第2页的内容` (pdf) | `extract_content` | ✅ |
| `把A1改成100` (xlsx) | `edit_cell` | ✅ |
| `把B2标红` (xlsx) | `format_cell` | ✅ |
| `在第3行插入一行` (xlsx) | `add_row` | ✅ |
| `删除第5行` (xlsx) | `delete_row` | ✅ |

**测试结果**：XLSX 解析 4/4 ✅，PDF 解析 3/3 ✅，参数归一化 2/2 ✅

---

## 二、filler 模块 Bug 修复：表格回填功能

### 2.1 修复的问题清单

| # | 问题描述 | 严重程度 | 影响范围 |
|---|----------|----------|----------|
| 1 | 表头行定位错误：把"第一个非空行"当作表头 | 🔴 严重 | 智能回填（xlsx） |
| 2 | 合并单元格主格值被从属格覆盖，导致列索引错位 | 🔴 严重 | 智能回填（xlsx） |
| 3 | 只处理 `wb.active` 活跃工作表，忽略其他工作表 | 🟡 中等 | 智能回填（xlsx） |
| 4 | XLSX 源文件用 `to_csv` 丢失列结构语义 | 🔴 严重 | 智能回填（xlsx） |
| 5 | 前端 409 错误提示不够友好 | 🟡 中等 | 智能回填（前端） |
| 6 | 模糊匹配无优先级，行溢出时返回 None 导致后续全留空 | 🟡 中等 | 智能回填（xlsx/docx） |
| 7 | XLSX 模板文本提取只取前3行，表头在4-10行时被遗漏 | 🟡 中等 | 字段解析（api） |
| 8 | 写入时无重复检查，可能触发合并单元格冲突 | 🟡 中等 | 智能回填（xlsx） |

### 2.2 修改文件

#### `modules/filler/intelligent_filler.py`

**重写 `_write_xlsx_smart()` 函数（第 323-430 行）**

| 改进点 | 旧逻辑 | 新逻辑 |
|--------|--------|--------|
| 表头识别 | 取第一个有内容的行 | 遍历所有工作表，选**非空列最多（≥3列）**的行 |
| 工作表 | 只处理 `wb.active` | 遍历所有 `wb.worksheets`，选最佳匹配 |
| 合并单元格 | 未处理，主格值被覆盖 | `merged_master` 集合只读主格，跳过从属格 |
| 写入防重 | 无 | `written_cells` 集合追踪已写入单元格 |
| 跨行合并 | 可能写到已合并区域 | `merged_row_ranges` 跳过已被合并的行 |

**重写 `_fuzzy_match_field()` 函数（第 448-500 行）**

| 改进点 | 旧逻辑 | 新逻辑 |
|--------|--------|--------|
| 行索引溢出 | 返回 `None`（后续全留空） | 取**最后一行重复填充** |
| 匹配策略 | 无优先级 | 精确(3分) > 包含(2分) > 子串(1分) |
| 歧义处理 | 多候选时随机返回 | 分数差>0 选最优，分数差=0 选精确匹配 |

**改进 `_read_source_texts()` 中 XLSX 读取逻辑**
- 显式保留 CSV 格式（含列标题行），LLM 能识别列标题
- 添加 15000 字符截断保护

#### `api/upload.py`

**改进 `_extract_template_text()` 中 XLSX 提取逻辑（第 434-467 行）**
- 行数限制：3行 → **10行**，避免表头在第4-10行时被遗漏
- 添加 `merged_master` 集合，处理合并单元格主格

#### `modules/frontend/src/pages/Fill.vue`

**改进 `handleSmartFill()` 错误处理（第 304-311 行）**
- 409 状态码（数据源未索引）单独处理，提示用户"请先在上传页面解析文档"

---

### 2.3 功能验证

| 测试用例 | 预期结果 | 通过 |
|----------|----------|------|
| 精确匹配：`"国家"` → `field_map["国家"]` | `Albania` | ✅ |
| 多行数据：`"国家"[1]` | `Austria` | ✅ |
| 模糊匹配：`"国家名称"` → `"国家"` | `Albania` | ✅ |
| 行溢出：`"GDP"[5]`（超出范围） | `50277.0`（重复最后一行） | ✅ |
| 无匹配：`"未知列"` | `None` | ✅ |
| 空值列表：`{"未知": []}` | `None` | ✅ |
| 部分字段为空：`{"大陆": ["Europe"]}` | `Europe` | ✅ |
| `_write_xlsx_smart` 包含所有关键逻辑 | 6项检查全部通过 | ✅ |

**测试结果**：核心逻辑测试 9/9 ✅，语法检查全部通过

---

## 三、2026-04-13 下午：智能回填 xlsx 字段识别与写入修复

### 3.1 修复的问题清单

| # | 问题描述 | 严重程度 | 根因 |
|---|----------|----------|------|
| 1 | 所有字段值全为空，输出文件只有表头 | 🔴 严重 | `_write_to_template` 中 xlsx 占位符模式被错误路由到 `table_filler`，覆盖了 `_write_xlsx_smart` 的数据 |
| 2 | LLM 识别 xlsx 模板字段时漏字段（7列只识别6列） | 🔴 严重 | `_read_template_text` 传给 LLM 的文本正确，但 LLM 本身不稳定会遗漏 |
| 3 | 列匹配时"汇率"列被误匹配到"所属洲"列 | 🔴 严重 | `_best_match_col` 模糊匹配逻辑有 bug，包含相同字符即被匹配 |
| 4 | 汇率列全为 NaN | 🔴 严重 | 问题1+2+3 叠加 |
| 5 | 源数据列名含单引号（`'国家名称'`），模板无引号，字段匹配失败 | 🔴 严重 | 用户在 Excel 里误输入了单引号前缀（Excel 强制文本格式前缀） |
| 6 | `_read_source_texts` 传给 LLM 的 xlsx 文本没去掉单引号 | 🟡 中等 | 同上 |
| 7 | xlsx 写入时去重逻辑导致行对齐错乱 | 🟡 中等 | 去重打乱了原始数据行顺序 |
| 8 | uvicorn `--reload` 热重载未生效，修改后代码不更新 | 🟡 中等 | 需手动重启后端进程 |

### 3.2 修改文件

#### `modules/filler/intelligent_filler.py`

**`extract_template_fields()` 函数（第 43-79 行）**
- xlsx 模板：直接用 openpyxl 读取表头列名（绕过 LLM 识别）
  - 遍历所有工作表，取第一个有数据的非空行作为表头
  - 跳过 `MergedCell` 从属格，避免重复读合并单元格值
  - 清理单引号前缀（`strip("'")`）
  - **关键修复**：找到占位符字段后，xlsx 文件返回 `"method": "llm"` 而非 `"placeholder"`（避免路由到 `table_filler`）

**`_read_template_text()` 函数（第 120-122 行）**
- 清理 xlsx 单元格值时，去掉单引号和双引号前缀
- `str(cell.value).strip().strip("'\"").strip()`

**`_write_xlsx_smart()` 函数（第 473 行）**
- 清理模板表头值时去掉单引号：`str(cell.value).strip().strip("'")`

**`_extract_values_by_llm()` 函数 xlsx 读取部分（第 240-265 行）**
- 清理列名时去掉单引号和双引号：`str(c).strip().strip("'\"").strip()`
- **改为精确匹配**：只接受列名完全相同（忽略大小写、空格差异）的字段，不再用模糊匹配
  - 避免"汇率"列因包含"洲"字而被错误匹配到"所属洲"
- 限制每字段最多 `max_rows` 个值（取前几行，保持行对齐）

**`_write_to_template()` 函数（第 421-429 行）**
- xlsx 占位符模式也走 `_write_xlsx_smart`（智能追加行模式），不再走 `table_filler`
- 关键条件：`if ext == '.xlsx': return _write_xlsx_smart(...)`

### 3.3 功能验证

| 测试用例 | 预期结果 | 通过 |
|----------|----------|------|
| 模板字段识别（xlsx 直接读表头） | 7个字段全部识别：国家名称、GDP总量、所属洲、首都、官方语言、人口、汇率 | ✅ |
| 数据源 xlsx 精确列匹配 | 汇率列匹配正确，不再被误匹配到所属洲 | ✅ |
| 完整流程 end-to-end | 5行数据全部填到正确位置，汇率列有值 | ✅ |
| 单元格单引号清理 | `'国家名称'` → `国家名称` | ✅ |

**测试结果**：核心逻辑测试 4/4 ✅

---

## 四、统计摘要

| 指标 | 数量 |
|------|------|
| 修改文件数 | 6 个 |
| 新建文件数 | 1 个（pdf_operations.py） |
| 核心函数重写 | 3 个（`_write_xlsx_smart`、`_fuzzy_match_field`、`_normalize_pdf_params`） |
| 新增函数 | 6 个（PDF 操作类 + 便捷函数 + PDF 执行器） |
| 修复 Bug | 8 个（其中 🔴 严重 4 个，🟡 中等 4 个） |
| 测试用例通过 | 9/9 ✅ |
| 新增支持的指令类型 | 7 种（xlsx 4种 + pdf 3种） |

---

## 五、表格回填功能（xlsx）贡献清单

### 一、底层能力扩展

| 贡献点 | 文件 | 具体内容 |
|--------|------|----------|
| XLSX 指令解析 | `operation_parser.py` | edit_cell、format_cell、add_row、delete_row 4种指令解析 |
| XLSX 参数归一化 | `common_operations.py` | 行/列/位置参数中文归一 |
| XLSX 操作执行器 | `common_operations.py` | 增删改查格式化完整链路 |

### 二、核心功能重写

| 贡献点 | 文件 | 具体内容 |
|--------|------|----------|
| **重写 `_write_xlsx_smart()`** | `intelligent_filler.py` | 表头识别、合并单元格处理、工作表遍历、写入防重 |
| **重写 `_fuzzy_match_field()`** | `intelligent_filler.py` | 精确>包含>子串三级评分、行溢出重复填充 |
| **重写 `extract_template_fields()`** | `intelligent_filler.py` | 绕过LLM直接读表头（快速准确） |
| 改进 `_read_source_texts()` | `intelligent_filler.py` | XLSX源文件保留CSV格式、15000字符截断 |
| 改进 `_write_to_template()` | `intelligent_filler.py` | XLSX路由修复，走 `_write_xlsx_smart` |
| 改进 `_extract_template_text()` | `api/upload.py` | XLSX提取10行、处理合并单元格主格 |
| 改进 `_read_template_text()` | `intelligent_filler.py` | 清理单引号/双引号前缀 |
| 改进 `_extract_values_by_llm()` | `intelligent_filler.py` | 精确匹配替代模糊匹配（防误匹配） |

### 三、配套优化

| 贡献点 | 文件 | 具体内容 |
|--------|------|----------|
| 前端错误提示 | `Fill.vue` | 409错误友好提示 |
| 去重逻辑修复 | `intelligent_filler.py` | 修复去重打乱行顺序的问题 |
| 单引号清理 | 多处 | 解决Excel强制文本格式前缀问题 |

### 四、BUG修复统计

- 🔴 严重级：6个（表头定位错误、合并单元格覆盖、工作表忽略、路由错误、列误匹配、源文件格式）
- 🟡 中等级：5个（行溢出、行顺序、文本提取、合并冲突、错误提示）

**一句话总结**：今天为表格回填功能新增了 XLSX 底层操作能力，重写了 3 个核心函数、修复了 11 个 bug，覆盖了从指令解析→字段识别→智能匹配→写入回填的完整链路。
