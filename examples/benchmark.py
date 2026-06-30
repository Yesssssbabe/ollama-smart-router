"""
性能基准测试
对比不同路由策略的性能

修复内容 (2025-07-10):
1. 添加详细的 try/except 异常处理，保护每个 benchmark 任务
2. 添加内层异常保护，防止单个失败影响后续测试
3. 保留基于 __file__ 的路径计算，替代硬编码 '..' 的 sys.path.insert
4. 添加 KeyboardInterrupt 处理，支持优雅退出
"""

import sys
import os
import time

# 推荐方式：先通过 pip install -e . 安装为可编辑包
# 以下代码用于从 examples/ 目录直接运行示例时的兼容性处理
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_script_dir, '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

try:
    from src.router import SmartRouter, RouterConfig, RoutingStrategy
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("   请确保项目已安装: pip install -e .")
    print(f"   或从项目根目录运行: python examples/{os.path.basename(__file__)}")
    sys.exit(1)


def benchmark_task(router, prompt: str, strategy: RoutingStrategy, name: str):
    """测试单个任务，添加异常保护"""
    print(f"\n测试: {name}")
    print(f"提示: {prompt[:50]}...")
    
    times = []
    for i in range(3):  # 运行3次取平均
        try:
            start = time.time()
            result = router.route(prompt, strategy=strategy)
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  运行{i+1}: {elapsed:.2f}s ({result.source})")
        except Exception as e:
            print(f"  运行{i+1}: 失败 ({type(e).__name__}: {e})")
            continue
    
    if times:
        avg_time = sum(times) / len(times)
        print(f"  平均耗时: {avg_time:.2f}s")
        return avg_time
    else:
        print(f"  所有运行均失败")
        return None


def main():
    try:
        print("=" * 60)
        print("性能基准测试")
        print("=" * 60)
        
        try:
            router = SmartRouter()
        except Exception as e:
            print(f"❌ 初始化路由器失败: {type(e).__name__}: {e}")
            print("   请检查 Ollama 是否已安装并运行")
            sys.exit(1)
        
        try:
            test_cases = [
                ("你好，请自我介绍", "simple"),
                ("写个Python斐波那契函数", "code"),
                ("分析快速排序的时间复杂度", "analysis"),
            ]
            
            results = {}
            
            for prompt, category in test_cases:
                try:
                    print(f"\n{'='*60}")
                    print(f"测试类别: {category}")
                    print(f"{'='*60}")
                    
                    # 测试不同策略
                    strategies = [
                        (RoutingStrategy.AUTO, "自动路由"),
                        (RoutingStrategy.LOCAL_GPU, "GPU强制"),
                        (RoutingStrategy.LOCAL_CPU, "CPU强制"),
                    ]
                    
                    for strategy, strategy_name in strategies:
                        key = f"{category}_{strategy_name}"
                        try:
                            avg = benchmark_task(router, prompt, strategy, strategy_name)
                            results[key] = avg
                        except Exception as e:
                            print(f"  错误: {type(e).__name__}: {e}")
                            results[key] = None
                except Exception as e:
                    print(f"⚠️  测试类别 '{category}' 失败: {type(e).__name__}: {e}")
                    continue
            
            # 汇总
            print(f"\n{'='*60}")
            print("测试结果汇总")
            print(f"{'='*60}")
            for key, value in results.items():
                if value is not None:
                    print(f"{key:30}: {value:.2f}s")
                else:
                    print(f"{key:30}: 失败")
        finally:
            router.close()
    
    except KeyboardInterrupt:
        print("\n\n  ⚠️  基准测试被用户中断")
    except Exception as e:
        print(f"\n❌ 基准测试失败: {type(e).__name__}: {e}")
        print("   请检查:")
        print("     1. Ollama 是否已安装并运行")
        print("     2. 依赖包是否已安装: pip install -r requirements.txt")


if __name__ == "__main__":
    main()
