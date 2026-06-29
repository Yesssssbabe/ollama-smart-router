"""
命令行交互界面
"""

import argparse
import os
import sys
from typing import Optional

from .router import SmartRouter, RouterConfig, RoutingStrategy
from .gpu_monitor import GPUMonitor, CPUMonitor
from .config_loader import config_from_yaml, merge_env_vars


def create_parser() -> argparse.ArgumentParser:
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        description="Ollama Smart Router - 智能模型调度器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "解释快速排序算法"
  %(prog)s --strategy gpu "写个Python函数"
  %(prog)s --interactive
  %(prog)s --list-models
        """
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        help="输入提示词"
    )

    parser.add_argument(
        "-s", "--strategy",
        choices=["auto", "gpu", "cpu", "cloud"],
        default="auto",
        help="路由策略 (默认: auto)"
    )

    parser.add_argument(
        "-c", "--complexity",
        choices=["simple", "medium", "complex"],
        help="手动指定任务复杂度"
    )

    parser.add_argument(
        "-m", "--model",
        help="指定模型 (覆盖自动选择，用于强制策略时)"
    )

    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="交互模式"
    )

    parser.add_argument(
        "--list-models",
        action="store_true",
        help="列出可用模型"
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="显示硬件状态"
    )

    parser.add_argument(
        "--cloud-key",
        help="云端API密钥"
    )

    parser.add_argument(
        "--config",
        default="config.yaml",
        help="配置文件路径 (默认: config.yaml)"
    )

    return parser


def interactive_mode(router: SmartRouter):
    """交互模式"""
    print("=" * 50)
    print("🤖 Ollama Smart Router - 交互模式")
    print("=" * 50)
    print("命令: /quit (退出), /status (状态), /stats (统计)")
    print("-" * 50)

    while True:
        try:
            prompt = input("\n你: ").strip()

            if not prompt:
                continue

            if prompt == "/quit":
                print("再见!")
                break
            elif prompt == "/status":
                router.gpu_monitor.print_status()
                router.cpu_monitor.print_status()
                continue
            elif prompt == "/stats":
                router.print_stats()
                continue
            elif prompt.startswith("/"):
                print(f"未知命令: {prompt}")
                continue

            print()
            result = router.route(prompt)
            print(f"\n🤖 ({result.source}): {result.content}")

        except KeyboardInterrupt:
            print("\n再见!")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")


def print_error(message):
    """打印错误信息"""
    print(f"\n❌ {message}\n")


def print_tip(message):
    """打印提示信息"""
    print(f"💡 {message}")


def check_ollama_connection():
    """检查 Ollama 连接"""
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


def print_ollama_error():
    """打印 Ollama 错误提示"""
    print_error("无法连接到 Ollama")
    print("可能的原因：")
    print("  1. Ollama 未安装")
    print("  2. Ollama 未运行（任务栏没有羊驼图标）")
    print("\n解决方法：")
    print("  • 下载安装: https://ollama.com")
    print("  • 启动 Ollama 应用")
    print("  • 命令行测试: ollama list")


def load_config(args) -> RouterConfig:
    """根据命令行参数加载配置"""
    # 从 YAML 加载
    config_path = args.config if args.config and os.path.exists(args.config) else None
    config = config_from_yaml(config_path)

    # 环境变量覆盖
    config = merge_env_vars(config)

    # 命令行参数覆盖
    if args.cloud_key:
        config.cloud_api_key = args.cloud_key
    if args.model:
        # 如果用户指定了模型，强制使用该模型作为 small/medium/large
        config.small_model = args.model
        config.medium_model = args.model
        config.large_model = args.model

    return config


def main():
    """主入口"""
    parser = create_parser()
    args = parser.parse_args()

    # 显示状态
    if args.status:
        print("=" * 50)
        print("硬件状态")
        print("=" * 50)
        GPUMonitor().print_status()
        try:
            CPUMonitor().print_status()
        except ImportError as e:
            print(f"⚠️ {e}")
        return 0

    # 创建配置
    config = load_config(args)

    # 映射策略
    strategy_map = {
        "auto": RoutingStrategy.AUTO,
        "gpu": RoutingStrategy.LOCAL_GPU,
        "cpu": RoutingStrategy.LOCAL_CPU,
        "cloud": RoutingStrategy.CLOUD
    }
    strategy = strategy_map[args.strategy]

    # 初始化路由器
    try:
        router = SmartRouter(config)
    except Exception as e:
        print_error(f"初始化失败: {e}")
        print_tip("运行环境检查: python check_env.py")
        return 1

    # 列出模型
    if args.list_models:
        print("可用模型:")
        for model in router.list_available_models():
            print(f"  - {model}")
        return 0

    # 检查 Ollama 连接（云端策略不需要）
    if strategy != RoutingStrategy.CLOUD and not check_ollama_connection():
        print_ollama_error()
        return 1

    # 交互模式
    if args.interactive or not args.prompt:
        interactive_mode(router)
        return 0

    # 单次查询
    try:
        result = router.route(args.prompt, complexity=args.complexity, strategy=strategy)
        print(result.content)
    except Exception as e:
        print_error(f"运行失败: {e}")

        # 提供针对性建议
        error_msg = str(e).lower()
        if "model" in error_msg and "not found" in error_msg:
            print_tip("模型未找到，请下载模型: ollama pull gemma3:4b")
        elif "connection" in error_msg:
            print_ollama_error()
        elif "gpu" in error_msg or "cuda" in error_msg:
            print_tip("GPU 错误，尝试使用 CPU: python -m src '问题' --strategy cpu")
        else:
            print_tip("运行环境检查: python check_env.py")

        return 1


if __name__ == "__main__":
    main()
