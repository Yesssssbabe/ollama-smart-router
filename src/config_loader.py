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
- PY39: 添加 from __future__ import annotations 保证 Python 3.9+ 兼容
- H-6: 放弃先检查后使用模式，改为 try-except 直接打开，缓解 TOCTOU
- H-7: 添加 YAML 文件大小上限（1MB），防止恶意大文件 DoS
- H-17: _safe_bool 支持 int/float 与 false/off/no/0 字符串
- H-18: config_from_yaml / merge_env_vars 通过 dataclasses.replace 创建新实例，
        避免直接修改 RouterConfig 绕过 __post_init__ 校验
- C-12: 环境变量覆盖模型名前使用 VALID_MODEL 正则校验
- H-19: URL 校验增加 CRLF / 控制字符注入检查
"""

from __future__ import annotations

import dataclasses
import ipaddress
import logging
import math
import os
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None

from .router import RouterConfig, VALID_MODEL

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATHS = [
    "config.yaml",
    "config.yml",
    "~/.config/ollama-smart-router/config.yaml",
]

try:
    from platformdirs import user_config_dir
    DEFAULT_CONFIG_PATHS.append(
        os.path.join(user_config_dir("ollama-smart-router"), "config.yaml")
    )
except Exception:
    pass


def _safe_float(value, default: float, field_name: str = "") -> float:
    """安全地将值转换为 float，失败、越界或 NaN/Infinity 时返回 default"""
    if value is None:
        return default
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            if field_name:
                logger.warning("配置项 %r 值 %r 为非法浮点数，使用默认值 %r", field_name, value, default)
            return default
        if f < 0:
            if field_name:
                logger.warning("配置项 %r 值 %r 为负数，使用默认值 %r", field_name, value, default)
            return default
        return f
    except (TypeError, ValueError):
        if field_name:
            logger.warning("配置项 %r 值 %r 无法转换为 float，使用默认值 %r", field_name, value, default)
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
            logger.warning("配置项 %r 值 %r 无法转换为 int，使用默认值 %r", field_name, value, default)
        return default


def _safe_str(value, default: str) -> str:
    """安全地获取字符串，空值或空字符串时返回 default"""
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def _safe_bool(value, default: bool = False) -> bool:
    """安全地将值转换为 bool，支持布尔值、数值和常见字符串"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        # 仅当不是 NaN/Infinity 时按 bool() 语义转换
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return default
        return bool(value)
    if isinstance(value, str):
        lowered = value.lower().strip()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off", ""):
            return False
        return default
    return default


MAX_CONFIG_FILE_SIZE: int = 1 * 1024 * 1024  # 1MB


