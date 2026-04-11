"""
Ollama Smart Router - 智能模型调度器
自动检测任务复杂度，智能分配本地GPU/CPU或云端API
"""

from .router import SmartRouter
from .complexity_analyzer import ComplexityAnalyzer
from .gpu_monitor import GPUMonitor

__version__ = "0.1.0"
__all__ = ["SmartRouter", "ComplexityAnalyzer", "GPUMonitor"]
