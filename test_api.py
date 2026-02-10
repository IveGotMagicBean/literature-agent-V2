#!/usr/bin/env python3
"""
API测试脚本 - 用于调试问答功能
"""

import requests
import json
import sys

API_BASE = "http://localhost:7860/api"

def test_status():
    """测试状态接口"""
    print("=" * 60)
    print("测试1: 检查API状态")
    print("=" * 60)
    
    try:
        response = requests.get(f"{API_BASE}/status", timeout=5)
        data = response.json()
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if data.get("loaded"):
            print("✅ PDF已加载")
            return True
        else:
            print("⚠️  PDF未加载，请先上传PDF")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_query_simple():
    """测试简单问答"""
    print("\n" + "=" * 60)
    print("测试2: 非流式问答 - 简单问题")
    print("=" * 60)
    
    question = "你好"
    print(f"问题: {question}")
    
    try:
        response = requests.post(
            f"{API_BASE}/query",
            json={"question": question},
            timeout=30
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if data.get("answer"):
                print(f"\n✅ 收到回答: {data['answer'][:100]}...")
                return True
            else:
                print("❌ 回答为空")
                return False
        else:
            print(f"❌ 请求失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_query_stream():
    """测试流式问答"""
    print("\n" + "=" * 60)
    print("测试3: 流式问答")
    print("=" * 60)
    
    question = "这篇文章的主要贡献是什么？"
    print(f"问题: {question}")
    print("\n流式响应:")
    print("-" * 60)
    
    try:
        response = requests.post(
            f"{API_BASE}/query/stream",
            json={"question": question},
            stream=True,
            timeout=60
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ 请求失败: {response.text}")
            return False
        
        event_count = 0
        has_answer = False
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    event_count += 1
                    try:
                        event_data = json.loads(line_str[6:])
                        event_type = event_data.get('type', 'unknown')
                        
                        # 打印前几个事件
                        if event_count <= 10:
                            print(f"事件 {event_count}: {event_type}")
                            if event_data.get('content'):
                                content = event_data['content'][:50]
                                print(f"  内容: {content}...")
                        
                        # 检查是否有答案
                        if event_type in ['answer', 'answer_chunk']:
                            has_answer = True
                            
                    except json.JSONDecodeError as e:
                        print(f"  JSON解析错误: {e}")
                        print(f"  原始数据: {line_str[:100]}")
        
        print("-" * 60)
        print(f"总共收到 {event_count} 个事件")
        
        if has_answer:
            print("✅ 收到答案内容")
            return True
        else:
            print("❌ 没有收到答案")
            return False
            
    except requests.Timeout:
        print("❌ 请求超时（60秒）")
        print("   这可能是因为Ollama响应太慢")
        return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_direct_llm():
    """直接测试Ollama"""
    print("\n" + "=" * 60)
    print("测试4: 直接测试Ollama")
    print("=" * 60)
    
    try:
        # 测试Ollama是否可用
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"✅ Ollama运行正常，已安装 {len(models)} 个模型")
            for model in models[:3]:
                print(f"  - {model.get('name')}")
        else:
            print(f"❌ Ollama响应异常: {response.status_code}")
            return False
        
        # 测试生成
        print("\n测试生成文本...")
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:14b",
                "prompt": "你好，请简短回答：1+1等于几？",
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('response', '')
            print(f"✅ Ollama生成成功: {answer[:100]}")
            return True
        else:
            print(f"❌ Ollama生成失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Ollama测试失败: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("  Literature Agent - API调试工具")
    print("=" * 60)
    print()
    
    # 运行所有测试
    results = {}
    
    results["状态检查"] = test_status()
    
    if results["状态检查"]:
        results["简单问答"] = test_query_simple()
        results["流式问答"] = test_query_stream()
    else:
        print("\n⚠️  跳过问答测试（需要先上传PDF）")
        results["简单问答"] = None
        results["流式问答"] = None
    
    results["Ollama测试"] = test_direct_llm()
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, result in results.items():
        if result is True:
            status = "✅ 通过"
        elif result is False:
            status = "❌ 失败"
        else:
            status = "⏭️  跳过"
        print(f"{name}: {status}")
    
    # 诊断建议
    print("\n" + "=" * 60)
    print("诊断建议")
    print("=" * 60)
    
    if not results["状态检查"]:
        print("❌ API连接失败")
        print("  1. 确认应用正在运行: python app.py")
        print("  2. 确认端口正确: localhost:7860")
    elif results["状态检查"] and results.get("简单问答") is None:
        print("⚠️  需要先上传PDF")
        print("  在浏览器中上传PDF后重新运行此脚本")
    elif results.get("简单问答") is False:
        print("❌ 问答功能异常")
        print("  可能原因:")
        print("  1. LLM调用失败 - 检查服务器终端的 [ERROR] 日志")
        print("  2. IntentRouter问题 - 查看完整错误堆栈")
        print("  3. 消息格式错误 - 检查 smart_agent.py 中的 LLM 调用")
    elif results.get("流式问答") is False:
        print("❌ 流式响应异常")
        print("  可能原因:")
        print("  1. Ollama响应太慢 - 尝试使用更小的模型")
        print("  2. stream_chat方法问题 - 检查 llm_factory.py")
    
    if not results["Ollama测试"]:
        print("\n❌ Ollama不可用")
        print("  1. 启动Ollama: ollama serve")
        print("  2. 检查模型: ollama list")
        print("  3. 拉取模型: ollama pull qwen2.5:14b")
    
    if all(r is True for r in results.values() if r is not None):
        print("\n🎉 所有测试通过！")
    
    return all(r is not False for r in results.values())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
