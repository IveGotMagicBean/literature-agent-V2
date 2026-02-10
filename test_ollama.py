#!/usr/bin/env python3
"""
测试Ollama连接 - 11434端口
"""

import requests
import sys

OLLAMA_URL = "http://localhost:11434"

print("=" * 60)
print("测试Ollama连接（端口11434）")
print("=" * 60)
print()

# 测试1: 检查Ollama服务
print("1. 测试Ollama服务...")
try:
    response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
    if response.status_code == 200:
        models = response.json().get('models', [])
        print(f"   ✅ Ollama运行正常")
        print(f"   📦 已安装 {len(models)} 个模型:")
        for model in models[:5]:
            print(f"      - {model['name']}")
    else:
        print(f"   ❌ Ollama响应异常: {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ 无法连接到Ollama: {e}")
    print(f"   请确保Ollama运行在 {OLLAMA_URL}")
    sys.exit(1)

print()

# 测试2: 测试生成
print("2. 测试文本生成...")
try:
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": "qwen2.5:14b",
            "prompt": "你好，请用一句话回答：1+1=?",
            "stream": False
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        answer = result.get('response', '')
        print(f"   ✅ 生成成功")
        print(f"   回答: {answer}")
    else:
        print(f"   ❌ 生成失败: {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ 生成失败: {e}")
    sys.exit(1)

print()

# 测试3: 测试流式生成
print("3. 测试流式生成...")
try:
    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": "qwen2.5:14b",
            "prompt": "你好",
            "stream": True
        },
        stream=True,
        timeout=30
    )
    
    if response.status_code == 200:
        print(f"   ✅ 流式生成正常")
        print(f"   流式输出: ", end='')
        
        import json
        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    text = chunk.get('response', '')
                    if text:
                        print(text, end='', flush=True)
                except:
                    pass
        print()
    else:
        print(f"   ❌ 流式生成失败: {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ 流式生成失败: {e}")
    sys.exit(1)

print()
print("=" * 60)
print("✅ 所有Ollama测试通过！")
print("=" * 60)
print()
print("Ollama配置正确，端口: 11434")
print("模型: qwen2.5:14b")
