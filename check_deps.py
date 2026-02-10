#!/usr/bin/env python3
"""
依赖检查和安装脚本
"""

import subprocess
import sys

# 必需的基础依赖
REQUIRED_PACKAGES = [
    "fastapi==0.109.0",
    "uvicorn[standard]==0.27.0",
    "python-multipart==0.0.6",
    "requests==2.31.0",
    "PyMuPDF==1.23.0",
    "pdfplumber==0.11.0",
    "opencv-python==4.9.0.80",
    "Pillow==10.2.0",
    "numpy==1.26.3",
    "python-pptx==0.6.23",
    "python-docx==1.1.0",
    "reportlab==4.0.9",
    "markdown==3.5.2",
    "toml==0.10.2",
    "aiofiles==23.2.1"
]

# 可选的LLM依赖
OPTIONAL_PACKAGES = {
    "openai": "openai==1.10.0",
    "anthropic": "anthropic==0.18.1"
}


def check_package(package_name):
    """检查包是否已安装"""
    try:
        __import__(package_name.replace("-", "_").split("==")[0])
        return True
    except ImportError:
        return False


def install_package(package):
    """安装包"""
    print(f"📦 安装 {package}...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package, "-q"],
            stdout=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    print("=" * 60)
    print("Literature Agent - 依赖检查")
    print("=" * 60)
    print()
    
    missing = []
    
    # 检查必需依赖
    print("🔍 检查必需依赖...")
    for package in REQUIRED_PACKAGES:
        package_name = package.split("==")[0].replace("-", "_")
        if package_name == "uvicorn[standard]":
            package_name = "uvicorn"
        
        if check_package(package_name):
            print(f"  ✅ {package_name}")
        else:
            print(f"  ❌ {package_name} (未安装)")
            missing.append(package)
    
    print()
    
    # 询问是否安装缺失的包
    if missing:
        print(f"发现 {len(missing)} 个缺失的依赖包")
        response = input("是否自动安装？(y/n): ").lower().strip()
        
        if response == 'y':
            print("\n📦 开始安装...")
            failed = []
            
            for package in missing:
                if install_package(package):
                    print(f"  ✅ {package.split('==')[0]} 安装成功")
                else:
                    print(f"  ❌ {package.split('==')[0]} 安装失败")
                    failed.append(package)
            
            if failed:
                print(f"\n⚠️  {len(failed)} 个包安装失败")
                print("请手动运行: pip install -r requirements.txt")
                return False
            else:
                print("\n✅ 所有依赖安装成功！")
        else:
            print("\n请手动运行: pip install -r requirements.txt")
            return False
    else:
        print("✅ 所有必需依赖已安装")
    
    # 检查可选依赖
    print("\n🔍 检查可选依赖 (LLM提供商)...")
    
    # 读取配置
    try:
        import toml
        with open("config/config.toml") as f:
            config = toml.load(f)
        
        provider = config.get("llm", {}).get("provider", "ollama")
        print(f"  当前配置: {provider}")
        
        if provider == "openai":
            if not check_package("openai"):
                print("  ⚠️  需要安装 openai")
                print("  运行: pip install openai")
        elif provider == "anthropic":
            if not check_package("anthropic"):
                print("  ⚠️  需要安装 anthropic")
                print("  运行: pip install anthropic")
        else:
            print("  ✅ 使用Ollama，无需额外依赖")
    
    except Exception as e:
        print(f"  ⚠️  无法读取配置: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 依赖检查完成")
    print("=" * 60)
    print("\n下一步:")
    print("1. 确保配置文件已设置: config/config.toml")
    print("2. 如使用Ollama: 运行 ollama serve")
    print("3. 启动应用: python app.py")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
