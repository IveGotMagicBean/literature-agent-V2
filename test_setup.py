"""
基础功能测试脚本
用于验证重构后的核心功能是否正常
"""

import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """测试所有核心模块是否可以正常导入"""
    print("🧪 测试模块导入...")
    
    try:
        from src.core.app_state import AppState
        print("  ✅ AppState")
        
        from src.core.llm_factory import create_llm, LLMWrapper
        print("  ✅ LLM Factory")
        
        from src.agents.smart_agent import SmartAgent
        print("  ✅ SmartAgent")
        
        from src.agents.ppt_agent import PPTAgent
        print("  ✅ PPTAgent")
        
        from src.agents.report_agent import ReportAgent
        print("  ✅ ReportAgent")
        
        from src.agents.subfigure_agent import SubfigureAgent
        print("  ✅ SubfigureAgent")
        
        from src.agents.intent_router import IntentRouter
        print("  ✅ IntentRouter")
        
        print("\n✅ 所有核心模块导入成功！")
        return True
        
    except ImportError as e:
        print(f"\n❌ 导入失败: {e}")
        return False


def test_config():
    """测试配置文件是否存在和格式是否正确"""
    print("\n🧪 测试配置...")
    
    config_path = Path("config/config.toml")
    
    if not config_path.exists():
        print("  ⚠️  配置文件不存在，将使用示例配置")
        example_path = Path("config/config.toml.example")
        if example_path.exists():
            print("  💡 请复制 config.toml.example 为 config.toml 并填入API密钥")
        return False
    
    try:
        import toml
        with open(config_path) as f:
            config = toml.load(f)
        
        # 检查必要的配置项
        required_keys = ['llm', 'system', 'generation', 'ui']
        missing = [k for k in required_keys if k not in config]
        
        if missing:
            print(f"  ❌ 缺少配置项: {missing}")
            return False
        
        print("  ✅ 配置文件格式正确")
        
        # 检查API密钥
        if config['llm']['api_key'] == 'your-api-key-here':
            print("  ⚠️  请配置真实的API密钥")
            return False
        
        print("  ✅ API密钥已配置")
        return True
        
    except Exception as e:
        print(f"  ❌ 配置文件解析失败: {e}")
        return False


def test_directories():
    """测试必要的目录是否存在"""
    print("\n🧪 测试目录结构...")
    
    required_dirs = [
        "static",
        "static/css",
        "static/js",
        "src/core",
        "src/api",
        "src/agents",
        "src/parsers",
        "src/generators",
        "src/utils",
        "config",
        "data",
        "uploads"
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"  ✅ {dir_path}")
        else:
            print(f"  ❌ {dir_path} (缺失)")
            all_exist = False
    
    return all_exist


def test_static_files():
    """测试静态文件是否存在"""
    print("\n🧪 测试静态文件...")
    
    required_files = [
        "static/index.html",
        "static/css/style.css",
        "static/js/app.js"
    ]
    
    all_exist = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} (缺失)")
            all_exist = False
    
    return all_exist


def main():
    """运行所有测试"""
    print("=" * 50)
    print("Literature Agent - 基础功能测试")
    print("=" * 50)
    
    results = {
        "模块导入": test_imports(),
        "目录结构": test_directories(),
        "静态文件": test_static_files(),
        "配置文件": test_config()
    }
    
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\n总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！项目已准备就绪。")
        print("\n下一步:")
        print("1. 确保config.toml中的API密钥已正确配置")
        print("2. 运行: python app.py")
        print("3. 访问: http://localhost:7860")
    else:
        print("\n⚠️  部分测试失败，请检查上述问题。")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
