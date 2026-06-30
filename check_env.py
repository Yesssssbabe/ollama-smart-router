#!/usr/bin/env python3
"""
环境检查脚本 - 帮助用户快速诊断安装问题

修复内容 (2025-07-10):
1. 修复裸 except: 捕获系统异常 (CRIT-2) → 使用具体异常类型
2. 修复 model_line.split()[0] 的 IndexError 风险 → 添加长度检查
3. 限制异常信息长度，避免敏感信息泄露，仅打印异常类型
4. 补全 required_files 列表，新增 src/config_loader.py、src/gpu_monitor.py 等关键文件
5. 统一超时处理，所有 subprocess.run 添加 timeout 参数
6. 增加 KeyboardInterrupt 独立处理，确保 Ctrl+C 可中断程序
"""

import sys
import subprocess
import os
import logging
from pathlib import Path

# 初始化日志（可选，无配置文件时回退到默认）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


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
                            parts = model_line.split()
                            model_name = parts[0] if parts else "unknown"
                            print(f"        📦 {model_name}")
                    else:
                        print_status("Ollama 运行中", True, "无模型")
                        print("     ⚠️  建议运行: ollama pull gemma3:4b")
                    return True
            except subprocess.TimeoutExpired:
                print_status("Ollama 运行状态", False, "查询超时")
                print("     ⚠️  Ollama 响应缓慢，请检查服务状态")
                return False
            except FileNotFoundError:
                print_status("Ollama 运行状态", False, "命令未找到")
                print("     ⚠️  请确保 Ollama 已安装并添加到 PATH")
                return False
            except subprocess.CalledProcessError as e:
                print_status("Ollama 运行状态", False, f"返回错误码 {e.returncode}")
                return False
            except Exception as e:
                # 保留未知异常的信息，但不吞没 KeyboardInterrupt
                print_status("Ollama 运行状态", False, f"未知错误: {type(e).__name__}")
                logger.debug(f"Ollama 运行检查详细错误: {e}")
                return False
        else:
            print_status("Ollama 已安装", False, "")
            return False
    except FileNotFoundError:
        print_status("Ollama 已安装", False, "未找到")
        print("     📥 下载地址: https://ollama.com")
        return False
    except Exception as e:
        print_status("Ollama 检查失败", False, f"{type(e).__name__}")
        logger.debug(f"Ollama 检查详细错误: {e}")
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
    except subprocess.TimeoutExpired:
        print_status("NVIDIA GPU", False, "nvidia-smi 超时")
        return False
    except FileNotFoundError:
        pass  # 继续检查其他GPU
    except subprocess.CalledProcessError:
        print_status("NVIDIA GPU", False, "nvidia-smi 返回错误")
        return False
    except Exception as e:
        print_status("NVIDIA GPU", False, f"检测失败: {type(e).__name__}")
        logger.debug(f"GPU 检查详细错误: {e}")
        return False
    
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
        "src/complexity_analyzer.py",
        "src/gpu_monitor.py",
        "src/config_loader.py",
        "src/cli.py",
        "requirements.txt",
        "config.yaml",
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
    
    try:
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
    except KeyboardInterrupt:
        print("\n\n  ⚠️ 检查被用户中断")
        return 130
    
    print("\n" + "="*60)
    print("  检查完成！")
    print("="*60 + "\n")
    
    # 返回状态码
    return 0 if results["python"] and results["files"] and results["ollama"] else 1


if __name__ == "__main__":
    sys.exit(main())
