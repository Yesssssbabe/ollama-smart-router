"""
命令行交互界面

修复内容:
- HIGH-1: 移除 --cloud-key 参数，防止API密钥泄露到shell history
- HIGH-1: 交互模式添加 /setkey 命令，使用 getpass 安全输入
- HIGH-14: 显式传入 --config 但文件不存在时，报错并退出，不再静默回退
- MEDIUM-1: 添加 --config 路径验证，防止路径遍历攻击
- MEDIUM-2: 交互模式添加输入长度限制（10万字符）
- H8: 空字符串参数使用 is not None and .strip() 双重检查
- L4: 在 load_config 函数顶部添加配置优先级注释
- 交互模式细化异常处理，区分 KeyboardInterrupt/EOFError/SystemExit
"""

import argparse
import dataclasses
import getpass
import logging
import os
import sys
from pathlib import Path
from typing import Optional

try:
    import readline
    readline.parse_and_bind("tab: complete")
except Exception:
    readline = None  # Windows 等环境可能缺少 readline

from .router import SmartRouter, RouterConfig, RoutingStrategy, VALID_MODEL
from .gpu_monitor import GPUMonitor, CPUMonitor
from .config_loader import config_from_yaml, merge_env_vars

logger = logging.getLogger(__name__)

MAX_PROMPT_LENGTH = 200000  # 交互模式最大输入长度（与路由限制对齐，约200KB）


def _production_error_message(detail: str) -> str:
    """H-13: 生产环境返回泛化错误消息，DEBUG 模式保留详细信息。

    Args:
        detail: 详细错误信息（仅在 DEBUG 模式展示）。

    Returns:
        str: 对外展示的错误消息。
    """
    if os.environ.get("DEBUG"):
        return detail
    return "请求处理失败，请稍后重试或联系管理员"


def validate_config_path(path: str) -> str:
    """验证配置文件路径，防止路径遍历、Tilde 展开绕过和符号链接攻击"""
    # H-5: 先展开 ~，再解析真实路径，避免 ~/secret.yaml 绕过检查
    expanded = Path(os.path.expanduser(path))
    real_path = expanded.resolve()
    real_cwd = Path(os.getcwd()).resolve()
    real_home = Path(os.path.expanduser("~")).resolve()
    # 允许当前工作目录下的文件，或用户主目录下的配置文件
    if not (
        real_path.is_relative_to(real_cwd)
        or real_path.is_relative_to(real_home)
    ):
        raise argparse.ArgumentTypeError(
            f"配置文件路径必须在当前工作目录或用户主目录下: {path}"
        )
    return path


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

    # HIGH-1: --cloud-key 已移除，强制使用 DEEPSEEK_API_KEY 环境变量
    # 交互模式可使用 /setkey 命令通过 getpass 安全输入

    parser.add_argument(
        "--config",
        default=None,
        type=validate_config_path,
        help="配置文件路径 (默认: 搜索当前目录 config.yaml 及 ~/.config/)"
    )

    return parser


