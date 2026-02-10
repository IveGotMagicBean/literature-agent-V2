#!/bin/bash

# Literature Agent API 测试脚本

API_BASE="http://localhost:7860/api"

echo "======================================"
echo "  Literature Agent API 测试"
echo "======================================"
echo ""

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 测试1: 状态检查
echo "📊 测试1: 检查API状态"
echo "命令: curl $API_BASE/status"
echo ""
response=$(curl -s $API_BASE/status)
echo "响应: $response"
echo ""

# 解析是否已加载PDF
loaded=$(echo $response | grep -o '"loaded":[^,}]*' | cut -d':' -f2)
if [ "$loaded" = "true" ]; then
    echo -e "${GREEN}✅ PDF已加载${NC}"
else
    echo -e "${YELLOW}⚠️  PDF未加载，请先上传PDF${NC}"
    echo ""
    echo "提示: 先在浏览器上传PDF，或使用:"
    echo "curl -X POST $API_BASE/upload -F 'file=@your_paper.pdf'"
    exit 1
fi

echo ""
echo "======================================"
echo ""

# 测试2: 非流式问答
echo "📝 测试2: 非流式问答"
echo "问题: 你好"
echo "命令: curl -X POST $API_BASE/query -H 'Content-Type: application/json' -d '{\"question\":\"你好\"}'"
echo ""
response=$(curl -s -X POST $API_BASE/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"你好"}')

echo "响应:"
echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
echo ""

# 检查是否有答案
answer=$(echo $response | grep -o '"answer"' | wc -l)
if [ $answer -gt 0 ]; then
    echo -e "${GREEN}✅ 成功收到回答${NC}"
else
    echo -e "${RED}❌ 没有收到回答${NC}"
fi

echo ""
echo "======================================"
echo ""

# 测试3: 流式问答
echo "📡 测试3: 流式问答"
echo "问题: 这篇文章的主要贡献是什么？"
echo "命令: curl -X POST $API_BASE/query/stream -H 'Content-Type: application/json' -d '{\"question\":\"这篇文章的主要贡献是什么？\"}'"
echo ""
echo "流式响应（前10个事件）:"

curl -s -X POST $API_BASE/query/stream \
  -H 'Content-Type: application/json' \
  -d '{"question":"这篇文章的主要贡献是什么？"}' | head -20

echo ""
echo ""
echo -e "${GREEN}✅ 测试完成${NC}"
echo ""
echo "如果看到流式响应中有 'data: {...}' 格式的内容，说明API正常工作。"
echo "如果没有看到内容或者卡住，说明LLM调用有问题。"
