"""
命令行交互界面
"""

import argparse
import sys
from typing import Optional

from .router import SmartRouter, RouterConfig, RoutingStrategy
from .gpu_monitor import GPUMonitor, CPUMonitor


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
        help="指定模型 (覆盖自动选择)"
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


def main():
    """主入口"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 创建配置
    config = RouterConfig()
    if args.cloud_key:
        config.cloud_api_key = args.cloud_key
    elif "DEEPSEEK_API_KEY" in __import__('os').environ:
        config.cloud_api_key = __import__('os').environ["DEEPSEEK_API_KEY"]
    
    # 映射策略
    strategy_map = {
        "auto": RoutingStrategy.AUTO,
        "gpu": RoutingStrategy.LOCAL_GPU,
        "cpu": RoutingStrategy.LOCAL_CPU,
        "cloud": RoutingStrategy.CLOUD
    }
    strategy = strategy_map[args.strategy]
    
    # 显示状态
    if args.status:
        print("=" * 50)
        print("硬件状态")
        print("=" * 50)
        GPUMonitor().print_status()
        CPUMonitor().print_status()
        return
    
    # 初始化路由器
    router = SmartRouter(config)
    
    # 列出模型
    if args.list_models:
        print("可用模型:")
        for model in router.list_available_models():
            print(f"  - {model}")
        return
    
    # 交互模式
    if args.interactive or not args.prompt:
        interactive_mode(router)
        return
    
    # 单次查询
    result = router.route(args.prompt, complexity=args.complexity, strategy=strategy)
    print(result.content)


if __name__ == "__main__":
    main()
