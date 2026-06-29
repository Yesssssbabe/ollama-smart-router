"""
配置加载模块
支持从 YAML 配置文件和环境变量加载配置
"""

import os
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

from .router import RouterConfig


DEFAULT_CONFIG_PATHS = [
    "config.yaml",
    "config.yml",
    "~/.config/ollama-smart-router/config.yaml",
]


def load_yaml_config(path: Optional[str] = None) -> Optional[dict]:
    """加载 YAML 配置文件"""
    if yaml is None:
        raise ImportError("需要安装 pyyaml 才能读取 YAML 配置: pip install pyyaml")

    candidates = []
    if path:
        candidates.append(Path(path).expanduser())
    else:
        for default in DEFAULT_CONFIG_PATHS:
            candidates.append(Path(default).expanduser())

    for candidate in candidates:
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}

    return None


def config_from_yaml(path: Optional[str] = None, base_config: Optional[RouterConfig] = None) -> RouterConfig:
    """从 YAML 文件创建 RouterConfig"""
    config = base_config or RouterConfig()

    data = load_yaml_config(path)
    if data is None:
        return config

    # 模型配置
    models = data.get("models", {})
    if "small" in models:
        config.small_model = models["small"].get("name", config.small_model)
        config.small_model_vram = float(models["small"].get("vram_gb", config.small_model_vram))
    if "medium" in models:
        config.medium_model = models["medium"].get("name", config.medium_model)
        config.medium_model_vram = float(models["medium"].get("vram_gb", config.medium_model_vram))
    if "large" in models:
        config.large_model = models["large"].get("name", config.large_model)
        config.large_model_vram = float(models["large"].get("vram_gb", config.large_model_vram))

    # GPU 阈值
    thresholds = data.get("gpu_thresholds", {})
    config.gpu_vram_threshold = float(thresholds.get("min_free_vram_gb", config.gpu_vram_threshold))
    # safety_margin 未在 RouterConfig 中定义，可作为内部使用

    # 云端配置
    cloud = data.get("cloud", {})
    config.cloud_base_url = cloud.get("base_url", config.cloud_base_url)
    config.cloud_model = cloud.get("model", config.cloud_model)
    # API key 优先从环境变量读取
    config.cloud_api_key = os.environ.get("DEEPSEEK_API_KEY") or cloud.get("api_key") or config.cloud_api_key

    # 性能配置
    performance = data.get("performance", {})
    config.num_ctx = int(performance.get("num_ctx", config.num_ctx))
    config.use_gpu_offload = performance.get("num_gpu", 99 if config.use_gpu_offload else 0) > 0

    # 路由策略
    routing = data.get("routing", {})
    config.prefer_cloud_for_complex = routing.get("prefer_cloud_for_complex", True)
    config.auto_fallback = routing.get("auto_fallback", True)

    return config


def merge_env_vars(config: RouterConfig) -> RouterConfig:
    """用环境变量覆盖配置"""
    if "DEEPSEEK_API_KEY" in os.environ:
        config.cloud_api_key = os.environ["DEEPSEEK_API_KEY"]
    if "CLOUD_BASE_URL" in os.environ:
        config.cloud_base_url = os.environ["CLOUD_BASE_URL"]
    if "CLOUD_MODEL" in os.environ:
        config.cloud_model = os.environ["CLOUD_MODEL"]
    if "SMALL_MODEL" in os.environ:
        config.small_model = os.environ["SMALL_MODEL"]
    if "MEDIUM_MODEL" in os.environ:
        config.medium_model = os.environ["MEDIUM_MODEL"]
    if "LARGE_MODEL" in os.environ:
        config.large_model = os.environ["LARGE_MODEL"]
    return config
