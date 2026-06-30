"""
Ollama Smart Router - 智能模型调度器
自动检测任务复杂度，智能分配本地GPU/CPU或云端API

修复内容 (2025-07-10):
1. 添加 logging 初始化代码，配置日志级别和格式
2. 补全 __all__ 导出列表，确保所有公共 API 可见
"""

import logging
import sys

# 初始化日志系统
# 如果 stdout 编码不是 UTF-8，尝试重新配置（Windows 兼容性）
if sys.platform == "win32" and sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass

# H-12: 仅在根日志记录器尚未配置时初始化，避免污染用户已有的日志配置
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)],
        force=False  # 不强制覆盖已有配置，尊重用户预配置
    )

# 获取模块日志记录器
logger = logging.getLogger(__name__)
logger.debug("src 包初始化完成，日志系统已配置")

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
    # 日志模块暴露，方便下游调用者配置
    "logger",
]
