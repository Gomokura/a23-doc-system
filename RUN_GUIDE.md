# 智能文档系统 - 运行指南

## 目录

- [环境要求](#环境要求)
- [第一步：安装 Ollama](#第一步安装-ollama)
- [第二步：下载 AI 模型](#第二步下载-ai-模型)
- [第三步：配置项目](#第三步配置项目)
- [第四步：安装依赖](#第四步安装依赖)
- [第五步：启动服务](#第五步启动服务)
- [常见问题](#常见问题)

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11、macOS、Linux |
| 内存 | 最低 8GB（推荐 16GB） |
| 磁盘空间 | 至少 10GB 可用空间 |
| Python | 3.10 或更高版本 |

---

## 第一步：安装 Ollama

Ollama 是本地运行 AI 模型的工具。

### Windows/Mac

1. 访问 https://ollama.com/download
2. 下载并安装对应版本
3. 安装完成后，Ollama 会自动在后台运行

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 验证安装

```bash
ollama --version
```

---

## 第二步：下载 AI 模型

打开终端（Windows 用 PowerShell 或 CMD），依次运行以下命令：

```bash
# 1. 下载文本处理模型（用于问答、摘要、实体抽取）
ollama pull qwen2.5:1.5b

# 2. 下载视觉模型（用于 PDF 图片识别，可选）
ollama pull qwen2.5vl:3b

# 3. 下载文本嵌入模型（用于文档检索）
ollama pull nomic-embed-text
```

> **注意**：如果网络较慢，可以使用代理或科学上网。模型下载需要一些时间。

### 验证模型

```bash
ollama list
```

应该看到：
```
NAME                ID          SIZE      MODIFIED
qwen2.5:1.5b       xxx         986 MB    ...
qwen2.5vl:3b       xxx         3.2 GB    ...
nomic-embed-text    xxx         274 MB    ...
```

---

## 第三步：配置项目

### 3.1 下载项目代码

```bash
git clone https://github.com/Gomokura/a23-doc-system.git
cd a23-doc-system
git checkout feat/retriever-lhh
```

### 3.2 复制环境配置文件

```bash
# 在项目根目录下
copy .env.example .env    # Windows
# 或
cp .env.example .env     # Linux/Mac
```

### 3.3 编辑 .env 文件

用文本编辑器打开 `.env` 文件，配置如下：

```env
# LLM 配置（使用 Ollama 本地部署，完全免费）
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:1.5b

# PDF 视觉模型（留空则用文本模型处理 PDF）
PDF_VLM_MODEL=qwen2.5vl:3b

# 嵌入模型
EMBED_MODEL=nomic-embed-text

# 数据库路径
CHROMA_PATH=./db/chroma
SQLITE_PATH=./db/app.db

# 文件目录
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs

# 服务配置
HOST=0.0.0.0
PORT=8000
```

---

## 第四步：安装依赖

### 4.1 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows PowerShell:
.\venv\Scripts\activate
# Windows CMD:
venv\Scripts\activate.bat
# Linux/Mac:
source venv/bin/activate
```

### 4.2 安装 Python 包

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **注意**：如果安装失败，尝试：
> ```bash
> pip install --no-cache-dir -r requirements.txt
> ```

### 4.3 安装前端依赖

```bash
cd modules/frontend
npm install
cd ../..
```

---

## 第五步：启动服务

### 5.1 确保 Ollama 运行中

```bash
ollama serve
```

如果没有报错，说明 Ollama 正在运行。

### 5.2 启动后端服务

新开一个终端窗口：

```bash
# 激活虚拟环境
.\venv\Scripts\activate   # Windows
# 或
source venv/bin/activate   # Linux/Mac

# 启动服务
python -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
```

看到以下信息说明启动成功：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### 5.3 启动前端（可选）

再开一个终端窗口：

```bash
cd modules/frontend
npm run dev
```

看到以下信息说明启动成功：
```
VITE ready in xxx ms
Local: http://localhost:5173/
```

---

## 访问系统

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |

---

## 常见问题

### Q1: Ollama 下载模型失败

**解决方法**：
1. 确保网络畅通
2. 使用代理：
   ```bash
   # Windows PowerShell
   $env:HTTPS_PROXY = "http://127.0.0.1:7890"
   # Linux/Mac
   export HTTPS_PROXY="http://127.0.0.1:7890"
   ```
3. 手动下载模型文件

### Q2: pip 安装依赖失败

**解决方法**：
1. 升级 pip：`pip install --upgrade pip`
2. 使用国内镜像：
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

### Q3: 内存不足 (Out of Memory)

**解决方法**：
1. 关闭其他占用内存的程序
2. 减小 Ollama 模型大小：
   ```bash
   ollama pull qwen2.5:0.5b   # 使用更小的模型
   ```
3. 在 .env 中注释掉 PDF_VLM_MODEL（跳过 PDF 图片识别）

### Q4: 端口被占用

**解决方法**：
1. 查找占用端口的进程：
   ```bash
   # Windows
   netstat -ano | findstr :8000
   # Linux/Mac
   lsof -i :8000
   ```
2. 关闭该进程或使用其他端口：
   ```bash
   python -m uvicorn main:app --port 8001
   ```

### Q5: 前端 npm install 失败

**解决方法**：
1. 清理缓存：
   ```bash
   npm cache clean --force
   rm -rf node_modules
   npm install
   ```
2. 使用淘宝镜像：
   ```bash
   npm install --registry=https://registry.npmmirror.com
   ```

### Q6: 找不到模块 'xxx'

**解决方法**：
1. 确保虚拟环境已激活（激活后命令行前有 `(venv)` 标记）
2. 重新安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

### Q7: 服务启动后无法访问

**解决方法**：
1. 检查防火墙设置
2. 确保使用正确地址：
   - 本机访问：http://localhost:8000
   - 局域网访问：http://你的IP地址:8000

---

## 快速检查清单

运行前确认以下项目：

- [ ] Ollama 已安装并运行
- [ ] 已下载所有模型（`ollama list`）
- [ ] 已创建虚拟环境
- [ ] 已安装 Python 依赖
- [ ] .env 文件已配置
- [ ] 端口 8000 和 5173 未被占用

---