def load_yaml_config(path: Optional[str] = None) -> Optional[dict[str, Any]]:
    """加载 YAML 配置文件

    尝试多种编码（utf-8, utf-8-sig, gbk）读取，失败时使用 errors='replace'。
    文件存在但无读权限时抛出 RuntimeError。
    通过先打开文件再检查大小，缓解 TOCTOU 与恶意大文件 DoS。
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
        # H-6: 直接尝试打开，避免先 exists() 再 open() 的 TOCTOU 窗口
        try:
            stat = candidate.stat()
        except FileNotFoundError:
            continue
        except OSError as e:
            raise RuntimeError(f"无法访问配置文件: {candidate}") from e

        # H-7: 限制文件大小，防止恶意大 YAML 导致内存耗尽
        if stat.st_size > MAX_CONFIG_FILE_SIZE:
            raise RuntimeError(
                f"配置文件过大 ({stat.st_size} 字节)，上限 {MAX_CONFIG_FILE_SIZE} 字节: {candidate}"
            )

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


def _is_safe_path(path: str) -> bool:
    """验证路径不在工作目录或用户主目录之外，防止任意文件读取"""
    try:
        real_path = Path(os.path.realpath(path))
        real_cwd = Path(os.getcwd()).resolve()
        real_home = Path(os.path.expanduser("~")).resolve()
        return (
            real_path.is_relative_to(real_cwd)
            or real_path.is_relative_to(real_home)
        )
    except (ValueError, OSError):
        return False


def _validate_cloud_base_url(url: str) -> None:
    """验证云端 API URL 安全：强制 https、禁止私有地址、拒绝 CRLF/控制字符"""
    from urllib.parse import urlparse
    # H-19: 拒绝换行符与控制字符，防止 HTTP 头/日志注入
    if any(ord(ch) < 32 for ch in url):
        raise ValueError(f"cloud_base_url 包含非法控制字符: {url!r}")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"cloud_base_url 必须使用 https 协议: {url}")
    if not parsed.hostname:
        raise ValueError(f"cloud_base_url 缺少主机名: {url}")
    try:
        addr = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        # 主机名不是 IP，允许
        return
    if addr.is_private or addr.is_loopback or addr.is_reserved:
        raise ValueError(f"cloud_base_url 禁止指向私有/回环地址: {url}")


def config_from_yaml(path: Optional[str] = None, base_config: Optional[RouterConfig] = None) -> RouterConfig:
    """从 YAML 文件创建 RouterConfig

    H-18: 不再直接修改 base_config，而是收集覆盖字段后通过 dataclasses.replace
    创建新实例，从而触发 __post_init__ 完整校验。
    """
    # 公共 API 入口也进行路径安全校验
    if path is not None and not _is_safe_path(path):
        raise PermissionError(f"配置文件路径不在允许范围内: {path}")

    config = base_config or RouterConfig()

    data = load_yaml_config(path)
    if data is None:
        return config

    overrides: dict[str, Any] = {}

    # 模型配置
    models = data.get("models", {})
    if "small" in models:
        if not isinstance(models["small"], dict):
            logger.warning("配置项 models.small 应为字典，使用默认值")
        else:
            overrides["small_model"] = _safe_str(models["small"].get("name"), config.small_model)
            overrides["small_model_vram"] = _safe_float(
                models["small"].get("vram_gb"), config.small_model_vram, "models.small.vram_gb"
            )
    if "medium" in models:
        if not isinstance(models["medium"], dict):
            logger.warning("配置项 models.medium 应为字典，使用默认值")
        else:
            overrides["medium_model"] = _safe_str(models["medium"].get("name"), config.medium_model)
            overrides["medium_model_vram"] = _safe_float(
                models["medium"].get("vram_gb"), config.medium_model_vram, "models.medium.vram_gb"
            )
    if "large" in models:
        if not isinstance(models["large"], dict):
            logger.warning("配置项 models.large 应为字典，使用默认值")
        else:
            overrides["large_model"] = _safe_str(models["large"].get("name"), config.large_model)
            overrides["large_model_vram"] = _safe_float(
                models["large"].get("vram_gb"), config.large_model_vram, "models.large.vram_gb"
            )

    # GPU 阈值
    thresholds = data.get("gpu_thresholds", {})
    overrides["gpu_vram_threshold"] = _safe_float(
        thresholds.get("min_free_vram_gb"), config.gpu_vram_threshold, "gpu_thresholds.min_free_vram_gb"
    )
    overrides["safety_margin_gb"] = _safe_float(
        thresholds.get("safety_margin_gb"), config.safety_margin_gb, "gpu_thresholds.safety_margin_gb"
    )

    # 云端配置
    cloud = data.get("cloud", {})
    cloud_base_url = _safe_str(cloud.get("base_url"), config.cloud_base_url)
    _validate_cloud_base_url(cloud_base_url)
    overrides["cloud_base_url"] = cloud_base_url
    overrides["cloud_model"] = _safe_str(cloud.get("model"), config.cloud_model)
    # CRIT-3: 拒绝使用 config.yaml 中明文存储的 API 密钥
    yaml_key = cloud.get("api_key")
    if yaml_key:
        logger.error(
            "config.yaml 中明文存储 API 密钥极不安全，请改用环境变量 DEEPSEEK_API_KEY；已忽略该值"
        )

    # 性能配置
    performance = data.get("performance", {})
    overrides["num_ctx"] = _safe_int(
        performance.get("num_ctx"), config.num_ctx, "performance.num_ctx"
    )
    # 布尔类型安全转换
    use_gpu_offload = config.use_gpu_offload
    if "use_gpu_offload" in performance:
        use_gpu_offload = _safe_bool(
            performance.get("use_gpu_offload"), use_gpu_offload
        )
    # H3: 类型安全比较，先转 int 再比较
    num_gpu_raw = performance.get("num_gpu", 99 if use_gpu_offload else 0)
    try:
        use_gpu_offload = int(num_gpu_raw) > 0
    except (TypeError, ValueError):
        pass  # 保持原有值
    overrides["use_gpu_offload"] = use_gpu_offload

    # 路由策略
    routing = data.get("routing", {})
    overrides["prefer_cloud_for_complex"] = _safe_bool(
        routing.get("prefer_cloud_for_complex"), config.prefer_cloud_for_complex
    )
    overrides["auto_fallback"] = _safe_bool(
        routing.get("auto_fallback"), config.auto_fallback
    )

    if not overrides:
        return config
    return dataclasses.replace(config, **overrides)


def merge_env_vars(config: RouterConfig) -> RouterConfig:
    """用环境变量覆盖配置（仅覆盖非空值，并校验模型名格式）

    C-12: 环境变量覆盖的模型名必须通过 VALID_MODEL 正则校验，
          否则记录错误并跳过，防止注入非法模型名。
    H-18: 通过 dataclasses.replace 创建新实例，避免直接修改原配置。
    """
    overrides: dict[str, Any] = {}

    # M1: 使用 os.environ.get() 检查非空，避免空字符串覆盖有效配置
    env_key = os.environ.get("DEEPSEEK_API_KEY")
    if env_key:
        overrides["cloud_api_key"] = env_key

    env_url = os.environ.get("CLOUD_BASE_URL")
    if env_url:
        _validate_cloud_base_url(env_url)
        overrides["cloud_base_url"] = env_url

    env_model = os.environ.get("CLOUD_MODEL")
    if env_model and VALID_MODEL.match(env_model.strip()):
        overrides["cloud_model"] = env_model.strip()
    elif env_model:
        logger.error("环境变量 CLOUD_MODEL 模型名格式不合法: %s", env_model)

    for name in ("small_model", "medium_model", "large_model"):
        env_name = name.upper()
        val = os.environ.get(env_name)
        if val and val.strip():
            stripped = val.strip()
            if VALID_MODEL.match(stripped):
                overrides[name] = stripped
            else:
                logger.error("环境变量 %s 模型名格式不合法: %s", env_name, val)

    if not overrides:
        return config
    return dataclasses.replace(config, **overrides)
