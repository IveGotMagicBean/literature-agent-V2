#!/bin/bash

# Literature Agent - 一键安装和启动脚本

set -e  # 遇到错误立即退出

echo "======================================"
echo "  Literature Agent - 自动安装"
echo "======================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查Python版本
echo "📋 检查Python环境..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "  Python版本: $python_version"

# 检查pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3未安装${NC}"
    echo "请先安装pip: sudo apt install python3-pip"
    exit 1
fi

# 安装依赖
echo ""
echo "📦 安装依赖包..."
echo "  这可能需要几分钟..."

pip3 install -q --upgrade pip

# 基础依赖
pip3 install -q fastapi==0.109.0 uvicorn[standard]==0.27.0 python-multipart==0.0.6
pip3 install -q requests==2.31.0 toml==0.10.2 aiofiles==23.2.1

# PDF处理
pip3 install -q PyMuPDF==1.23.0 pdfplumber==0.11.0

# 图像处理
pip3 install -q opencv-python==4.9.0.80 Pillow==10.2.0 numpy==1.26.3

# 文档生成
pip3 install -q python-pptx==0.6.23 python-docx==1.1.0 reportlab==4.0.9 markdown==3.5.2

echo -e "${GREEN}✅ 依赖安装完成${NC}"

# 检查配置文件
echo ""
echo "⚙️  检查配置..."
if [ ! -f "config/config.toml" ]; then
    echo -e "${YELLOW}⚠️  配置文件不存在，创建默认配置...${NC}"
    cp config/config.toml.example config/config.toml
    echo -e "${YELLOW}  请编辑 config/config.toml 设置LLM配置${NC}"
fi

# 创建必要目录
echo ""
echo "📁 创建目录..."
mkdir -p data data/images uploads

# 检查LLM配置
echo ""
echo "🤖 检查LLM配置..."

provider=$(grep -A 1 '^\[llm\]' config/config.toml | grep 'provider' | cut -d'"' -f2)
echo "  配置的provider: $provider"

if [ "$provider" = "ollama" ]; then
    echo ""
    echo "🔍 检测到Ollama配置"
    
    # 检查Ollama是否安装
    if ! command -v ollama &> /dev/null; then
        echo -e "${YELLOW}⚠️  Ollama未安装${NC}"
        echo ""
        echo "是否安装Ollama？(y/n)"
        read -r install_ollama
        
        if [ "$install_ollama" = "y" ]; then
            echo "📥 安装Ollama..."
            curl -fsSL https://ollama.com/install.sh | sh
            echo -e "${GREEN}✅ Ollama安装完成${NC}"
        fi
    fi
    
    # 检查Ollama服务
    if command -v ollama &> /dev/null; then
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Ollama服务正在运行${NC}"
            
            # 检查模型
            model=$(grep -A 3 '^\[llm.ollama\]' config/config.toml | grep 'model' | cut -d'"' -f2)
            echo "  配置的模型: $model"
            
            if ollama list | grep -q "$model"; then
                echo -e "${GREEN}✅ 模型已下载${NC}"
            else
                echo -e "${YELLOW}⚠️  模型未下载${NC}"
                echo ""
                echo "是否下载模型 $model？(y/n)"
                read -r download_model
                
                if [ "$download_model" = "y" ]; then
                    echo "📥 下载模型 $model..."
                    ollama pull "$model"
                    echo -e "${GREEN}✅ 模型下载完成${NC}"
                fi
            fi
        else
            echo -e "${YELLOW}⚠️  Ollama服务未运行${NC}"
            echo "  请在另一个终端运行: ollama serve"
            echo "  然后重新运行本脚本"
        fi
    fi
elif [ "$provider" = "openai" ]; then
    echo "  使用OpenAI API"
    if ! python3 -c "import openai" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  openai包未安装${NC}"
        echo "  安装中..."
        pip3 install -q openai
    fi
    echo -e "${GREEN}✅ OpenAI配置就绪${NC}"
    echo -e "${YELLOW}  请确保在config.toml中设置了API密钥${NC}"
elif [ "$provider" = "anthropic" ]; then
    echo "  使用Anthropic Claude"
    if ! python3 -c "import anthropic" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  anthropic包未安装${NC}"
        echo "  安装中..."
        pip3 install -q anthropic
    fi
    echo -e "${GREEN}✅ Anthropic配置就绪${NC}"
    echo -e "${YELLOW}  请确保在config.toml中设置了API密钥${NC}"
fi

# 测试导入
echo ""
echo "🧪 测试模块导入..."
python3 check_deps.py

# 完成
echo ""
echo "======================================"
echo -e "${GREEN}✅ 安装完成！${NC}"
echo "======================================"
echo ""
echo "下一步:"
echo "1. 检查 config/config.toml 配置"

if [ "$provider" = "ollama" ]; then
    echo "2. 确保Ollama服务运行: ollama serve"
    echo "3. 启动应用: python3 app.py"
else
    echo "2. 确保API密钥已设置"
    echo "3. 启动应用: python3 app.py"
fi

echo "4. 访问: http://localhost:7860"
echo ""

# 询问是否立即启动
echo "是否现在启动应用？(y/n)"
read -r start_now

if [ "$start_now" = "y" ]; then
    echo ""
    echo "🚀 启动应用..."
    python3 app.py
fi