def interactive_mode(router: SmartRouter):
    """交互模式"""
    print("=" * 50)
    print("🤖 Ollama Smart Router - 交互模式")
    print("=" * 50)
    print("命令: /quit (退出), /status (状态), /stats (统计), /setkey (设置API密钥), /help (帮助)")
    print("-" * 50)

    try:
        while True:
            try:
                prompt = input("\n你: ").strip()
            except EOFError:
                print("\n再见!")
                break

            if not prompt:
                continue

            if prompt == "/quit":
                print("再见!")
                break
            elif prompt == "/status":
                router.gpu_monitor.print_status()
                try:
                    router.cpu_monitor.print_status()
                except Exception as e:
                    print(f"⚠️ CPU状态获取失败: {e}")
                continue
            elif prompt == "/stats":
                router.print_stats()
                continue
            elif prompt == "/setkey":
                # HIGH-1: 使用 getpass 安全输入，避免密钥泄露到屏幕和 history
                try:
                    key = getpass.getpass("请输入 API 密钥 (输入不显示): ")
                    if key.strip():
                        # C-4/H-2: RouterConfig 为 frozen，使用 dataclasses.replace 更新
                        router.config = dataclasses.replace(
                            router.config, cloud_api_key=key.strip()
                        )
                        # 重置云端客户端，下次使用时重新初始化
                        router._cloud_client = None
                        print("✅ API 密钥已设置")
                    else:
                        print("⚠️ 输入为空，未设置密钥")
                except EOFError:
                    print("⚠️ 无法读取输入")
                continue
            elif prompt == "/help":
                print("可用命令:")
                print("  /quit    - 退出交互模式")
                print("  /status  - 显示硬件状态")
                print("  /stats   - 显示使用统计")
                print("  /setkey  - 安全设置云端 API 密钥 (通过环境变量 DEEPSEEK_API_KEY 更推荐)")
                print("  /help    - 显示此帮助")
                continue
            elif prompt.startswith("/"):
                print(f"未知命令: {prompt}，输入 /help 查看可用命令")
                continue

            # MEDIUM-2: 输入长度限制
            if len(prompt) > MAX_PROMPT_LENGTH:
                print(f"❌ 输入过长，最大支持 {MAX_PROMPT_LENGTH} 字符")
                continue

            print()
            result = router.route(prompt)
            print(f"\n🤖 ({result.source}): {result.content}")

    except KeyboardInterrupt:
        print("\n再见!")
    except (SystemExit, GeneratorExit):
        # 系统退出异常应继续向上传播，不得吞没
        raise
    except Exception as e:
        # H-13: 生产环境隐藏详细异常，仅记录日志
        logger.exception("交互模式发生未预期错误")
        print(f"❌ 错误: {_production_error_message(str(e))}")
    finally:
        router.close()


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
    if sys.platform == "darwin":
        print("  2. Ollama 未运行（菜单栏没有羊驼图标）")
    elif sys.platform == "win32":
        print("  2. Ollama 未运行（系统托盘图标）")
    else:
        print("  2. Ollama 未运行")
    print("\n解决方法：")
    print("  • 下载安装: https://ollama.com")
    if sys.platform == "darwin":
        print("  • 启动 Ollama 应用")
    elif sys.platform == "win32":
        print("  • 启动 Ollama 应用")
    else:
        print("  • 启动 Ollama 服务: systemctl start ollama")
    print("  • 命令行测试: ollama list")


def load_config(args) -> RouterConfig:
    """
    根据命令行参数加载配置

    配置优先级（从高到低）:
    1. 命令行参数 (args)
    2. 环境变量 (os.environ)
    3. YAML 配置文件
    """
    # HIGH-14: 如果用户显式传入 --config，但文件不存在，必须报错并退出
    # 不静默回退到默认搜索路径
    if args.config is not None:
        if not os.path.exists(args.config):
            print_error(f"指定的配置文件不存在: {args.config}")
            sys.exit(1)
        config_path = args.config
    else:
        # 未显式传入 --config，使用默认搜索路径
        config_path = None

    config = config_from_yaml(config_path)

    # 环境变量覆盖
    config = merge_env_vars(config)

    # H8: 命令行参数覆盖，使用 is not None and .strip() 双重检查
    # 确保空字符串和纯空格字符串不会覆盖有效配置
    if args.model is not None and args.model.strip():
        model = args.model.strip()
        if not VALID_MODEL.match(model):
            raise ValueError(f"[ERR_INPUT_INVALID] 模型名格式不合法: {model}")
        # C-4/H-2: RouterConfig 为 frozen，使用 dataclasses.replace 更新
        config = dataclasses.replace(
            config, small_model=model, medium_model=model, large_model=model
        )

    return config


def main() -> int:
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
    try:
        config = load_config(args)
    except SystemExit:
        raise
    except Exception as e:
        print_error(f"配置加载失败: {e}")
        return 1

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

    try:
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
            # H-13: 生产环境隐藏详细异常，DEBUG 模式保留完整信息用于排障
            logger.exception("单次查询运行失败")
            display_msg = _production_error_message(str(e))
            print_error(f"运行失败: {display_msg}")

            # 提供针对性建议（基于错误类型而非原始消息，避免泄露敏感信息）
            error_type = type(e).__name__.lower()
            error_msg = str(e).lower()
            if "model" in error_msg and "not found" in error_msg:
                print_tip("模型未找到，请下载模型: ollama pull gemma3:4b")
            elif "connection" in error_type or "connection" in error_msg:
                print_ollama_error()
            elif "gpu" in error_msg or "cuda" in error_msg:
                print_tip("GPU 错误，尝试使用 CPU: python -m src '问题' --strategy cpu")
            else:
                print_tip("运行环境检查: python check_env.py")

            return 1

        return 0
    finally:
        router.close()


if __name__ == "__main__":
    sys.exit(main())