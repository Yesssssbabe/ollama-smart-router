#!/usr/bin/env python3
"""
一键安装脚本

修复内容 (2025-07-10):
1. 添加 --yes / --non-interactive 命令行参数，支持 CI/CD 无交互运行
2. 在 CI 环境 (CI 环境变量存在) 中自动跳过交互式输入
3. run_command 使用 shlex.split() 替代 str.split()，正确处理含空格路径
4. 修复 e.stderr[:200] 在 stderr 为 None 时的 TypeError → (e.stderr or '')[:200]
5. ollama pull 添加 timeout=300，避免无限挂起
6. script_path.write_text() 添加 try/except (OSError, PermissionError)
7. input() 添加 try/except EOFError，并设置默认选项
8. 统一输入提示默认选项为 [y/N]
9. 添加 pip 安装重试机制（3次）
10. 添加虚拟环境检测提示
"""

import argparse
import shlex
import subprocess
import sys
import os
from pathlib import Path


# 检测是否处于非交互环境
IS_CI = os.environ.get("CI", "").lower() in ("true", "1", "yes")
IS_NON_INTERACTIVE = not sys.stdin.isatty() or IS_CI


def run_command(cmd, description, retries=1):
    """运行命令并显示进度"""
    print(f"\n📦 {description}...")
    print(f"   运行: {cmd}")
    
    # 强制使用列表形式，如果是字符串则使用 shlex.split 安全分割
    if isinstance(cmd, str):
        cmd_parts = shlex.split(cmd)
    else:
        cmd_parts = list(cmd)
    
    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"   ✅ 成功")
            return True
        except subprocess.CalledProcessError as e:
            print(f"   ❌ 失败 (尝试 {attempt}/{retries})")
            stderr_msg = (e.stderr or '')[:200]
            print(f"   错误: {stderr_msg}")
            if attempt < retries:
                print(f"   🔄 正在重试...")
            else:
                return False
    return False


def ask_yes_no(prompt, default=False, auto_yes=False):
    """安全地询问用户 yes/no，处理 EOFError 和 CI 环境"""
    if auto_yes or IS_NON_INTERACTIVE:
        choice = 'y' if default else 'n'
        print(f"{prompt} {'Y/n' if default else 'y/N'} → {choice} (自动)")
        return choice == 'y'
    
    suffix = " [Y/n] " if default else " [y/N] "
    full_prompt = f"{prompt}{suffix}"
    
    try:
        choice = input(full_prompt).strip().lower()
        if not choice:
            return default
        return choice in ('y', 'yes')
    except EOFError:
        print(f"{'Y/n' if default else 'y/N'} → {'y' if default else 'n'} (默认)")
        return default
    except KeyboardInterrupt:
        print("\n   ⚠️  用户取消")
        return False


def install_dependencies(auto_yes=False):
    """安装依赖"""
    print("="*60)
    print("  开始安装 Ollama Smart Router")
    print("="*60)
    
    # 虚拟环境检测提示
    if not (hasattr(sys, 'real_prefix') or sys.base_prefix != sys.prefix):
        print("\n  ⚠️  警告: 未检测到虚拟环境")
        print("     建议: python -m venv venv")
    
    # 升级 pip
    run_command(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
        "升级 pip"
    )

    # 安装依赖（重试3次）
    if not run_command(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        "安装依赖包",
        retries=3
    ):
        return False

    # 可选：安装 openai
    if ask_yes_no("是否安装云端 API 支持 (openai)?", default=False, auto_yes=auto_yes):
        run_command(
            [sys.executable, "-m", "pip", "install", "openai"],
            "安装 openai"
        )
    
    return True


