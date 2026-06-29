"""
GPU监控模块 - 实时监控RTX 5060显存使用情况
"""

import re
import shutil
import subprocess
from typing import Optional, Dict
from dataclasses import dataclass

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class GPUMemoryInfo:
    """GPU内存信息"""
    total_gb: float
    used_gb: float
    free_gb: float
    utilization_percent: float


class GPUMonitor:
    """GPU监控器 - 专门适配NVIDIA RTX系列"""

    def __init__(self):
        self.has_nvidia_smi = self._check_nvidia_smi()

    def _check_nvidia_smi(self) -> bool:
        """检查nvidia-smi是否可用"""
        return shutil.which("nvidia-smi") is not None

    def get_gpu_memory(self) -> Optional[GPUMemoryInfo]:
        """
        获取GPU显存信息
        适用于RTX 5060 8GB及同类显卡
        """
        if not self.has_nvidia_smi:
            return None

        try:
            # 获取显存信息
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.total,memory.used,memory.free,utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, check=True
            )

            values = [v.strip() for v in result.stdout.strip().split(',')]
            if len(values) >= 4:
                return GPUMemoryInfo(
                    total_gb=float(values[0]) / 1024,
                    used_gb=float(values[1]) / 1024,
                    free_gb=float(values[2]) / 1024,
                    utilization_percent=float(values[3])
                )
        except Exception as e:
            print(f"[警告] 获取GPU信息失败: {e}")

        return None

    def get_free_vram_gb(self) -> float:
        """获取空闲显存（GB）"""
        info = self.get_gpu_memory()
        return info.free_gb if info else 0

    def can_fit_model(self, model_vram_gb: float, safety_margin: float = 1.0) -> bool:
        """
        判断是否能容纳指定大小的模型

        Args:
            model_vram_gb: 模型需要的显存(GB)
            safety_margin: 安全余量(GB)，默认1GB
        """
        free = self.get_free_vram_gb()
        return free >= (model_vram_gb + safety_margin)

    def get_optimal_batch_size(self, model_vram_gb: float) -> int:
        """
        根据剩余显存计算最佳batch size
        简单启发式：剩余每2GB显存增加1个batch
        """
        free = self.get_free_vram_gb()
        remaining = max(0, free - model_vram_gb - 1)  # 保留1GB余量
        return max(1, int(remaining / 2) + 1)

    def print_status(self):
        """打印GPU状态"""
        info = self.get_gpu_memory()
        if info:
            print(f"🎮 GPU状态: {info.used_gb:.1f}/{info.total_gb:.1f} GB "
                  f"({info.utilization_percent:.0f}% 利用率)")
        else:
            print("⚠️ 无法获取GPU信息")


class CPUMonitor:
    """CPU监控器 - 适配U9 275HX 24核处理器"""

    def __init__(self):
        if not HAS_PSUTIL:
            raise ImportError("需要安装 psutil 才能监控CPU: pip install psutil")
        self.cpu_count = psutil.cpu_count(logical=True)
        self.physical_cores = psutil.cpu_count(logical=False)

    def get_cpu_percent(self) -> float:
        """获取CPU使用率"""
        return psutil.cpu_percent(interval=0.1)

    def get_memory_info(self) -> Dict[str, float]:
        """获取系统内存信息"""
        mem = psutil.virtual_memory()
        return {
            "total_gb": mem.total / (1024**3),
            "available_gb": mem.available / (1024**3),
            "percent_used": mem.percent
        }

    def print_status(self):
        """打印CPU状态"""
        mem = self.get_memory_info()
        print(f"💻 CPU: {self.physical_cores}核/{self.cpu_count}线程 | "
              f"内存: {mem['available_gb']:.1f}/{mem['total_gb']:.1f} GB 可用")
