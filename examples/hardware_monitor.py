"""
硬件监控示例 - 监控RTX 5060和U9 275HX

修复内容 (2025-07-10):
1. 添加 try/except 异常处理，包含 GPU 信息获取失败、CPU 监控失败等场景
2. 添加连续失败计数器，GPU 信息持续失败时退出循环避免无限输出空行
3. 使用 __file__ 动态路径计算替代硬编码 '..' 的 sys.path.insert
4. 添加 KeyboardInterrupt 处理，支持优雅退出监控循环
5. 添加导入失败的友好提示和安装指引
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
    from src.gpu_monitor import GPUMonitor, CPUMonitor
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("   请确保项目已安装: pip install -e .")
    print(f"   或从项目根目录运行: python examples/{os.path.basename(__file__)}")
    sys.exit(1)


def monitor_demo():
    """硬件监控演示"""
    print("=" * 60)
    print("硬件监控演示")
    print("适配: U9 275HX + RTX 5060 8GB + 32GB RAM")
    print("=" * 60)
    
    try:
        gpu = GPUMonitor()
        cpu = CPUMonitor()
    except Exception as e:
        print(f"❌ 初始化监控器失败: {type(e).__name__}: {e}")
        print("   请检查 psutil 是否已安装: pip install psutil")
        return
    
    # 显示当前状态
    try:
        print("\n当前状态:")
        print("-" * 60)
        gpu.print_status()
        cpu.print_status()
    except Exception as e:
        print(f"⚠️  打印状态失败: {type(e).__name__}: {e}")
    
    # 检测模型适配性
    try:
        print("\n" + "=" * 60)
        print("模型适配性检测")
        print("=" * 60)
        
        models = [
            ("gemma3:4b", 3.0),
            ("qwen2.5:7b", 6.0),
            ("llama3.2:8b", 7.0),
            ("deepseek-r1:14b", 12.0),
        ]
        
        try:
            free_vram = gpu.get_free_vram_gb()
            if free_vram is not None:
                print(f"\n当前GPU空闲显存: {free_vram:.1f}GB\n")
            else:
                print("\n当前GPU空闲显存: 无法获取\n")
        except Exception as e:
            print(f"\n⚠️  获取显存失败: {type(e).__name__}: {e}\n")
            free_vram = None
        
        for model, vram in models:
            try:
                can_fit = gpu.can_fit_model(vram)
                status = "✅ 可运行" if can_fit else "❌ 显存不足"
                print(f"  {model:20} 需要{vram:4.1f}GB  {status}")
                if can_fit:
                    try:
                        batch = gpu.get_optimal_batch_size(vram)
                        print(f"                         建议batch_size: {batch}")
                    except Exception as e:
                        print(f"                         建议batch_size: 计算失败 ({e})")
            except Exception as e:
                print(f"  {model:20} 检查失败: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"⚠️  模型适配性检测失败: {type(e).__name__}: {e}")
    
    # 实时监控（可选）
    print("\n" + "=" * 60)
    print("实时监控 (按Ctrl+C停止)")
    print("=" * 60)
    
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 5
    
    try:
        while True:
            try:
                gpu_info = gpu.get_gpu_memory()
                cpu_percent = cpu.get_cpu_percent()
                
                if gpu_info:
                    print(f"\rGPU: {gpu_info.utilization_percent:3.0f}% | "
                          f"VRAM: {gpu_info.used_gb:.1f}/{gpu_info.total_gb:.1f}GB | "
                          f"CPU: {cpu_percent:5.1f}%", end="", flush=True)
                    consecutive_failures = 0
                else:
                    print(f"\rGPU: 信息不可用 | CPU: {cpu_percent:5.1f}%", end="", flush=True)
                    consecutive_failures += 1
                
                # 如果连续失败超过阈值，退出循环
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print(f"\n\n⚠️  GPU 信息连续 {MAX_CONSECUTIVE_FAILURES} 次获取失败，停止监控")
                    break
                
                time.sleep(1)
            except Exception as e:
                print(f"\n⚠️  监控循环出错: {type(e).__name__}: {e}")
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print(f"\n⚠️  连续失败 {MAX_CONSECUTIVE_FAILURES} 次，停止监控")
                    break
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n监控已停止")


if __name__ == "__main__":
    try:
        monitor_demo()
    except KeyboardInterrupt:
        print("\n\n监控已停止")
    except Exception as e:
        print(f"\n❌ 监控演示失败: {type(e).__name__}: {e}")
