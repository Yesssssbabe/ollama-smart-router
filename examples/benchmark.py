"""
性能基准测试
对比不同路由策略的性能
"""

import sys
import time
sys.path.insert(0, '..')

from src.router import SmartRouter, RouterConfig, RoutingStrategy


def benchmark_task(router, prompt: str, strategy: RoutingStrategy, name: str):
    """测试单个任务"""
    print(f"\n测试: {name}")
    print(f"提示: {prompt[:50]}...")
    
    times = []
    for i in range(3):  # 运行3次取平均
        start = time.time()
        result = router.route(prompt, strategy=strategy)
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"  运行{i+1}: {elapsed:.2f}s ({result.source})")
    
    avg_time = sum(times) / len(times)
    print(f"  平均耗时: {avg_time:.2f}s")
    return avg_time


def main():
    print("=" * 60)
    print("性能基准测试")
    print("=" * 60)
    
    router = SmartRouter()
    
    test_cases = [
        ("你好，请自我介绍", "simple"),
        ("写个Python斐波那契函数", "code"),
        ("分析快速排序的时间复杂度", "analysis"),
    ]
    
    results = {}
    
    for prompt, category in test_cases:
        print(f"\n{'='*60}")
        print(f"测试类别: {category}")
        print(f"{'='*60}")
        
        # 测试不同策略
        strategies = [
            (RoutingStrategy.AUTO, "自动路由"),
            (RoutingStrategy.LOCAL_GPU, "GPU强制"),
            (RoutingStrategy.LOCAL_CPU, "CPU强制"),
        ]
        
        for strategy, name in strategies:
            key = f"{category}_{name}"
            try:
                avg = benchmark_task(router, prompt, strategy, name)
                results[key] = avg
            except Exception as e:
                print(f"  错误: {e}")
                results[key] = None
    
    # 汇总
    print(f"\n{'='*60}")
    print("测试结果汇总")
    print(f"{'='*60}")
    for key, value in results.items():
        if value:
            print(f"{key:30}: {value:.2f}s")
        else:
            print(f"{key:30}: 失败")


if __name__ == "__main__":
    main()
