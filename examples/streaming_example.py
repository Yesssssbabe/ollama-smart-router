"""
流式输出示例

修复内容 (2025-07-10):
1. 使用 .get() 链式安全访问 Ollama 流式响应 chunk，避免 KeyError
2. 添加 try/except 异常处理，包含流中断、模型缺失等场景
3. 使用 __file__ 动态路径计算替代硬编码 '..' 的 sys.path.insert
4. 添加 ollama 包导入失败的友好提示
5. 添加 KeyboardInterrupt 处理，流输出可优雅中断
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
    import ollama
except ImportError:
    print("❌ 未安装 ollama 包")
    print("   请运行: pip install ollama")
    sys.exit(1)


def stream_local():
    """本地模型流式输出"""
    print("=" * 50)
    print("本地模型流式输出 (gemma3:4b)")
    print("=" * 50)
    
    prompt = "用100字介绍Python"
    print(f"提示: {prompt}\n")
    
    try:
        stream = ollama.chat(
            model="gemma3:4b",
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )
        
        print("回复: ", end="", flush=True)
        for chunk in stream:
            # 使用 .get() 安全访问，避免 KeyError
            message = chunk.get('message') or {}
            content = message.get('content', '') if isinstance(message, dict) else ''
            if content:
                print(content, end="", flush=True)
        print("\n")
    except KeyboardInterrupt:
        print("\n\n  ⚠️  流输出被用户中断")
    except Exception as e:
        print(f"\n❌ 流式输出失败: {type(e).__name__}: {e}")
        print("   请检查:")
        print("     1. Ollama 是否已安装并运行")
        print("     2. gemma3:4b 模型是否已下载: ollama pull gemma3:4b")


def stream_with_router():
    """结合路由器的流式输出"""
    try:
        from src.router import SmartRouter
        from src.complexity_analyzer import ComplexityAnalyzer
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("   请确保项目已安装: pip install -e .")
        return
    
    try:
        router = SmartRouter()
        analyzer = ComplexityAnalyzer()
        
        prompt = "写一首关于AI的短诗"
        analysis = analyzer.analyze(prompt)
        
        print("=" * 50)
        print("智能路由 + 流式输出")
        print("=" * 50)
        print(f"任务分析: {analysis.complexity.value}")
        
        # 根据复杂度选择模型
        if analysis.complexity.value == "simple":
            model = "gemma3:4b"
        else:
            model = "qwen2.5:7b"
        
        print(f"选择模型: {model}\n")
        
        stream = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )
        
        print("回复: ", end="", flush=True)
        for chunk in stream:
            # 使用 .get() 安全访问，避免 KeyError
            message = chunk.get('message') or {}
            content = message.get('content', '') if isinstance(message, dict) else ''
            if content:
                print(content, end="", flush=True)
        print("\n")
    except KeyboardInterrupt:
        print("\n\n  ⚠️  流输出被用户中断")
    except Exception as e:
        print(f"\n❌ 流式输出失败: {type(e).__name__}: {e}")
        print("   请检查 Ollama 是否已安装并运行")


def main():
    try:
        stream_local()
        print("\n")
        stream_with_router()
    except KeyboardInterrupt:
        print("\n\n  ⚠️  示例被用户中断")


if __name__ == "__main__":
    main()
