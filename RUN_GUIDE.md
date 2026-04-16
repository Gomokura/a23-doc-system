# 运行指南

## 目录

- [环境要求](#环境要求)
- [第一步：配置 API Key](#第一步配置-api-key)
- [第二步：安装后端依赖](#第二步安装后端依赖)
- [第三步：启动后端](#第三步启动后端)
- [第四步：安装并启动前端](#第四步安装并启动前端)
- [访问系统](#访问系统)
- [常见问题](#常见问题)

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11、macOS、Linux |
| Python | 3.11+（推荐 3.11） |
| Node.js | 18+（用于前端） |
| 内存 | 最低 4GB（无需本地 GPU） |
| 网络 | 需要访问 SiliconFlow API（国内可直连） |

> 本系统使用云端 LLM/VLM/Embedding API，**不需要本地 GPU，不需要安装 Ollama**。

---

## 第一步：配置 API Key

编辑项目根目录下的 `config.py`，填入你的 SiliconFlow API Key：

```python
llm_api_key: str = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
```

SiliconFlow 注册地址：https://cloud.siliconflow.cn
注册后在「API 密钥」页面创建 Key，新用户有免费额度。

其余配置项一般无需修改，默认值如下：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `llm_model` | `Qwen/Qwen2.5-72B-Instruct` | 问答/填表主模型 |
| `vlm_model` | `Qwen/Qwen2-VL-72B-Instruct` | 扫描件 PDF OCR |
| `embed_model` | `BAAI/bge-m3` | 向量检索 Embedding |
| `host` | `0.0.0.0` | 后端监听地址 |
| `port` | `8000` | 后端端口 |

---

## 第二步：安装后端依赖

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
# Windows PowerShell:
.\venv\Scripts\activate
# Windows CMD:
venv\Scripts\activate.bat
# Linux/Mac:
source venv/bin/activate

# 3. 安装依赖
pip install --upgrade pip
pip install -r requirements.txt
```

如果安装较慢，可使用国内镜像：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 第三步：启动后端

**Windows（推荐）：** 直接双击 `start_backend.bat`

**命令行：**

```bash
# 确保虚拟环境已激活
python main.py
```

看到以下输出说明启动成功：

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

首次启动时，系统会自动创建 SQLite 数据库和 ChromaDB 向量库目录，无需手动初始化。

---

## 第四步：安装并启动前端

新开一个终端窗口：

```bash
cd modules/frontend
npm install
npm run dev
```

看到以下输出说明启动成功：

```
VITE v6.x.x  ready in xxx ms
➜  Local:   http://localhost:5173/
```

如果 npm 安装较慢，可使用淘宝镜像：

```bash
npm install --registry=https://registry.npmmirror.com
```

---

## 访问系统

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档（Swagger） | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |

---

## 使用流程

```
1. 上传页面  →  上传文档（docx/xlsx/pdf/txt/md），点击「解析」等待索引完成
2. 问答页面  →  选择文档，输入问题，获取答案与溯源
3. 填表页面  →  上传模板，选择数据源，输入筛选条件，预览后确认填写，下载结果
4. 文档操作  →  选择文件，输入自然语言指令（如"删除成绩小于60的行"），预览后执行
```

---

## 常见问题

### Q1: API Key 无效 / 401 错误

检查 `config.py` 中的 `llm_api_key` 是否正确填写，注意不要有多余空格。
SiliconFlow 控制台确认 Key 状态正常且有余额。

### Q2: pip 安装依赖失败

```bash
# 升级 pip 后重试
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
```

### Q3: 端口被占用

```bash
# Windows 查找占用 8000 端口的进程
netstat -ano | findstr :8000
# 关闭该进程，或修改 config.py 中的 port 值
```

前端端口冲突时，修改 `modules/frontend/vite.config.ts` 中的 `server.port`。

### Q4: 前端 npm install 失败

```bash
cd modules/frontend
rm -rf node_modules
npm cache clean --force
npm install --registry=https://registry.npmmirror.com
```

### Q5: 换了 Embedding 模型后报维度错误

系统会自动检测维度变化并重建索引，无需手动操作。如果仍有问题，删除 `db/chroma/` 目录后重启后端即可。

### Q6: 扫描件 PDF 识别效果差

扫描件走云端 VLM（Qwen2-VL-72B）OCR，识别准确率约 85%。确保网络正常、API 余额充足。文字型 PDF 走 PyMuPDF 直接提取，准确率接近 100%。

### Q7: 填表响应时间较长

- xlsx 数据源：行筛选约 8-10s（LLM 解析意图 1 次 + pandas 执行）
- 纯文字 docx 数据源：并发批量提取，约 15-30s（取决于段落数量）
- 多表模板：每个表格独立筛选，时间随表格数量线性增加

---

## 启动前检查清单

- [ ] `config.py` 中已填入有效的 SiliconFlow API Key
- [ ] Python 虚拟环境已激活，依赖已安装
- [ ] 后端已启动（http://localhost:8000/health 返回 200）
- [ ] 前端已启动（http://localhost:5173 可访问）
- [ ] 端口 8000 和 5173 未被其他程序占用
