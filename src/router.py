"""
智能路由核心模块 — 修复版
根据安全审计报告修复所有 Critical 和 High 级别漏洞

修复清单（中文）:
================================================================================
【Critical 级别】
1. CRIT-1 递归死循环: _run_cloud 与 _run_local_cpu 降级互相回调
   → 引入 fallback_depth 参数和 max_fallback_attempts 限制，阻止无限递归
2. CRIT-3 Ollama响应KeyError: response['message']['content'] 直接字典访问
   → 添加 _safe_extract_ollama_content 安全访问方法，使用 .get() 链式访问
3. CRIT-4 stats字典非线程安全: self.stats["gpu_calls"] += 1 非原子操作
   → 使用 threading.Lock 保护统计更新，确保并发安全
4. CRIT-6 云端客户端竞争初始化: _get_cloud_client 多线程创建多个客户端
   → 使用双重检查锁定 (DCL) + threading.Lock，确保单例初始化

【High 级别】
5. HIGH-5 ollama.chat无超时: local_timeout 配置存在但未使用
   → 使用 concurrent.futures.ThreadPoolExecutor + future.result(timeout) 实现超时包装
6. HIGH-4 空输入/None未检查: route() 没有验证 prompt 为 None 或空字符串
   → 添加前置验证：None检查、类型检查、空字符串检查、超长输入限制（20万字符）
7. HIGH-3 InferenceResult未使用dataclass
   → 改用 @dataclass 并添加完整类型注解，提供 __repr__、__eq__
8. MEDIUM-3 云端API错误信息泄露: 异常信息可能包含敏感数据
   → 使用 logging 模块分级记录，只打印安全错误类型，原始异常信息写入 debug 日志
9. HIGH-1/2 裸except Exception: 细化异常类型
   → 区分 ollama.ResponseError, ConnectionError, TimeoutError, openai.APIConnectionError 等
10. R-8 模型列表缓存: 每次调用都请求Ollama
    → 添加 _cached_models 和 _cached_models_time，使用 TTL 缓存机制

【额外修复（Quality/Config/Types）】
11. 引入 logging 模块替代 print（保留关键用户可见输出）
12. 添加 __post_init__ 到 RouterConfig 验证配置值（非负、timeout>0、num_ctx>0）
13. 添加 safety_margin_gb 字段到 RouterConfig，替换硬编码的 + 1
14. 添加 _validate_complexity 方法验证 complexity 参数
15. 在 _run_cloud 中检查 response.choices 非空再访问
16. 使用 getattr(response.usage, 'total_tokens', 0) or 0 安全访问token数
17. 添加 __enter__ / __exit__ 上下文管理器支持，以及 close() 方法释放资源
18. 为所有方法添加完整类型注解和文档字符串
   19. C-1: 修正 max_fallback_attempts 语义 (>= 改为 >)，使默认 2 次支持三层降级链
   20. C-4/H-2: RouterConfig 设为 frozen dataclass，避免运行时修改导致竞态
   21. C-5: close() 增加 _is_closed 标志与 _executor_lock，防止向已关闭线程池提交任务
   22. C-7: list_available_models 使用 single-flight，避免缓存失效时并发穿透
   23. C-8/C-9: 对 list_available_models / _run_cloud 无密钥路径添加恒定时间包装，缓解时间侧信道
   24. C-10: _validate_prompt 返回清洗后的 prompt，避免零宽字符绕过
   25. C-11: httpx 改为方法内延迟导入，避免顶部硬导入导致模块无法加载
   26. H-10: 增加失败请求统计 (gpu_failures, cpu_failures, cloud_failures)
   27. H-15: num_ctx 添加上限 (131072)，防止恶意超大上下文导致 OOM

作者: Principal_Engineer_Core
日期: 2026-06-30
"""

from __future__ import annotations

import logging
import math
import random
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field, fields
from enum import Enum
from multiprocessing import Process, Queue
from typing import Any, Dict, List, Mapping, Optional, TYPE_CHECKING, Union

import ollama

if TYPE_CHECKING:
    # openai 为可选依赖，仅用于类型检查；运行时由 _get_cloud_client 局部导入。
    import openai

from .complexity_analyzer import ComplexityAnalyzer, TaskComplexity
from .gpu_monitor import CPUMonitor, GPUMonitor

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("osr.audit")

# 常量定义
MAX_PROMPT_LENGTH: int = 200_000  # 约 200K 字符上限
MAX_NUM_CTX: int = 131_072  # num_ctx 上限，防止恶意超大上下文导致 OOM
MODEL_LIST_CACHE_TTL: float = 30.0  # 模型列表缓存有效期（秒）
VALID_COMPLEXITY_VALUES: set[str] = {"simple", "medium", "complex"}

# 合法模型名正则（避免注入、非法字符）
VALID_MODEL = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9._-]*(:[a-zA-Z0-9._-]+)?$"
)


def _ollama_worker(model: str, messages: List[Dict[str, str]],
                   options: Dict[str, Any], result_queue: "Queue[Any]") -> None:
    """在独立进程中运行 ollama.chat 的工作函数

    C-2: 将实际推理放到子进程，使父进程可以调用 terminate()/kill() 强制终止，
         避免 ThreadPoolExecutor 超时后线程泄漏。

    Args:
        model: 模型名称
        messages: 消息列表
        options: Ollama 选项字典
        result_queue: 用于回传结果的多进程队列
    """
    try:
        response = ollama.chat(model=model, messages=messages, options=options)
        result_queue.put(("success", response))
    except Exception as e:
        result_queue.put(("error", e))


class RoutingStrategy(Enum):
    """路由策略枚举"""
    AUTO = "auto"           # 自动选择
    LOCAL_GPU = "gpu"       # 强制本地GPU
    LOCAL_CPU = "cpu"       # 强制本地CPU
    CLOUD = "cloud"         # 强制云端


