"""
混合推理示例 - 本地 + 云端API

修复内容 (2025-07-10):
1. 删除 os.getenv 的默认值，未设置环境变量时抛出 ValueError 并提示
2. 添加 try/except 异常处理，包含 Ollama 未运行、模型缺失、API 认证失败等场景
3. 使用 __file__ 动态路径计算替代硬编码 '..' 的 sys.path.insert
4. 添加 KeyboardInterrupt 处理，支持优雅退出
"""

import sys
import os

# 推荐方式：先通过 pip install -e . 安装为可编辑包
# 以下代码用于从 examples/ 目录直接运行示例时的兼容性处理
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_script_dir, '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from src.router import SmartRouter, RouterConfig
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("   请确保项目已安装: pip install -e .")
    print(f"   或从项目根目录运行: python examples/{os.path.basename(__file__)}")
    sys.exit(1)


def main():
    try:
        # 从环境变量获取 API 密钥，不再提供默认假值
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError(
                "请设置环境变量 DEEPSEEK_API_KEY\n"
                "   例如: export DEEPSEEK_API_KEY='your-api-key'\n"
                "   请勿将真实密钥硬编码到代码中！"
            )
        
        # 配置云端API
        config = RouterConfig(
            cloud_api_key=api_key,
            cloud_base_url="https://api.deepseek.com",
            cloud_model="deepseek-chat"
        )
        
        try:
            router = SmartRouter(config)
        except Exception as e:
            print(f"❌ 初始化路由器失败: {type(e).__name__}: {e}")
            print("   请检查 Ollama 是否已安装并运行")
            sys.exit(1)
        
        print("=" * 50)
        print("混合推理示例")
        print("=" * 50)
        
        tasks = [
            ("simple", "翻译: Hello World"),
            ("medium", "分析这段Python代码的时间复杂度: def foo(n): return n*n"),
            ("complex", "设计一个支持百万并发的分布式系统架构"),
        ]
        
        for complexity, prompt in tasks:
            try:
                print(f"\n任务: {prompt[:50]}...")
                print(f"复杂度: {complexity}")
                
                result = router.route(prompt, complexity=complexity)
                print(f"路由到: {result.source}")
                print(f"耗时: {result.latency:.2f}s")
                print(f"回复: {result.content[:150]}...")
                print("-" * 50)
            except Exception as e:
                print(f"   ⚠️  任务失败: {type(e).__name__}: {e}")
                print("-" * 50)
        
        # 查看统计
        try:
            print("\n统计信息:")
            router.print_stats()
        except Exception as e:
            print(f"   ⚠️  打印统计失败: {type(e).__name__}: {e}")
    
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n  ⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 示例运行失败: {type(e).__name__}: {e}")
        print("   请检查:")
        print("     1. Ollama 是否已安装并运行")
        print("     2. DEEPSEEK_API_KEY 环境变量是否已正确设置")
        print("     3. 网络连接是否正常")


if __name__ == "__main__":
    main()
