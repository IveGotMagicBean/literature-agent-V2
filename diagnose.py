#!/usr/bin/env python3
"""
快速诊断脚本 - 检查Literature Agent的所有组件
"""

import sys
import subprocess
from pathlib import Path
import json

def check_ollama():
    """检查Ollama服务"""
    print("\n🔍 检查Ollama...")
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"  ✅ Ollama运行正常")
            print(f"  📦 已安装模型: {len(models)}个")
            for model in models[:3]:
                print(f"     - {model.get('name', 'unknown')}")
            return True
        else:
            print(f"  ❌ Ollama响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Ollama未运行: {e}")
        print("  💡 请运行: ollama serve")
        return False

def check_files():
    """检查必要文件"""
    print("\n🔍 检查文件结构...")
    
    required_files = {
        "app.py": "主应用",
        "config/config.toml": "配置文件",
        "static/index.html": "主页面",
        "static/js/app.js": "前端脚本",
        "static/css/style.css": "样式文件",
    }
    
    all_good = True
    for file, desc in required_files.items():
        path = Path(file)
        if path.exists():
            size = path.stat().st_size
            print(f"  ✅ {desc}: {file} ({size} bytes)")
        else:
            print(f"  ❌ {desc}: {file} (缺失)")
            all_good = False
    
    return all_good

def check_directories():
    """检查目录"""
    print("\n🔍 检查目录...")
    
    dirs = ["data", "uploads", "static", "src"]
    all_good = True
    
    for d in dirs:
        path = Path(d)
        if path.exists():
            print(f"  ✅ {d}/")
        else:
            print(f"  ❌ {d}/ (不存在，将自动创建)")
            path.mkdir(exist_ok=True)
            all_good = False
    
    return all_good

def check_dependencies():
    """检查Python依赖"""
    print("\n🔍 检查Python依赖...")
    
    packages = {
        "fastapi": "FastAPI框架",
        "uvicorn": "ASGI服务器",
        "requests": "HTTP客户端",
        "fitz": "PDF处理 (PyMuPDF)",
        "cv2": "图像处理 (opencv-python)",
        "pptx": "PPT生成 (python-pptx)",
        "docx": "Word生成 (python-docx)",
        "toml": "配置解析",
    }
    
    missing = []
    for package, desc in packages.items():
        try:
            __import__(package.replace("-", "_"))
            print(f"  ✅ {desc}")
        except ImportError:
            print(f"  ❌ {desc} (未安装)")
            missing.append(package)
    
    if missing:
        print(f"\n  💡 缺失的包: {', '.join(missing)}")
        print(f"  运行: pip install {' '.join(missing)}")
        return False
    
    return True

def check_config():
    """检查配置"""
    print("\n🔍 检查配置...")
    
    try:
        import toml
        with open("config/config.toml") as f:
            config = toml.load(f)
        
        provider = config.get("llm", {}).get("provider")
        print(f"  ✅ 配置文件格式正确")
        print(f"  📝 LLM Provider: {provider}")
        
        if provider == "ollama":
            model = config.get("llm", {}).get("ollama", {}).get("model")
            print(f"  📝 Ollama模型: {model}")
        
        return True
    except Exception as e:
        print(f"  ❌ 配置文件错误: {e}")
        return False

def test_api():
    """测试API"""
    print("\n🔍 测试API接口...")
    
    # 检查应用是否在运行
    try:
        import requests
        response = requests.get("http://localhost:7860/api/status", timeout=2)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ API运行正常")
            print(f"  📊 状态: {json.dumps(data, indent=4)}")
            return True
        else:
            print(f"  ❌ API响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ API未运行: {e}")
        print("  💡 请先运行: python app.py")
        return False

def main():
    print("=" * 60)
    print("Literature Agent - 系统诊断")
    print("=" * 60)
    
    results = {
        "文件结构": check_files(),
        "目录": check_directories(),
        "Python依赖": check_dependencies(),
        "配置文件": check_config(),
        "Ollama服务": check_ollama(),
        "API接口": test_api(),
    }
    
    print("\n" + "=" * 60)
    print("诊断结果汇总")
    print("=" * 60)
    
    for name, result in results.items():
        status = "✅ 正常" if result else "❌ 异常"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\n总计: {passed}/{total} 项检查通过")
    
    if passed == total:
        print("\n🎉 所有检查通过！系统运行正常。")
        print("\n访问: http://localhost:7860")
    else:
        print("\n⚠️  部分检查失败，请根据上述提示修复。")
        print("\n常见修复步骤:")
        print("1. 安装依赖: pip install -r requirements.txt")
        print("2. 启动Ollama: ollama serve")
        print("3. 启动应用: python app.py")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
