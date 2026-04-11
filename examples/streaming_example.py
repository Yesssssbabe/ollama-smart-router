"""
流式输出示例
"""

import sys
sys.path.insert(0, '..')

import ollama

def stream_local():
    """本地模型流式输出"""
    print("=" * 50)
    print("本地模型流式输出 (gemma3:4b)")
    print("=" * 50)
    
    prompt = "用100字介绍Python"
    print(f"提示: {prompt}\n")
    
    stream = ollama.chat(
        model="gemma3:4b",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    
    print("回复: ", end="", flush=True)
    for chunk in stream:
        content = chunk['message']['content']
        print(content, end="", flush=True)
    print("\n")


def stream_with_router():
    """结合路由器的流式输出"""
    from src.router import SmartRouter
    from src.complexity_analyzer import ComplexityAnalyzer
    
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
        content = chunk['message']['content']
        print(content, end="", flush=True)
    print("\n")


if __name__ == "__main__":
    stream_local()
    print("\n")
    stream_with_router()
