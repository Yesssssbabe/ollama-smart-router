"""
基础用法示例

修复内容 (2025-07-10):
1. 使用 __file__ 动态计算项目根路径，替代硬编码 '..' 的 sys.path.insert 反模式
2. 添加详细的 try/except 异常处理，提供友好错误提示
3. 保留 sys.path.insert 作为兼容性回退，但添加注释说明推荐方式
"""

import sys
import os

# 推荐方式：先通过 pip install -e . 安装为可编辑包，然后直接 import
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


def main():
    try:
        # 1. 基础用法 - 自动路由
        print("=" * 50)
        print("示例1: 自动路由")
        print("=" * 50)
        
        router = SmartRouter()
        
        # 简单任务 - 应该路由到GPU小模型
        try:
            result = router.route("你好，请介绍一下自己")
            print(f"\n回复 ({result.source}):\n{result.content[:200]}...")
        except Exception as e:
            print(f"   ⚠️  路由失败: {type(e).__name__}: {e}")
        
        # 代码任务 - 应该路由到CPU中模型
        try:
            result = router.route("写个Python快速排序算法")
            print(f"\n回复 ({result.source}):\n{result.content[:200]}...")
        except Exception as e:
            print(f"   ⚠️  路由失败: {type(e).__name__}: {e}")
        
        # 2. 手动指定复杂度
        print("\n" + "=" * 50)
        print("示例2: 手动指定复杂度")
        print("=" * 50)
        
        try:
            result = router.route("解释什么是机器学习", complexity="simple")
            print(f"强制简单模式 ({result.source}): {result.content[:100]}...")
        except Exception as e:
            print(f"   ⚠️  路由失败: {type(e).__name__}: {e}")
        
        # 3. 强制使用特定策略
        print("\n" + "=" * 50)
        print("示例3: 强制策略")
        print("=" * 50)
        
        # 强制CPU
        try:
            result = router.route("1+1等于几？", strategy=RoutingStrategy.LOCAL_CPU)
            print(f"强制CPU ({result.source}): {result.content[:100]}...")
        except Exception as e:
            print(f"   ⚠️  路由失败: {type(e).__name__}: {e}")
        
        # 4. 查看统计
        print("\n" + "=" * 50)
        print("使用统计")
        print("=" * 50)
        try:
            router.print_stats()
        except Exception as e:
            print(f"   ⚠️  打印统计失败: {type(e).__name__}: {e}")
    
    except KeyboardInterrupt:
        print("\n\n  ⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 示例运行失败: {type(e).__name__}: {e}")
        print("   请检查:")
        print("     1. Ollama 是否已安装并运行")
        print("     2. 依赖包是否已安装: pip install -r requirements.txt")
        print("     3. 模型是否已下载: ollama pull gemma3:4b")


if __name__ == "__main__":
    main()