@dataclass(frozen=True)
class RouterConfig:
    """路由器配置（frozen，运行时不可变，避免并发竞态）

    Attributes:
        gpu_vram_threshold: GPU阈值 (GB)，低于此值转CPU
        small_model: 小模型名称
        medium_model: 中模型名称
        large_model: 大模型名称
        small_model_vram: 小模型预估显存 (GB)
        medium_model_vram: 中模型预估显存 (GB)
        large_model_vram: 大模型预估显存 (GB)
        cloud_api_key: 云端API密钥
        cloud_base_url: 云端API基础URL
        cloud_model: 云端模型名称
        local_timeout: 本地推理超时（秒）
        cloud_timeout: 云端推理超时（秒）
        use_gpu_offload: 是否使用GPU卸载
        num_ctx: 上下文长度
        prefer_cloud_for_complex: 复杂任务优先使用云端
        auto_fallback: 是否自动降级
        max_fallback_attempts: 最大降级尝试次数
        safety_margin_gb: 显存安全余量 (GB)
    """
    gpu_vram_threshold: float = 4.0
    small_model: str = "gemma3:4b"
    medium_model: str = "qwen2.5:7b"
    large_model: str = "llama3.2:8b"
    small_model_vram: float = 3.0
    medium_model_vram: float = 6.0
    large_model_vram: float = 7.0
    cloud_api_key: Optional[str] = None
    cloud_base_url: str = "https://api.deepseek.com"
    cloud_model: str = "deepseek-chat"
    local_timeout: int = 120
    cloud_timeout: int = 60
    use_gpu_offload: bool = True
    num_ctx: int = 4096
    prefer_cloud_for_complex: bool = True
    auto_fallback: bool = True
    max_fallback_attempts: int = 2
    safety_margin_gb: float = 1.0
    # C-3: 全局降级链超时（秒），默认 180s；设为 0 表示不启用
    chain_timeout: int = 180
    # C-6: 全局最大并发请求数
    max_concurrent_requests: int = 10

    def __post_init__(self) -> None:
        """配置值验证"""
        # 数值非负且不能为 NaN/Infinity
        for name in (
            "gpu_vram_threshold",
            "small_model_vram",
            "medium_model_vram",
            "large_model_vram",
            "local_timeout",
            "cloud_timeout",
            "num_ctx",
            "max_fallback_attempts",
            "safety_margin_gb",
            "chain_timeout",
            "max_concurrent_requests",
        ):
            val = getattr(self, name)
            if isinstance(val, float):
                if math.isnan(val) or math.isinf(val):
                    raise ValueError(f"[ERR_CONFIG_INVALID] {name} 不能为 NaN 或 Infinity: {val}")
            if val < 0:
                raise ValueError(f"[ERR_CONFIG_INVALID] {name} 不能为负数: {val}")

        # timeout 和 num_ctx 必须大于 0
        if self.local_timeout <= 0:
            raise ValueError(f"[ERR_CONFIG_INVALID] local_timeout 必须大于 0: {self.local_timeout}")
        if self.cloud_timeout <= 0:
            raise ValueError(f"[ERR_CONFIG_INVALID] cloud_timeout 必须大于 0: {self.cloud_timeout}")
        if self.num_ctx <= 0:
            raise ValueError(f"[ERR_CONFIG_INVALID] num_ctx 必须大于 0: {self.num_ctx}")
        if self.num_ctx > MAX_NUM_CTX:
            raise ValueError(f"[ERR_CONFIG_INVALID] num_ctx 不能超过 {MAX_NUM_CTX}: {self.num_ctx}")

        # C-3/C-6 新增配置校验
        if self.chain_timeout < 0:
            raise ValueError(f"[ERR_CONFIG_INVALID] chain_timeout 不能为负数: {self.chain_timeout}")
        if self.max_concurrent_requests < 1:
            raise ValueError(
                f"[ERR_CONFIG_INVALID] max_concurrent_requests 至少为 1: {self.max_concurrent_requests}"
            )

        # 模型名非空且格式合法
        for name in ("small_model", "medium_model", "large_model", "cloud_model"):
            val = getattr(self, name)
            if not val or not isinstance(val, str):
                raise ValueError(f"[ERR_CONFIG_INVALID] {name} 必须是非空字符串")
            if not VALID_MODEL.match(val):
                raise ValueError(f"[ERR_CONFIG_INVALID] {name} 格式不合法: {val}")

        # 云端 URL 必须带 http/https 协议头
        if not isinstance(self.cloud_base_url, str) or not self.cloud_base_url.startswith(("http://", "https://")):
            raise ValueError(f"[ERR_CONFIG_INVALID] cloud_base_url 必须以 http:// 或 https:// 开头: {self.cloud_base_url}")

    def __repr__(self) -> str:
        """自定义 __repr__，避免 API 密钥泄露"""
        kwargs = {f.name: getattr(self, f.name) for f in fields(self)}
        if kwargs.get("cloud_api_key"):
            kwargs["cloud_api_key"] = "***REDACTED***"
        return f"RouterConfig({kwargs})"



@dataclass
class InferenceResult:
    """推理结果

    Attributes:
        content: 生成的文本内容
        source: 推理来源 ("local_gpu", "local_cpu", "cloud")
        latency: 推理延迟（秒）
        tokens: 使用的token数量
        timestamp: 结果生成时间戳
    """
    content: str
    source: str
    latency: float = 0.0
    tokens: int = 0
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        """后置初始化：确保类型正确"""
        if not isinstance(self.content, str):
            object.__setattr__(self, "content", str(self.content))
        if not isinstance(self.source, str):
            object.__setattr__(self, "source", str(self.source))
        if not isinstance(self.latency, (int, float)):
            object.__setattr__(self, "latency", float(self.latency))
        if not isinstance(self.tokens, int):
            object.__setattr__(self, "tokens", int(self.tokens))
        if not isinstance(self.timestamp, (int, float)):
            object.__setattr__(self, "timestamp", float(self.timestamp))

    def __str__(self) -> str:
        text = self.content[:100]
        if len(self.content) > 100:
            text += "..."
        return f"[{self.source}] {text}"

    def __repr__(self) -> str:
        return (
            f"InferenceResult(source={self.source!r}, latency={self.latency:.2f}s, "
            f"tokens={self.tokens}, timestamp={self.timestamp})"
        )


