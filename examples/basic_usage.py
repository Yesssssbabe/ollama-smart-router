"""
基础用法示例
"""

import sys
sys.path.insert(0, '..')

from src.router import SmartRouter, RouterConfig

# 1. 基础用法 - 自动路由
print("=" * 50)
print("示例1: 自动路由")
print("=" * 50)

router = SmartRouter()

# 简单任务 - 应该路由到GPU小模型
result = router.route("你好，请介绍一下自己")
print(f"\n回复 ({result.source}):\n{result.content[:200]}...")

# 代码任务 - 应该路由到CPU中模型  
result = router.route("写个Python快速排序算法")
print(f"\n回复 ({result.source}):\n{result.content[:200]}...")

# 2. 手动指定复杂度
print("\n" + "=" * 50)
print("示例2: 手动指定复杂度")
print("=" * 50)

result = router.route("解释什么是机器学习", complexity="simple")
print(f"强制简单模式 ({result.source}): {result.content[:100]}...")

# 3. 强制使用特定策略
print("\n" + "=" * 50)
print("示例3: 强制策略")
print("=" * 50)

from src.router import RoutingStrategy

# 强制CPU
result = router.route("1+1等于几？", strategy=RoutingStrategy.LOCAL_CPU)
print(f"强制CPU ({result.source}): {result.content[:100]}...")

# 4. 查看统计
print("\n" + "=" * 50)
print("使用统计")
print("=" * 50)
router.print_stats()
