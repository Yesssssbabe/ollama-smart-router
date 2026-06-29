"""
Ollama Smart Router - 智能模型调度器
自动检测任务复杂度，智能分配本地GPU/CPU或云端API
"""

from .router import SmartRouter, RouterConfig, RoutingStrategy, InferenceResult
from .complexity_analyzer import ComplexityAnalyzer, TaskComplexity, TaskAnalysis
from .gpu_monitor import GPUMonitor, CPUMonitor
from .config_loader import config_from_yaml, merge_env_vars

__version__ = "0.1.0"
__all__ = [
    "SmartRouter",
    "RouterConfig",
    "RoutingStrategy",
    "InferenceResult",
    "ComplexityAnalyzer",
    "TaskComplexity",
    "TaskAnalysis",
    "GPUMonitor",
    "CPUMonitor",
    "config_from_yaml",
    "merge_env_vars",
]