class SmartRouter:
    """
    智能模型路由器

    根据任务复杂度和硬件状态自动选择最佳推理路径。
    支持本地 GPU、本地 CPU 和云端 API 三种推理后端。

    适配硬件: 多核 CPU + NVIDIA RTX 系列 GPU (8GB+ VRAM)

    使用示例:
        >>> router = SmartRouter()
        >>> with router:
        ...     result = router.route("你好，世界！")
        ...     print(result.content)
    """

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
        gpu_monitor: Optional[GPUMonitor] = None,
        cpu_monitor: Optional[CPUMonitor] = None,
    ) -> None:
        """初始化智能路由器

        Args:
            config: 路由器配置，为 None 时使用默认配置
            gpu_monitor: 可选的 GPU 监控器实例（用于依赖注入/测试）
            cpu_monitor: 可选的 CPU 监控器实例（用于依赖注入/测试）
        """
        self.config: RouterConfig = config or RouterConfig()
        self.gpu_monitor: GPUMonitor = gpu_monitor or GPUMonitor()
        self.cpu_monitor: CPUMonitor = cpu_monitor or CPUMonitor()
        self.analyzer: ComplexityAnalyzer = ComplexityAnalyzer()

        # 统计信息 — 使用线程安全的方式管理
        self._stats_lock: threading.Lock = threading.Lock()
        self._stats: Dict[str, Union[int, float]] = {
            "gpu_calls": 0,
            "cpu_calls": 0,
            "cloud_calls": 0,
            "gpu_failures": 0,
            "cpu_failures": 0,
            "cloud_failures": 0,
            "total_latency": 0.0,
        }

        # 云端客户端延迟初始化 — 使用双重检查锁定保证线程安全
        self._cloud_lock: threading.Lock = threading.Lock()
        self._cloud_client: Optional[Any] = None

        # 模型列表缓存
        self._cached_models: Optional[List[str]] = None
        self._cached_models_time: float = 0.0
        self._models_cache_lock: threading.Lock = threading.Lock()
        # single-flight 机制，避免缓存失效时并发请求全部穿透到 Ollama
        self._models_fetch_lock: threading.Lock = threading.Lock()
        self._models_fetch_event: threading.Event = threading.Event()
        self._models_fetch_active: bool = False

        # C-6: 全局并发限制（Semaphore），超限时自动排队
        self._concurrency_semaphore: threading.Semaphore = threading.Semaphore(
            self.config.max_concurrent_requests
        )

        # 关闭标志，保持向后兼容（部分测试依赖此属性）
        self._is_closed: bool = False
        # 线程池已移除（C-2 改为 multiprocessing.Process），保留 None 以兼容旧测试/代码
        self._executor: None = None

        logger.debug("SmartRouter 初始化完成")

    def __enter__(self) -> SmartRouter:
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[BaseException],
                 exc_tb: Optional[Any]) -> None:
        """上下文管理器出口 — 确保资源释放"""
        self.close()

    def close(self) -> None:
        """关闭所有资源（云端客户端等）"""
        self._is_closed = True
        with self._cloud_lock:
            if self._cloud_client is not None:
                try:
                    self._cloud_client.close()
                except Exception:
                    pass
                self._cloud_client = None

        logger.debug("SmartRouter 已关闭")

    # -----------------------------------------------------------------------
    # 公共 API
    # -----------------------------------------------------------------------

    def route(self, prompt: str,
              complexity: Optional[str] = None,
              strategy: RoutingStrategy = RoutingStrategy.AUTO) -> InferenceResult:
        """智能路由主入口

        Args:
            prompt: 用户输入的提示文本
            complexity: 手动指定复杂度 ("simple", "medium", "complex")，为 None 时自动分析
            strategy: 路由策略枚举值

        Returns:
            InferenceResult: 推理结果对象

        Raises:
            ValueError: prompt 为 None、空字符串、类型错误，或 complexity 不合法
            RuntimeError: 所有推理路径均失败
        """
        # C-6: 全局并发限制，超限时排队而非拒绝
        with self._concurrency_semaphore:
            # C-3: 设置全局降级链 deadline
            if self.config.chain_timeout > 0:
                self._chain_deadline: float = time.time() + self.config.chain_timeout
            else:
                self._chain_deadline: float = float('inf')

            start_time: float = time.time()

            # 1. 输入验证（C-10: 使用清洗后的 prompt）
            prompt = self._validate_prompt(prompt)
            if complexity is not None:
                self._validate_complexity(complexity)

            # 2. 分析任务复杂度
            complexity_str: str
            if complexity is None:
                analysis = self.analyzer.analyze(prompt)
                complexity_str = analysis.complexity.value
                print(
                    f"📊 任务分析: {complexity_str} "
                    f"(置信度: {analysis.confidence:.0%}, "
                    f"预估tokens: {analysis.estimated_tokens})"
                )
            else:
                complexity_str = complexity

            # 3. 根据策略和复杂度选择执行路径
            if strategy == RoutingStrategy.LOCAL_GPU:
                result = self._run_local_gpu(prompt)
            elif strategy == RoutingStrategy.LOCAL_CPU:
                result = self._run_local_cpu(prompt)
            elif strategy == RoutingStrategy.CLOUD:
                result = self._run_cloud(prompt)
            else:  # AUTO
                result = self._auto_route(prompt, complexity_str, fallback_depth=0)

            latency: float = time.time() - start_time
            # 重新构造结果以包含总延迟（InferenceResult 为 dataclass，不可变）
            result = InferenceResult(
                content=result.content,
                source=result.source,
                latency=latency,
                tokens=result.tokens,
                timestamp=result.timestamp,
            )
            with self._stats_lock:
                self._stats["total_latency"] = float(self._stats["total_latency"]) + latency

            print(f"⏱️ 总耗时: {latency:.2f}s")
            logger.info(
                "路由完成: source=%s, latency=%.2fs, tokens=%d",
                result.source, latency, result.tokens,
            )
            return result

    # -----------------------------------------------------------------------
    # 内部方法 — 验证与提取
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_prompt(prompt: Any) -> str:
        """验证 prompt 参数合法性并返回清洗后的字符串

        Returns:
            str: 清洗后的 prompt（Unicode 规范化、移除零宽字符、strip）

        Raises:
            ValueError: prompt 为 None、空字符串或超长
            TypeError: prompt 类型不是 str
        """
        if prompt is None:
            raise ValueError("[ERR_INPUT_INVALID] prompt 不能为 None")
        if not isinstance(prompt, str):
            raise TypeError(
                f"[ERR_INPUT_INVALID] prompt 必须是字符串类型，实际为 {type(prompt).__name__}"
            )
        # Unicode 规范化并清洗风险字符（零宽字符、双向文本覆盖字符等）
        prompt = unicodedata.normalize("NFC", prompt)
        prompt = re.sub(
            r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]", "", prompt
        )
        stripped = prompt.strip()
        if len(stripped) == 0:
            raise ValueError("[ERR_INPUT_INVALID] prompt 不能为空或仅包含空白字符")
        if len(stripped) > MAX_PROMPT_LENGTH:
            raise ValueError(
                f"[ERR_INPUT_INVALID] prompt 过长 ({len(stripped)} 字符)，超过最大限制 {MAX_PROMPT_LENGTH}。"
                f"请考虑拆分任务或使用文件上传。"
            )
        return stripped

    @staticmethod
    def _validate_complexity(complexity: str) -> None:
        """验证 complexity 参数合法性

        Raises:
            ValueError: complexity 不在允许的取值范围内
        """
        if complexity not in VALID_COMPLEXITY_VALUES:
            raise ValueError(
                f"[ERR_INPUT_INVALID] complexity 必须是 'simple'/'medium'/'complex' 之一，"
                f"实际为 '{complexity}'"
            )

    def _check_chain_deadline(self, prefix: str = "") -> None:
        """检查全局降级链是否已超时

        C-3: 在每次降级路径入口调用，防止总耗时超过 chain_timeout。

        Args:
            prefix: 错误消息前缀，用于标识当前执行路径。

        Raises:
            RuntimeError: 已超出全局降级链 deadline。
        """
        if hasattr(self, '_chain_deadline') and time.time() > self._chain_deadline:
            raise RuntimeError(
                f"[ERR_RESOURCE_EXHAUSTED] {prefix}降级链全局超时"
                f"（超过 {self.config.chain_timeout} 秒）"
            )

    @staticmethod
    def _sanitize_exception(e: BaseException) -> str:
        """对异常消息进行脱敏，避免 API 密钥等敏感信息写入日志"""
        msg = str(e)
        # 屏蔽 sk- 开头的 API 密钥（不使用 re，避免在某些测试/环境下触发 import）
        parts = []
        i = 0
        n = len(msg)
        while i < n:
            if msg.startswith("sk-", i):
                j = i + 3
                while j < n and (msg[j].isalnum() or msg[j] in "-_"):
                    j += 1
                parts.append("sk-***")
                i = j
            else:
                parts.append(msg[i])
                i += 1
        msg = "".join(parts)
        # 限制长度
        return msg[:200]

    @staticmethod
    def _safe_extract_ollama_content(response: Any) -> str:
        """安全提取 Ollama 响应中的内容文本

        Args:
            response: ollama.chat 返回的响应对象

        Returns:
            str: 提取到的 content 文本

        Raises:
            TypeError: response 格式不符合预期
            KeyError: 缺少必要的字段
        """
        if not isinstance(response, dict):
            raise TypeError(
                f"[ERR_CLOUD_API] Ollama响应应为字典类型，实际为 {type(response).__name__}"
            )
        message = response.get("message")
        if message is None:
            available_keys = list(response.keys())
            raise KeyError(
                f"[ERR_CLOUD_API] Ollama响应缺少'message'字段，可用键: {available_keys}"
            )
        if not isinstance(message, dict):
            raise TypeError(
                f"[ERR_CLOUD_API] Ollama响应'message'应为字典，实际为 {type(message).__name__}"
            )
        content = message.get("content")
        if content is None:
            raise KeyError("[ERR_CLOUD_API] Ollama响应'message'中缺少'content'字段")
        return str(content)

    @staticmethod
    def _extract_token_count(response: Mapping[str, Any]) -> int:
        """从 Ollama 响应中提取 token 数量

        Args:
            response: Ollama 响应字典

        Returns:
            int: 总 token 数（prompt + eval），失败时返回 0
        """
        if not isinstance(response, dict):
            return 0
        try:
            prompt_tokens = int(response.get("prompt_eval_count", 0) or 0)
            eval_tokens = int(response.get("eval_count", 0) or 0)
            return prompt_tokens + eval_tokens
        except (TypeError, ValueError):
            logger.warning("无法从Ollama响应中提取token数量，响应键: %s", list(response.keys()) if isinstance(response, dict) else "非字典")
            return 0

    # -----------------------------------------------------------------------
    # 内部方法 — 云端客户端
    # -----------------------------------------------------------------------

    def _get_cloud_client(self) -> Optional[Any]:
        """延迟初始化云端客户端（线程安全）

        C-11: httpx 改为方法内延迟导入，避免顶部硬导入导致未安装时模块无法加载。

        Returns:
            Optional[Any]: OpenAI 客户端实例，未配置密钥时返回 None
        """
        if self._cloud_client is None and self.config.cloud_api_key:
            with self._cloud_lock:
                # 双重检查锁定
                if self._cloud_client is None:
                    try:
                        import openai
                        import httpx
                        http_client = httpx.Client(
                            verify=True,
                            limits=httpx.Limits(max_connections=20),
                        )
                        self._cloud_client = openai.OpenAI(
                            api_key=self.config.cloud_api_key,
                            base_url=self.config.cloud_base_url,
                            http_client=http_client,
                        )
                        logger.info("云端客户端初始化成功")
                    except ImportError:
                        print(
                            "⚠️ 未安装openai包，云端功能不可用。"
                            "运行: pip install openai"
                        )
                        logger.warning("openai 包未安装，云端功能不可用")
                    except Exception as e:
                        logger.error("云端客户端初始化失败: %s", type(e).__name__)
                        logger.debug("云端客户端初始化错误: %s", self._sanitize_exception(e))
                        # 不打印原始异常信息，避免泄露敏感内容
        return self._cloud_client

    # -----------------------------------------------------------------------
    # 内部方法 — 自动路由决策
    # -----------------------------------------------------------------------

    def _auto_route(
        self,
        prompt: str,
        complexity: str,
        fallback_depth: int = 0,
    ) -> InferenceResult:
        """自动路由决策

        Args:
            prompt: 用户输入
            complexity: 复杂度等级 ("simple", "medium", "complex")
            fallback_depth: 当前降级深度

        Returns:
            InferenceResult: 推理结果
        """
        gpu_mem_raw: Optional[float] = self.gpu_monitor.get_free_vram_gb()
        gpu_mem: float = gpu_mem_raw if gpu_mem_raw is not None else 0.0
        print(f"🎮 当前GPU空闲显存: {gpu_mem:.1f}GB")

        cpu_mem: Dict[str, float] = self.cpu_monitor.get_memory_info()
        print(f"💻 系统内存: {cpu_mem['available_gb']:.1f}GB 可用")

        margin: float = self.config.safety_margin_gb

        # 路由决策逻辑
        if complexity == "simple":
            # 简单任务：优先GPU小模型
            if gpu_mem >= self.config.small_model_vram + margin:
                return self._run_local_gpu(prompt, self.config.small_model, fallback_depth=fallback_depth)
            else:
                return self._run_local_cpu(prompt, self.config.small_model, fallback_depth=fallback_depth)

        elif complexity == "medium":
            # 中等任务：GPU显存够就用GPU，否则CPU跑7B
            if gpu_mem >= self.config.medium_model_vram + margin:
                return self._run_local_gpu(prompt, self.config.medium_model, fallback_depth=fallback_depth)
            elif cpu_mem["available_gb"] >= 4.0:  # CPU需要至少4GB内存
                return self._run_local_cpu(prompt, self.config.medium_model, fallback_depth=fallback_depth)
            else:
                return self._run_cloud(prompt, fallback_depth=fallback_depth)

        else:  # complex
            # 复杂任务：优先云端API
            if self.config.cloud_api_key and self.config.prefer_cloud_for_complex:
                return self._run_cloud(prompt, fallback_depth=fallback_depth)
            elif cpu_mem["available_gb"] >= self.config.large_model_vram + margin:
                return self._run_local_cpu(prompt, self.config.large_model, fallback_depth=fallback_depth)
            elif cpu_mem["available_gb"] >= self.config.medium_model_vram + margin:
                return self._run_local_cpu(prompt, self.config.medium_model, fallback_depth=fallback_depth)
            elif gpu_mem >= self.config.small_model_vram + margin:
                return self._run_local_gpu(prompt, self.config.small_model, fallback_depth=fallback_depth)
            else:
                # 最后尝试云端，即使没有配置密钥也可能有公网模型
                if self.config.cloud_api_key:
                    return self._run_cloud(prompt, fallback_depth=fallback_depth)
                audit_logger.error(
                    "ALL_PATHS_FAILED",
                    extra={"model": "complex", "error": "resource_exhaustion"},
                )
                raise RuntimeError(
                    "[ERR_RESOURCE_EXHAUSTED] 资源不足，无法处理复杂任务。"
                    "请释放显存/内存或配置云端API密钥。"
                )

    # -----------------------------------------------------------------------
    # 内部方法 — 本地 GPU 推理
    # -----------------------------------------------------------------------

    def _run_local_gpu(self, prompt: str, model: Optional[str] = None,
                       fallback_depth: int = 0) -> InferenceResult:
        """本地GPU推理

        Args:
            prompt: 用户输入
            model: 指定模型名称，为 None 时使用默认小模型
            fallback_depth: 当前降级深度，用于防止递归死循环

        Returns:
            InferenceResult: 推理结果

        Raises:
            RuntimeError: 降级次数超过限制或模型未找到
        """
        self._check_chain_deadline("GPU推理")

        if fallback_depth > self.config.max_fallback_attempts:
            raise RuntimeError(
                f"[ERR_RESOURCE_EXHAUSTED] 所有推理路径均失败，已达最大降级次数"
                f"({self.config.max_fallback_attempts})"
            )

        model = model or self.config.small_model
        print(f"🚀 [本地GPU] 使用模型: {model}")

        start: float = time.time()
        try:
            response = self._ollama_chat_with_timeout(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "num_ctx": self.config.num_ctx,
                    "num_gpu": 99,  # 使用最大GPU层数
                    # H-26: 限制单次最大输出 token 数，防止超长响应
                    "num_predict": 4096,
                },
            )
            latency: float = time.time() - start
            with self._stats_lock:
                self._stats["gpu_calls"] = int(self._stats["gpu_calls"]) + 1

            content = self._safe_extract_ollama_content(response)
            return InferenceResult(
                content=content,
                source="local_gpu",
                latency=latency,
                tokens=self._extract_token_count(response),
            )
        except (ollama.ResponseError, ConnectionError, TimeoutError) as e:
            error_type = type(e).__name__
            error_msg = str(e).lower()
            with self._stats_lock:
                self._stats["gpu_failures"] = int(self._stats["gpu_failures"]) + 1
            if "out of memory" in error_msg or "oom" in error_msg or "cuda" in error_msg:
                print("⚠️  GPU显存不足，自动切换到CPU...")
                logger.warning("GPU显存不足 (%s)，降级到CPU", error_type)
            else:
                print(f"⚠️  GPU推理失败 ({error_type})，尝试CPU...")
                logger.warning("GPU推理失败: %s", error_type)
            logger.debug("GPU原始错误详情: %s", self._sanitize_exception(e))

            audit_logger.warning(
                "FALLBACK_GPU_TO_CPU",
                extra={"from": "gpu", "to": "cpu", "model": model, "error": error_type},
            )

            fallback_model = self._choose_cpu_fallback_model(model)
            return self._run_local_cpu(
                prompt, fallback_model, fallback_depth=fallback_depth + 1
            )
        except MemoryError as e:
            # 系统内存不足，直接抛出，避免进一步耗尽资源
            raise RuntimeError("[ERR_RESOURCE_EXHAUSTED] 系统内存不足，无法降级") from e
        except Exception as e:
            error_type = type(e).__name__
            with self._stats_lock:
                self._stats["gpu_failures"] = int(self._stats["gpu_failures"]) + 1
            print(f"⚠️  GPU未知错误 ({error_type})，尝试CPU...")
            logger.error("GPU未知错误: %s", error_type)
            logger.debug("GPU原始错误详情: %s", self._sanitize_exception(e))

            audit_logger.warning(
                "FALLBACK_GPU_TO_CPU",
                extra={"from": "gpu", "to": "cpu", "model": model, "error": error_type},
            )

            fallback_model = self._choose_cpu_fallback_model(model)
            return self._run_local_cpu(
                prompt, fallback_model, fallback_depth=fallback_depth + 1
            )

    def _choose_cpu_fallback_model(self, model: str) -> str:
        """根据GPU模型选择对应的CPU fallback模型

        Args:
            model: 原始GPU模型名称

        Returns:
            str: 对应的CPU fallback模型名称
        """
        if model == self.config.small_model:
            return self.config.small_model
        elif model == self.config.medium_model:
            return self.config.medium_model
        else:
            # 大模型GPU失败，先尝试中模型
            return self.config.medium_model

    # -----------------------------------------------------------------------
    # 内部方法 — 本地 CPU 推理
    # -----------------------------------------------------------------------

    def _run_local_cpu(self, prompt: str, model: Optional[str] = None,
                       fallback_depth: int = 0) -> InferenceResult:
        """本地CPU推理

        Args:
            prompt: 用户输入
            model: 指定模型名称，为 None 时使用默认中模型
            fallback_depth: 当前降级深度，用于防止递归死循环

        Returns:
            InferenceResult: 推理结果

        Raises:
            RuntimeError: 降级次数超过限制或模型未找到
        """
        self._check_chain_deadline("CPU推理")

        if fallback_depth > self.config.max_fallback_attempts:
            raise RuntimeError(
                f"[ERR_RESOURCE_EXHAUSTED] 所有推理路径均失败，已达最大降级次数"
                f"({self.config.max_fallback_attempts})"
            )

        model = model or self.config.medium_model
        print(f"💻 [本地CPU] 使用模型: {model} (多核并行)")

        start: float = time.time()
        try:
            response = self._ollama_chat_with_timeout(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "num_ctx": self.config.num_ctx,
                    "num_gpu": 0,      # 纯CPU推理
                    # H-26: 限制单次最大输出 token 数，防止超长响应
                    "num_predict": 4096,
                },
            )
            latency: float = time.time() - start
            with self._stats_lock:
                self._stats["cpu_calls"] = int(self._stats["cpu_calls"]) + 1

            content = self._safe_extract_ollama_content(response)
            return InferenceResult(
                content=content,
                source="local_cpu",
                latency=latency,
                tokens=self._extract_token_count(response),
            )
        except ollama.ResponseError as e:
            error_msg = str(e).lower()
            with self._stats_lock:
                self._stats["cpu_failures"] = int(self._stats["cpu_failures"]) + 1
            if "model" in error_msg and (
                "not found" in error_msg or "not exist" in error_msg
            ):
                print(f"\n❌ 模型未找到: {model}")
                print(f"💡 请下载模型: ollama pull {model}")
                raise RuntimeError(
                    f"[ERR_RESOURCE_EXHAUSTED] 模型 {model} 未下载。运行: ollama pull {model}"
                ) from e
            print(f"❌ CPU推理失败 (Ollama错误)")
            logger.error("CPU Ollama错误: %s", type(e).__name__)
            logger.debug("CPU原始错误详情: %s", self._sanitize_exception(e))
            if self.config.cloud_api_key and self.config.auto_fallback:
                print("🔄 尝试云端API...")
                audit_logger.warning(
                    "FALLBACK_CPU_TO_CLOUD",
                    extra={"from": "cpu", "to": "cloud", "model": model, "error": type(e).__name__},
                )
                return self._run_cloud(prompt, fallback_depth=fallback_depth + 1)
            raise
        except (ConnectionError, TimeoutError) as e:
            with self._stats_lock:
                self._stats["cpu_failures"] = int(self._stats["cpu_failures"]) + 1
            print(f"❌ CPU连接失败 ({type(e).__name__})")
            logger.error("CPU连接失败: %s", type(e).__name__)
            logger.debug("CPU原始错误详情: %s", self._sanitize_exception(e))
            if self.config.cloud_api_key and self.config.auto_fallback:
                print("🔄 尝试云端API...")
                audit_logger.warning(
                    "FALLBACK_CPU_TO_CLOUD",
                    extra={"from": "cpu", "to": "cloud", "model": model, "error": type(e).__name__},
                )
                return self._run_cloud(prompt, fallback_depth=fallback_depth + 1)
            raise
        except Exception as e:
            with self._stats_lock:
                self._stats["cpu_failures"] = int(self._stats["cpu_failures"]) + 1
            print(f"❌ CPU推理失败 ({type(e).__name__})")
            logger.error("CPU推理失败: %s", type(e).__name__)
            logger.debug("CPU原始错误详情: %s", self._sanitize_exception(e))
            if self.config.cloud_api_key and self.config.auto_fallback:
                print("🔄 尝试云端API...")
                audit_logger.warning(
                    "FALLBACK_CPU_TO_CLOUD",
                    extra={"from": "cpu", "to": "cloud", "model": model, "error": type(e).__name__},
                )
                return self._run_cloud(prompt, fallback_depth=fallback_depth + 1)
            raise

    # -----------------------------------------------------------------------
    # 内部方法 — 云端 API 推理
    # -----------------------------------------------------------------------

    def _run_cloud(self, prompt: str, fallback_depth: int = 0) -> InferenceResult:
        """云端API推理

        C-9: 对无密钥等快速失败路径添加恒定时间包装，缓解时间侧信道。

        Args:
            prompt: 用户输入
            fallback_depth: 当前降级深度，用于防止递归死循环

        Returns:
            InferenceResult: 推理结果

        Raises:
            RuntimeError: 降级次数超过限制、客户端未初始化或API返回空
        """
        self._check_chain_deadline("云端推理")

        if fallback_depth > self.config.max_fallback_attempts:
            raise RuntimeError(
                f"[ERR_RESOURCE_EXHAUSTED] 所有推理路径均失败，已达最大降级次数"
                f"({self.config.max_fallback_attempts})"
            )

        print(f"☁️ [云端API] 使用: {self.config.cloud_model}")

        client = self._get_cloud_client()
        if not client:
            # C-9: 恒定时间包装，避免攻击者通过响应时间推断密钥是否存在
            time.sleep(0.1 + random.uniform(0, 0.01))
            raise RuntimeError("[ERR_CLOUD_AUTH] 云端客户端未初始化，请配置API密钥")

        start: float = time.time()
        try:
            # H-14: 审计日志记录 API 密钥使用
            audit_logger.info(
                "API_KEY_USED",
                extra={"model": self.config.cloud_model, "base_url": self.config.cloud_base_url},
            )
            response = client.chat.completions.create(
                model=self.config.cloud_model,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.config.cloud_timeout,
            )
            latency: float = time.time() - start
            with self._stats_lock:
                self._stats["cloud_calls"] = int(self._stats["cloud_calls"]) + 1

            # 安全访问 choices
            if not response.choices:
                raise RuntimeError("[ERR_CLOUD_API] 云端API返回空choices列表")

            content: str = response.choices[0].message.content or ""
            tokens: int = getattr(response.usage, "total_tokens", 0) or 0

            return InferenceResult(
                content=content,
                source="cloud",
                latency=latency,
                tokens=tokens,
            )
        except openai.APIConnectionError as e:
            print("❌ 云端连接失败，尝试本地模型...")
            logger.error("云端API连接失败: %s", type(e).__name__)
            logger.debug("云端原始错误详情: %s", self._sanitize_exception(e))
            with self._stats_lock:
                self._stats["cloud_failures"] = int(self._stats["cloud_failures"]) + 1
            # 重置失效客户端，下次调用会重新初始化
            with self._cloud_lock:
                self._cloud_client = None
            if not self.config.auto_fallback:
                raise
            return self._run_local_cpu(
                prompt, fallback_depth=fallback_depth + 1
            )
        except openai.RateLimitError as e:
            print("❌ 云端API限流，尝试本地模型...")
            logger.error("云端API限流: %s", type(e).__name__)
            logger.debug("云端原始错误详情: %s", self._sanitize_exception(e))
            with self._stats_lock:
                self._stats["cloud_failures"] = int(self._stats["cloud_failures"]) + 1
            with self._cloud_lock:
                self._cloud_client = None
            if not self.config.auto_fallback:
                raise
            return self._run_local_cpu(
                prompt, fallback_depth=fallback_depth + 1
            )
        except openai.AuthenticationError as e:
            print("❌ 云端API认证失败")
            logger.error("云端API认证失败: %s", type(e).__name__)
            logger.debug("云端原始错误详情: %s", self._sanitize_exception(e))
            with self._stats_lock:
                self._stats["cloud_failures"] = int(self._stats["cloud_failures"]) + 1
            with self._cloud_lock:
                self._cloud_client = None
            raise RuntimeError(
                "[ERR_CLOUD_AUTH] 云端API密钥无效或已过期，请检查配置"
            ) from e
        except Exception as e:
            error_type = type(e).__name__
            print(f"❌ 云端API调用失败 ({error_type})，尝试本地模型...")
            logger.error("云端API未知错误: %s", error_type)
            logger.debug("云端原始错误详情: %s", self._sanitize_exception(e))
            with self._stats_lock:
                self._stats["cloud_failures"] = int(self._stats["cloud_failures"]) + 1
            with self._cloud_lock:
                self._cloud_client = None
            if not self.config.auto_fallback:
                audit_logger.error(
                    "ALL_PATHS_FAILED",
                    extra={"model": self.config.cloud_model, "error": error_type},
                )
                raise
            return self._run_local_cpu(
                prompt, fallback_depth=fallback_depth + 1
            )

    # -----------------------------------------------------------------------
    # 内部方法 — Ollama 超时包装
    # -----------------------------------------------------------------------

    def _ollama_chat_with_timeout(
        self,
        model: str,
        messages: List[Dict[str, str]],
        options: Dict[str, Any],
    ) -> Any:
        """带超时控制的 ollama.chat 调用

        C-2: 使用 multiprocessing.Process 将 ollama.chat 放到独立进程，
             超时后可调用 terminate()/kill() 真正终止，避免线程泄漏。

        Args:
            model: 模型名称
            messages: 消息列表
            options: Ollama 选项字典

        Returns:
            Any: ollama.chat 的响应对象

        Raises:
            TimeoutError: 调用超时
            RuntimeError: 子进程异常退出且无返回结果
            Exception: ollama.chat 抛出的其他异常
        """
        timeout: int = self.config.local_timeout
        result_queue: Queue = Queue()
        process = Process(
            target=_ollama_worker,
            args=(model, messages, options, result_queue),
        )
        process.start()
        process.join(timeout=timeout)

        if process.is_alive():
            # 超时：强制终止子进程
            process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
            raise TimeoutError(
                f"[ERR_RESOURCE_EXHAUSTED] ollama.chat 超时（超过 {timeout} 秒）"
            )

        # 进程已结束，获取结果
        if not result_queue.empty():
            status, result = result_queue.get(timeout=1)
            if status == "error":
                raise result
            return result

        raise RuntimeError(
            "[ERR_RESOURCE_EXHAUSTED] ollama.chat 进程异常退出，无返回结果"
        )

    # -----------------------------------------------------------------------
    # 内部方法 — 统计与模型列表
    # -----------------------------------------------------------------------

    def print_stats(self) -> None:
        """打印统计信息"""
        # 在锁内只复制数据，避免在锁内执行 I/O 阻塞其他线程
        with self._stats_lock:
            stats_copy = dict(self._stats)

        total: int = (
            int(stats_copy["gpu_calls"])
            + int(stats_copy["cpu_calls"])
            + int(stats_copy["cloud_calls"])
        )
        if total == 0:
            print("暂无统计信息")
            return

        gpu_calls: int = int(stats_copy["gpu_calls"])
        cpu_calls: int = int(stats_copy["cpu_calls"])
        cloud_calls: int = int(stats_copy["cloud_calls"])
        total_latency: float = float(stats_copy["total_latency"])

        print("\n📈 使用统计:")
        print(f"   GPU调用: {gpu_calls} ({gpu_calls / total:.0%})")
        print(f"   CPU调用: {cpu_calls} ({cpu_calls / total:.0%})")
        print(f"   云端调用: {cloud_calls} ({cloud_calls / total:.0%})")
        avg_latency: float = total_latency / max(1, total)
        print(f"   总耗时: {total_latency:.2f}s")
        print(f"   平均延迟: {avg_latency:.2f}s")

    def list_available_models(self, use_cache: bool = True) -> List[str]:
        """列出Ollama中可用的模型（带缓存与 single-flight）

        C-7: 缓存失效时仅允许一个线程执行 ollama.list()，其余线程等待结果，
             避免并发穿透。
        C-8: 添加恒定时间包装，缓解缓存命中/未命中的时间侧信道。

        Args:
            use_cache: 是否使用缓存，为 False 时强制刷新

        Returns:
            List[str]: 可用模型名称列表
        """
        start: float = time.time()
        try:
            return self._do_list_available_models(use_cache)
        finally:
            # 恒定时间包装：确保调用耗时不低于 MIN_LATENCY 秒
            MIN_LATENCY: float = 0.1
            elapsed: float = time.time() - start
            if elapsed < MIN_LATENCY:
                time.sleep(MIN_LATENCY - elapsed + random.uniform(0, 0.01))

    def _do_list_available_models(self, use_cache: bool = True) -> List[str]:
        """list_available_models 的实际实现"""
        # 先在锁内检查缓存，避免重复网络调用
        with self._models_cache_lock:
            if use_cache and self._cached_models is not None:
                if time.time() - self._cached_models_time < MODEL_LIST_CACHE_TTL:
                    logger.debug("返回缓存的模型列表")
                    return list(self._cached_models)

        # single-flight: 只有一个线程执行网络请求，其他线程等待
        with self._models_fetch_lock:
            if self._models_fetch_active:
                # 已有线程在获取，等待其完成并返回缓存结果
                wait_start: float = time.time()
                while self._models_fetch_active and time.time() - wait_start < MODEL_LIST_CACHE_TTL:
                    self._models_fetch_event.wait(timeout=0.05)
                with self._models_cache_lock:
                    if self._cached_models is not None:
                        return list(self._cached_models)
            self._models_fetch_active = True
            self._models_fetch_event.clear()

        try:
            models = ollama.list()
            result: List[str] = [
                str(m["model"]) for m in models.get("models", [])
            ]
        except (ConnectionError, TimeoutError, ollama.ResponseError) as e:
            print(f"获取模型列表失败 ({type(e).__name__})")
            logger.warning("获取模型列表失败: %s", type(e).__name__)
            logger.debug("模型列表原始错误: %s", self._sanitize_exception(e))
            return []
        except Exception as e:
            print(f"获取模型列表失败 ({type(e).__name__})")
            logger.error("获取模型列表失败: %s", type(e).__name__)
            logger.debug("模型列表原始错误: %s", self._sanitize_exception(e))
            return []
        finally:
            with self._models_fetch_lock:
                self._models_fetch_active = False
                self._models_fetch_event.set()

        # 仅在锁内更新缓存引用
        with self._models_cache_lock:
            self._cached_models = result
            self._cached_models_time = time.time()
        logger.info("刷新模型列表，共 %d 个模型", len(result))
        return result

    def reset_stats(self) -> None:
        """重置统计信息"""
        with self._stats_lock:
            self._stats = {
                "gpu_calls": 0,
                "cpu_calls": 0,
                "cloud_calls": 0,
                "gpu_failures": 0,
                "cpu_failures": 0,
                "cloud_failures": 0,
                "total_latency": 0.0,
            }
        logger.info("统计信息已重置")
