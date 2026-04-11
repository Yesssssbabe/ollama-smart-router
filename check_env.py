#!/usr/bin/env python3
"""
环境检查脚本 - 帮助用户快速诊断安装问题
"""

import sys
import subprocess
import os
from pathlib import Path


def print_section(title):
    """打印章节标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_status(item, status, detail=""):
    """打印状态"""
    icon = "✅" if status else "❌"
    print(f"  {icon} {item:<30} {detail}")


def check_python():
    """检查 Python 版本"""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    is_ok = version >= (3, 9)
    print_status(f"Python 版本", is_ok, version_str)
    if not is_ok:
        print("     ⚠️  需要 Python 3.9 或更高版本")
    return is_ok


def check_ollama():
    """检查 Ollama 是否安装和运行"""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            print_status("Ollama 已安装", True, version)
            
            # 检查 Ollama 是否在运行
            try:
                list_result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if list_result.returncode == 0:
                    models = [line.strip() for line in list_result.stdout.strip().split('\n') if line.strip()]
                    if len(models) > 1:  # 第一行是表头
                        model_count = len(models) - 1
                        print_status("Ollama 运行中", True, f"{model_count} 个模型")
                        # 显示已安装的模型
                        for model_line in models[1:4]:  # 最多显示3个
                            model_name = model_line.split()[0] if model_line.split() else "?"
                            print(f"        📦 {model_name}")
                    else:
                        print_status("Ollama 运行中", True, "无模型")
                        print("     ⚠️  建议运行: ollama pull gemma3:4b")
                    return True
            except:
                print_status("Ollama 运行状态", False, "无法连接")
                print("     ⚠️  请启动 Ollama 应用（任务栏羊驼图标）")
                return False
        else:
            print_status("Ollama 已安装", False, "")
            return False
    except FileNotFoundError:
        print_status("Ollama 已安装", False, "未找到")
        print("     📥 下载地址: https://ollama.com")
        return False
    except Exception as e:
        print_status("Ollama 检查失败", False, str(e))
        return False


def check_dependencies():
    """检查依赖包"""
    required = {
        "ollama": "ollama",
        "psutil": "psutil",
        "pyyaml": "yaml",
        "openai": "openai (可选，用于云端API)"
    }
    
    all_ok = True
    for package, import_name in required.items():
        try:
            if package == "openai":
                __import__(import_name.split()[0])
                print_status(f"{package}", True, "已安装 (可选)")
            else:
                __import__(import_name)
                print_status(f"{package}", True, "已安装")
        except ImportError:
            if package == "openai":
                print_status(f"{package}", False, "未安装 (可选)")
            else:
                print_status(f"{package}", False, "未安装")
                all_ok = False
    
    return all_ok


def check_gpu():
    """检查 GPU 情况"""
    print_section("GPU 状态（可选）")
    
    # 检查 NVIDIA GPU
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # 解析显存信息
            lines = result.stdout.split('\n')
            for line in lines:
                if 'MiB' in line and '/' in line:
                    # 提取显存信息
                    parts = line.split('|')
                    if len(parts) >= 3:
                        mem_info = parts[2].strip()
                        print(f"  🎮 NVIDIA GPU 检测到")
                        print(f"     显存: {mem_info}")
                        return True
            print_status("NVIDIA GPU", True, "已检测到")
            return True
    except:
        pass
    
    # 检查其他 GPU (macOS Metal 等)
    if sys.platform == "darwin":
        print_status("GPU 加速", True, "Metal (macOS)")
        return True
    
    print_status("独立 GPU", False, "未检测到")
    print("     💡 没有 GPU 也能运行，会使用 CPU 推理")
    return False


def check_project_files():
    """检查项目文件是否完整"""
    print_section("项目文件检查")
    
    required_files = [
        "src/router.py",
        "src/__init__.py",
        "requirements.txt",
        "config.yaml"
    ]
    
    all_ok = True
    for file in required_files:
        path = Path(file)
        exists = path.exists()
        print_status(file, exists, "存在" if exists else "缺失")
        if not exists:
            all_ok = False
    
    return all_ok


def print_summary(results):
    """打印总结"""
    print_section("检查总结")
    
    must_ok = all([
        results["python"],
        results["files"]
    ])
    
    if must_ok and results["ollama"]:
        print("  ✅ 环境检查通过！可以开始使用")
        print("\n  🚀 快速开始:")
        print("     python -m src --status")
        print("     python -m src \"你好\"")
    elif must_ok and not results["ollama"]:
        print("  ⚠️  需要安装并启动 Ollama")
        print("\n  📥 下载地址: https://ollama.com")
        print("  📦 安装后运行: ollama pull gemma3:4b")
    elif not results["dependencies"]:
        print("  ⚠️  缺少依赖包")
        print("\n  🔧 修复方法:")
        print("     pip install -r requirements.txt")
    else:
        print("  ❌ 环境检查未通过")
        print("\n  🔧 请根据上方提示修复问题")


def main():
    """主函数"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🔍 Ollama Smart Router - 环境检查工具                 ║
║                                                           ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    results = {
        "python": False,
        "ollama": False,
        "dependencies": False,
        "files": False,
        "gpu": False
    }
    
    # 检查 Python
    print_section("Python 环境")
    results["python"] = check_python()
    
    # 检查项目文件
    results["files"] = check_project_files()
    
    # 检查 Ollama
    print_section("Ollama 检查")
    results["ollama"] = check_ollama()
    
    # 检查依赖
    print_section("依赖包检查")
    results["dependencies"] = check_dependencies()
    
    # 检查 GPU
    results["gpu"] = check_gpu()
    
    # 打印总结
    print_summary(results)
    
    print("\n" + "="*60)
    print("  检查完成！")
    print("="*60 + "\n")
    
    # 返回状态码
    return 0 if results["python"] and results["files"] else 1


if __name__ == "__main__":
    sys.exit(main())
