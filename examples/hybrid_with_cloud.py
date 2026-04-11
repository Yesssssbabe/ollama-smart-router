"""
混合推理示例 - 本地 + 云端API
"""

import sys
import os
sys.path.insert(0, '..')

from src.router import SmartRouter, RouterConfig

# 配置云端API
config = RouterConfig(
    cloud_api_key=os.getenv("DEEPSEEK_API_KEY", "your-api-key-here"),
    cloud_base_url="https://api.deepseek.com",
    cloud_model="deepseek-chat"
)

router = SmartRouter(config)

print("=" * 50)
print("混合推理示例")
print("=" * 50)

tasks = [
    ("simple", "翻译: Hello World"),
    ("medium", "分析这段Python代码的时间复杂度: def foo(n): return n*n"),
    ("complex", "设计一个支持百万并发的分布式系统架构"),
]

for complexity, prompt in tasks:
    print(f"\n任务: {prompt[:50]}...")
    print(f"复杂度: {complexity}")
    
    result = router.route(prompt, complexity=complexity)
    print(f"路由到: {result.source}")
    print(f"耗时: {result.latency:.2f}s")
    print(f"回复: {result.content[:150]}...")
    print("-" * 50)

print("\n统计信息:")
router.print_stats()
