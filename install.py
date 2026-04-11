#!/usr/bin/env python3
"""
一键安装脚本
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description):
    """运行命令并显示进度"""
    print(f"\n📦 {description}...")
    print(f"   运行: {cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"   ✅ 成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ 失败")
        print(f"   错误: {e.stderr[:200]}")
        return False


def install_dependencies():
    """安装依赖"""
    print("="*60)
    print("  开始安装 Ollama Smart Router")
    print("="*60)
    
    # 升级 pip
    run_command(
        f"{sys.executable} -m pip install --upgrade pip",
        "升级 pip"
    )
    
    # 安装依赖
    if not run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "安装依赖包"
    ):
        return False
    
    # 可选：安装 openai
    print("\n📦 是否安装云端 API 支持 (openai)? [y/N]", end=" ")
    choice = input().strip().lower()
    if choice in ('y', 'yes'):
        run_command(
            f"{sys.executable} -m pip install openai",
            "安装 openai"
        )
    
    return True


def setup_ollama():
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
            model_names = [m.split()[0] for m in models if m.strip()]
            
            if model_names:
                print(f"\n✅ 已安装模型: {', '.join(model_names)}")
            else:
                print("\n⚠️  尚未安装任何模型")
                print("\n📥 建议下载模型:")
                print("   ollama pull gemma3:4b    # 小模型，快速")
                print("   ollama pull qwen2.5:7b   # 中模型，平衡")
                
                print("\n是否自动下载 gemma3:4b? [Y/n]", end=" ")
                choice = input().strip().lower()
                if choice not in ('n', 'no'):
                    print("\n⏳ 正在下载 gemma3:4b (可能需要几分钟)...")
                    subprocess.run(["ollama", "pull", "gemma3:4b"])
        else:
            print("\n❌ Ollama 未运行，请启动 Ollama 后再下载模型")
    except FileNotFoundError:
        print("\n❌ 未检测到 Ollama")
        print("   📥 请从 https://ollama.com 下载安装")
    except Exception as e:
        print(f"\n⚠️  检查 Ollama 时出错: {e}")


def create_shortcut():
    """创建快捷方式（可选）"""
    print("\n" + "="*60)
    print("  快捷方式")
    print("="*60)
    
    print("\n是否创建启动快捷脚本? [y/N]", end=" ")
    choice = input().strip().lower()
    
    if choice in ('y', 'yes'):
        # 创建启动脚本
        if sys.platform == "win32":
            script_content = '''@echo off
cd /d "%~dp0"
python -m src -i
'''
            script_name = "start.bat"
        else:
            script_content = '''#!/bin/bash
cd "$(dirname "$0")"
python3 -m src -i
'''
            script_name = "start.sh"
        
        script_path = Path(script_name)
        script_path.write_text(script_content, encoding='utf-8')
        
        if sys.platform != "win32":
            os.chmod(script_path, 0o755)
        
        print(f"   ✅ 已创建 {script_name}")
        print(f"   双击 {script_name} 即可启动交互模式")


def main():
    """主函数"""
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
        print(f"   当前版本: {sys.version}")
        return 1
    
    # 安装依赖
    if not install_dependencies():
        print("\n❌ 安装失败，请检查网络连接")
        return 1
    
    # 检查 Ollama
    setup_ollama()
    
    # 创建快捷方式
    create_shortcut()
    
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