def setup_ollama(auto_yes=False):
    """检查并提示设置 Ollama"""
    print("\n" + "="*60)
    print("  Ollama 模型设置")
    print("="*60)
    
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            models = result.stdout.strip().split('\n')[1:]  # 跳过表头
            model_names = []
            for m in models:
                if m.strip():
                    parts = m.split()
                    if parts:
                        model_names.append(parts[0])
            
            if model_names:
                print(f"\n✅ 已安装模型: {', '.join(model_names)}")
            else:
                print("\n⚠️  尚未安装任何模型")
                print("\n📥 建议下载模型:")
                print("   ollama pull gemma3:4b    # 小模型，快速")
                print("   ollama pull qwen2.5:7b   # 中模型，平衡")
                
                if ask_yes_no("是否自动下载 gemma3:4b?", default=True, auto_yes=auto_yes):
                    print("\n⏳ 正在下载 gemma3:4b (可能需要几分钟)...")
                    try:
                        subprocess.run(
                            ["ollama", "pull", "gemma3:4b"],
                            timeout=300
                        )
                    except subprocess.TimeoutExpired:
                        print("   ❌ 下载超时，请稍后手动运行: ollama pull gemma3:4b")
                    except subprocess.CalledProcessError as e:
                        print(f"   ❌ 下载失败: {e}")
        else:
            print("\n❌ Ollama 未运行，请启动 Ollama 后再下载模型")
    except FileNotFoundError:
        print("\n❌ 未检测到 Ollama")
        print("   📥 请从 https://ollama.com 下载安装")
    except Exception as e:
        print(f"\n⚠️  检查 Ollama 时出错: {type(e).__name__}")


def create_shortcut(auto_yes=False):
    """创建快捷方式（可选）"""
    print("\n" + "="*60)
    print("  快捷方式")
    print("="*60)
    
    if not ask_yes_no("是否创建启动快捷脚本?", default=False, auto_yes=auto_yes):
        return
    
    # 创建启动脚本
    if sys.platform == "win32":
        script_content = '''@echo off
cd /d "%~dp0"
python -m src -i
'''
        script_name = "start.bat"
    else:
        script_content = '''#!/bin/bash
cd "$(dirname "$(readlink -f "$0")")"
python3 -m src -i
'''
        script_name = "start.sh"
    
    script_path = Path(script_name)
    
    # 检查文件是否存在
    if script_path.exists():
        if not ask_yes_no(f"{script_name} 已存在，是否覆盖?", default=False, auto_yes=auto_yes):
            print(f"   ⏭️  跳过创建快捷方式")
            return
    
    try:
        script_path.write_text(script_content, encoding='utf-8')
    except (OSError, PermissionError) as e:
        print(f"   ❌ 写入文件失败: {e}")
        print(f"   请手动创建 {script_name} 并写入以下内容:")
        print(script_content)
        return
    
    if sys.platform != "win32":
        try:
            os.chmod(script_path, 0o755)
        except OSError:
            print(f"   ⚠️  无法设置执行权限，请手动运行: chmod +x {script_name}")
    
    print(f"   ✅ 已创建 {script_name}")
    print(f"   双击 {script_name} 即可启动交互模式")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Ollama Smart Router 一键安装脚本"
    )
    parser.add_argument(
        "-y", "--yes", "--non-interactive",
        action="store_true",
        dest="auto_yes",
        help="非交互模式，自动回答所有提示为 yes (适合 CI/CD)"
    )
    args = parser.parse_args()
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🚀 Ollama Smart Router - 一键安装脚本                 ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # 检查 Python 版本
    if sys.version_info < (3, 9):
        print("❌ 需要 Python 3.9 或更高版本")
        print(f"   当前版本: {sys.version.split()[0]}")
        return 1
    
    # 安装依赖
    if not install_dependencies(auto_yes=args.auto_yes):
        print("\n❌ 安装失败，请检查网络连接")
        return 1
    
    # 检查 Ollama
    setup_ollama(auto_yes=args.auto_yes)
    
    # 创建快捷方式
    create_shortcut(auto_yes=args.auto_yes)
    
    # 完成
    print("\n" + "="*60)
    print("  ✅ 安装完成！")
    print("="*60)
    print("\n🎉 现在可以使用了！\n")
    print("快速测试:")
    print("   python -m src --status")
    print("   python -m src \"你好\"")
    print("   python -m src -i     # 交互模式")
    print("\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
