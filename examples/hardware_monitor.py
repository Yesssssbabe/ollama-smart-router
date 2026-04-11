"""
硬件监控示例 - 监控RTX 5060和U9 275HX
"""

import sys
import time
sys.path.insert(0, '..')

from src.gpu_monitor import GPUMonitor, CPUMonitor

def monitor_demo():
    """硬件监控演示"""
    print("=" * 60)
    print("硬件监控演示")
    print("适配: U9 275HX + RTX 5060 8GB + 32GB RAM")
    print("=" * 60)
    
    gpu = GPUMonitor()
    cpu = CPUMonitor()
    
    print("\n当前状态:")
    print("-" * 60)
    gpu.print_status()
    cpu.print_status()
    
    # 检测模型适配性
    print("\n" + "=" * 60)
    print("模型适配性检测")
    print("=" * 60)
    
    models = [
        ("gemma3:4b", 3.0),
        ("qwen2.5:7b", 6.0),
        ("llama3.2:8b", 7.0),
        ("deepseek-r1:14b", 12.0),
    ]
    
    print(f"\n当前GPU空闲显存: {gpu.get_free_vram_gb():.1f}GB\n")
    
    for model, vram in models:
        can_fit = gpu.can_fit_model(vram)
        status = "✅ 可运行" if can_fit else "❌ 显存不足"
        print(f"  {model:20} 需要{vram:4.1f}GB  {status}")
        if can_fit:
            batch = gpu.get_optimal_batch_size(vram)
            print(f"                         建议batch_size: {batch}")
    
    # 实时监控（可选）
    print("\n" + "=" * 60)
    print("实时监控 (按Ctrl+C停止)")
    print("=" * 60)
    
    try:
        while True:
            gpu_info = gpu.get_gpu_memory()
            cpu_percent = cpu.get_cpu_percent()
            
            if gpu_info:
                print(f"\rGPU: {gpu_info.utilization_percent:3.0f}% | "
                      f"VRAM: {gpu_info.used_gb:.1f}/{gpu_info.total_gb:.1f}GB | "
                      f"CPU: {cpu_percent:5.1f}%", end="", flush=True)
            
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n监控已停止")


if __name__ == "__main__":
    monitor_demo()
