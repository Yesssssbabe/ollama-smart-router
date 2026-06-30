"""
配置加载模块
支持从 YAML 配置文件和环境变量加载配置

修复内容:
- HIGH-6: 添加 _safe_float, _safe_int, _safe_str 工具函数，失败时回退默认值并记录警告
- H2: YAML 文件读取添加多编码回退和 errors='replace'
- M2: 文件存在但无读权限时捕获 PermissionError，给出有意义的错误
- M1: 环境变量空字符串不再覆盖有效配置，使用 os.environ.get() 检查非空
- L1: 统一在 merge_env_vars 中处理环境变量，移除 config_from_yaml 中的重复读取
- L4: 配置加载顺序已文档化（见 cli.py load_config 注释）
- M3: 从 YAML 读取 safety_margin_gb 并设置到 RouterConfig
"""

import logging
import os
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

from .router import RouterConfig

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATHS = [
    "config.yaml",
    "config.yml",
    "~/.config/ollama-smart-router/config.yaml",
]


def _safe_float(value, default: float, field_name: str = "") -> float:
    """安全地将值转换为 float，失败或越界时返回 default"""
    if value is None:
        return default
    try:
        f = float(value)
        if f < 0:
            if field_name:
                logger.warning(f"配置项 '{field_name}' 值 {value} 为负数，使用默认值 {default}")
            return default
        return f
    except (TypeError, ValueError):
        if field_name:
            logger.warning(f"配置项 '{field_name}' 值 '{value}' 无法转换为 float，使用默认值 {default}")
        return default


def _safe_int(value, default: int, field_name: str = "") -> int:
    """安全地将值转换为 int，失败或越界时返回 default"""
    if value is None:
        return default
    try:
        i = int(value)
        if i <= 0:
            if field_name:
                logger.warning(f"配置项 '{field_name}' 值 {value} 必须大于 0，使用默认值 {default}")
            return default
        return i
    except (TypeError, ValueError):
        if field_name:
            logger.warning(f"配置项 '{field_name}' 值 '{value}' 无法转换为 int，使用默认值 {default}")
        return default


def _safe_str(value, default: str) -> str:
    """安全地获取字符串，空值或空字符串时返回 default"""
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def load_yaml_config(path: Optional[str] = None) -> Optional[dict]:
    """加载 YAML 配置文件

    尝试多种编码（utf-8, utf-8-sig, gbk）读取，失败时使用 errors='replace'。
    文件存在但无读权限时抛出 RuntimeError。
    """
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
            # 尝试多种编码读取
            encodings = ["utf-8", "utf-8-sig", "gbk"]
            last_error = None
            for encoding in encodings:
                try:
                    with open(candidate, "r", encoding=encoding, errors="replace") as f:
                        return yaml.safe_load(f) or {}
                except UnicodeDecodeError as e:
                    last_error = e
                    continue
                except PermissionError as e:
                    raise RuntimeError(f"配置文件存在但无读取权限: {candidate}") from e
                except yaml.YAMLError as e:
                    raise RuntimeError(f"YAML 解析失败: {candidate} - {e}") from e
            # 如果所有编码都失败
            if last_error:
                raise RuntimeError(f"无法以支持的编码读取配置文件: {candidate}") from last_error

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
        config.small_model = _safe_str(models["small"].get("name"), config.small_model)
        config.small_model_vram = _safe_float(
            models["small"].get("vram_gb"), config.small_model_vram, "models.small.vram_gb"
        )
    if "medium" in models:
        config.medium_model = _safe_str(models["medium"].get("name"), config.medium_model)
        config.medium_model_vram = _safe_float(
            models["medium"].get("vram_gb"), config.medium_model_vram, "models.medium.vram_gb"
        )
    if "large" in models:
        config.large_model = _safe_str(models["large"].get("name"), config.large_model)
        config.large_model_vram = _safe_float(
            models["large"].get("vram_gb"), config.large_model_vram, "models.large.vram_gb"
        )

    # GPU 阈值
    thresholds = data.get("gpu_thresholds", {})
    config.gpu_vram_threshold = _safe_float(
        thresholds.get("min_free_vram_gb"), config.gpu_vram_threshold, "gpu_thresholds.min_free_vram_gb"
    )
    # M3: safety_margin_gb 从配置读取，不再硬编码
    if hasattr(config, "safety_margin_gb"):
        config.safety_margin_gb = _safe_float(
            thresholds.get("safety_margin_gb"), config.safety_margin_gb, "gpu_thresholds.safety_margin_gb"
        )

    # 云端配置
    cloud = data.get("cloud", {})
    config.cloud_base_url = _safe_str(cloud.get("base_url"), config.cloud_base_url)
    config.cloud_model = _safe_str(cloud.get("model"), config.cloud_model)
    # L1: 统一在 merge_env_vars 中处理环境变量，此处仅读取 YAML 中的值
    yaml_key = cloud.get("api_key")
    if yaml_key and yaml_key != config.cloud_api_key:
        config.cloud_api_key = str(yaml_key)
        logger.warning(
            "⚠️ API 密钥配置在 config.yaml 中不安全，建议使用环境变量 DEEPSEEK_API_KEY 或 .env 文件"
        )

    # 性能配置
    performance = data.get("performance", {})
    config.num_ctx = _safe_int(
        performance.get("num_ctx"), config.num_ctx, "performance.num_ctx"
    )
    # H3: 类型安全比较，先转 int 再比较
    num_gpu_raw = performance.get("num_gpu", 99 if config.use_gpu_offload else 0)
    try:
        config.use_gpu_offload = int(num_gpu_raw) > 0
    except (TypeError, ValueError):
        pass  # 保持原有值

    # 路由策略
    routing = data.get("routing", {})
    config.prefer_cloud_for_complex = routing.get(
        "prefer_cloud_for_complex", config.prefer_cloud_for_complex
    )
    config.auto_fallback = routing.get("auto_fallback", config.auto_fallback)

    return config


def merge_env_vars(config: RouterConfig) -> RouterConfig:
    """用环境变量覆盖配置（仅覆盖非空值）"""
    # M1: 使用 os.environ.get() 检查非空，避免空字符串覆盖有效配置
    env_key = os.environ.get("DEEPSEEK_API_KEY")
    if env_key:
        config.cloud_api_key = env_key

    env_url = os.environ.get("CLOUD_BASE_URL")
    if env_url:
        config.cloud_base_url = env_url

    env_model = os.environ.get("CLOUD_MODEL")
    if env_model:
        config.cloud_model = env_model

    env_small = os.environ.get("SMALL_MODEL")
    if env_small:
        config.small_model = env_small

    env_medium = os.environ.get("MEDIUM_MODEL")
    if env_medium:
        config.medium_model = env_medium

    env_large = os.environ.get("LARGE_MODEL")
    if env_large:
        config.large_model = env_large

    return config
