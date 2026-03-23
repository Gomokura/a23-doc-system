#!/bin/bash
# A23 一键启动脚本 - 负责人: 成员1
# 用法: bash run.sh

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  A23 文档理解与多源数据融合系统"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件，正在从 .env.example 复制..."
    cp .env.example .env
    echo "✅ 已创建 .env，请填入真实的 API Key 后重新运行"
    exit 1
fi

# 创建必要目录
mkdir -p uploads outputs db/chroma

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 检查依赖..."
pip install -r requirements.txt -q

echo ""
echo "🚀 启动后端服务..."
echo "   API 文档: http://localhost:8000/docs"
echo "   健康检查: http://localhost:8000/health"
echo ""

# 启动 FastAPI
python main.py
