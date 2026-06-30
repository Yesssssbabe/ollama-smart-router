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

作者: Principal_Engineer_Core
日期: 2026-06-30
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Union

import ollama

from .complexity_analyzer import ComplexityAnalyzer, TaskComplexity
from .gpu_monitor import CPUMonitor, GPUMonitor

logger = logging.getLogger(__name__)

# 常量定义
MAX_PROMPT_LENGTH: int = 200_000  # 约 200K 字符上限
MODEL_LIST_CACHE_TTL: float = 30.0  # 模型列表缓存有效期（秒）
VALID_COMPLEXITY_VALUES: set[str] = {"simple", "medium", "complex"}


class RoutingStrategy(Enum):
    """路由策略枚举"""
    AUTO = "auto"           # 自动选择
    LOCAL_GPU = "gpu"       # 强制本地GPU
    LOCAL_CPU = "cpu"       # 强制本地CPU
    CLOUD = "cloud"         # 强制云端


@dataclass
class RouterConfig:
    """路由器配置

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

    def __post_init__(self) -> None:
        """配置值验证"""
        if self.gpu_vram_threshold < 0:
            raise ValueError(
                f"gpu_vram_threshold 不能为负数: {self.gpu_vram_threshold}"
            )
        for name in ("small_model_vram", "medium_model_vram", "large_model_vram"):
            val: float = getattr(self, name)
            if val < 0:
                raise ValueError(f"{name} 不能为负数: {val}")
        if self.local_timeout <= 0:
            raise ValueError(f"local_timeout 必须大于 0: {self.local_timeout}")
        if self.cloud_timeout <= 0:
            raise ValueError(f"cloud_timeout 必须大于 0: {self.cloud_timeout}")
        if self.num_ctx <= 0:
            raise ValueError(f"num_ctx 必须大于 0: {self.num_ctx}")
        if self.max_fallback_attempts < 0:
            raise ValueError(
                f"max_fallback_attempts 不能为负数: {self.max_fallback_attempts}"
            )
        if self.safety_margin_gb < 0:
            raise ValueError(
                f"safety_margin_gb 不能为负数: {self.safety_margin_gb}"
            )


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

    def __init__(self, config: Optional[RouterConfig] = None) -> None:
        """初始化智能路由器

        Args:
            config: 路由器配置，为 None 时使用默认配置
        """
        self.config: RouterConfig = config or RouterConfig()
        self.gpu_monitor: GPUMonitor = GPUMonitor()
        self.cpu_monitor: CPUMonitor = CPUMonitor()
        self.analyzer: ComplexityAnalyzer = ComplexityAnalyzer()

        # 统计信息 — 使用线程安全的方式管理
        self._stats_lock: threading.Lock = threading.Lock()
        self._stats: Dict[str, Union[int, float]] = {
            "gpu_calls": 0,
            "cpu_calls": 0,
            "cloud_calls": 0,
            "total_latency": 0.0,
        }

        # 云端客户端延迟初始化 — 使用双重检查锁定保证线程安全
        self._cloud_lock: threading.Lock = threading.Lock()
        self._cloud_client: Optional[Any] = None

        # 模型列表缓存
        self._cached_models: Optional[List[str]] = None
        self._cached_models_time: float = 0.0
        self._models_cache_lock: threading.Lock = threading.Lock()

        # 线程池（用于 ollama.chat 超时控制）
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="ollama_router"
        )

        logger.debug("SmartRouter 初始化完成")

    def __enter__(self) -> SmartRouter:
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[BaseException],
                 exc_tb: Optional[Any]) -> None:
        """上下文管理器出口 — 确保资源释放"""
        self.close()

    def __del__(self) -> None:
        """析构时尝试关闭资源"""
        try:
            self.close()
        except Exception:
            pass

    def close(self) -> None:
        """关闭所有资源（云端客户端、线程池等）"""
        with self._cloud_lock:
            self._cloud_client = None
        if hasattr(self, "_executor") and self._executor is not None:
            self._executor.shutdown(wait=False)
            logger.debug("线程池已关闭")

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
        start_time: float = time.time()

        # 1. 输入验证
        self._validate_prompt(prompt)
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
            result = self._auto_route(prompt, complexity_str)

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
    def _validate_prompt(prompt: Any) -> None:
        """验证 prompt 参数合法性

        Raises:
            ValueError: prompt 为 None、空字符串或超长
            TypeError: prompt 类型不是 str
        """
        if prompt is None:
            raise ValueError("prompt 不能为 None")
        if not isinstance(prompt, str):
            raise TypeError(
                f"prompt 必须是字符串类型，实际为 {type(prompt).__name__}"
            )
        stripped = prompt.strip()
        if len(stripped) == 0:
            raise ValueError("prompt 不能为空或仅包含空白字符")
        if len(stripped) > MAX_PROMPT_LENGTH:
            raise ValueError(
                f"prompt 过长 ({len(stripped)} 字符)，超过最大限制 {MAX_PROMPT_LENGTH}。"
                f"请考虑拆分任务或使用文件上传。"
            )

    @staticmethod
    def _validate_complexity(complexity: str) -> None:
        """验证 complexity 参数合法性

        Raises:
            ValueError: complexity 不在允许的取值范围内
        """
        if complexity not in VALID_COMPLEXITY_VALUES:
            raise ValueError(
                f"complexity 必须是 'simple'/'medium'/'complex' 之一，"
                f"实际为 '{complexity}'"
            )

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
                f"Ollama响应应为字典类型，实际为 {type(response).__name__}"
            )
        message = response.get("message")
        if message is None:
            available_keys = list(response.keys())
            raise KeyError(
                f"Ollama响应缺少'message'字段，可用键: {available_keys}"
            )
        if not isinstance(message, dict):
            raise TypeError(
                f"Ollama响应'message'应为字典，实际为 {type(message).__name__}"
            )
        content = message.get("content")
        if content is None:
            raise KeyError("Ollama响应'message'中缺少'content'字段")
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
            logger.warning("无法从Ollama响应中提取token数量: %s", response)
            return 0

    # -----------------------------------------------------------------------
    # 内部方法 — 云端客户端
    # -----------------------------------------------------------------------

    def _get_cloud_client(self) -> Optional[Any]:
        """延迟初始化云端客户端（线程安全）

        Returns:
            Optional[Any]: OpenAI 客户端实例，未配置密钥时返回 None
        """
        if self._cloud_client is None and self.config.cloud_api_key:
            with self._cloud_lock:
                # 双重检查锁定
                if self._cloud_client is None:
                    try:
                        import openai
                        self._cloud_client = openai.OpenAI(
                            api_key=self.config.cloud_api_key,
                            base_url=self.config.cloud_base_url,
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
                        # 不打印原始异常信息，避免泄露敏感内容
        return self._cloud_client

    # -----------------------------------------------------------------------
    # 内部方法 — 自动路由决策
    # -----------------------------------------------------------------------

    def _auto_route(self, prompt: str, complexity: str) -> InferenceResult:
        """自动路由决策

        Args:
            prompt: 用户输入
            complexity: 复杂度等级 ("simple", "medium", "complex")

        Returns:
            InferenceResult: 推理结果
        """
        gpu_mem: float = self.gpu_monitor.get_free_vram_gb()
        print(f"🎮 当前GPU空闲显存: {gpu_mem:.1f}GB")

        cpu_mem: Dict[str, float] = self.cpu_monitor.get_memory_info()
        print(f"💻 系统内存: {cpu_mem['available_gb']:.1f}GB 可用")

        margin: float = self.config.safety_margin_gb

        # 路由决策逻辑
        if complexity == "simple":
            # 简单任务：优先GPU小模型
            if gpu_mem >= self.config.small_model_vram + margin:
                return self._run_local_gpu(prompt, self.config.small_model)
            else:
                return self._run_local_cpu(prompt, self.config.small_model)

        elif complexity == "medium":
            # 中等任务：GPU显存够就用GPU，否则CPU跑7B
            if gpu_mem >= self.config.medium_model_vram + margin:
                return self._run_local_gpu(prompt, self.config.medium_model)
            elif cpu_mem["available_gb"] >= 4.0:  # CPU需要至少4GB内存
                return self._run_local_cpu(prompt, self.config.medium_model)
            else:
                return self._run_cloud(prompt)

        else:  # complex
            # 复杂任务：优先云端API
            if self.config.cloud_api_key and self.config.prefer_cloud_for_complex:
                return self._run_cloud(prompt)
            elif cpu_mem["available_gb"] >= self.config.large_model_vram + margin:
                return self._run_local_cpu(prompt, self.config.large_model)
            elif cpu_mem["available_gb"] >= self.config.medium_model_vram + margin:
                return self._run_local_cpu(prompt, self.config.medium_model)
            elif gpu_mem >= self.config.small_model_vram + margin:
                return self._run_local_gpu(prompt, self.config.small_model)
            else:
                # 最后尝试云端，即使没有配置密钥也可能有公网模型
                if self.config.cloud_api_key:
                    return self._run_cloud(prompt)
                raise RuntimeError(
                    "资源不足，无法处理复杂任务。"
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
        if fallback_depth >= self.config.max_fallback_attempts:
            raise RuntimeError(
                f"所有推理路径均失败，已达最大降级次数"
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
            if "out of memory" in error_msg or "oom" in error_msg or "cuda" in error_msg:
                print("⚠️  GPU显存不足，自动切换到CPU...")
                logger.warning("GPU显存不足 (%s)，降级到CPU", error_type)
            else:
                print(f"⚠️  GPU推理失败 ({error_type})，尝试CPU...")
                logger.warning("GPU推理失败: %s", error_type)
            logger.debug("GPU原始错误详情: %s", e)

            fallback_model = self._choose_cpu_fallback_model(model)
            return self._run_local_cpu(
                prompt, fallback_model, fallback_depth=fallback_depth + 1
            )
        except Exception as e:
            error_type = type(e).__name__
            print(f"⚠️  GPU未知错误 ({error_type})，尝试CPU...")
            logger.error("GPU未知错误: %s", error_type)
            logger.debug("GPU原始错误详情: %s", e)

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
        if fallback_depth >= self.config.max_fallback_attempts:
            raise RuntimeError(
                f"所有推理路径均失败，已达最大降级次数"
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
                    "num_thread": 0,   # 使用所有线程
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
            if "model" in error_msg and (
                "not found" in error_msg or "not exist" in error_msg
            ):
                print(f"\n❌ 模型未找到: {model}")
                print(f"💡 请下载模型: ollama pull {model}")
                raise RuntimeError(
                    f"模型 {model} 未下载。运行: ollama pull {model}"
                ) from e
            print(f"❌ CPU推理失败 (Ollama错误)")
            logger.error("CPU Ollama错误: %s", type(e).__name__)
            logger.debug("CPU原始错误详情: %s", e)
            if self.config.cloud_api_key and self.config.auto_fallback:
                print("🔄 尝试云端API...")
                return self._run_cloud(prompt, fallback_depth=fallback_depth + 1)
            raise
        except (ConnectionError, TimeoutError) as e:
            print(f"❌ CPU连接失败 ({type(e).__name__})")
            logger.error("CPU连接失败: %s", type(e).__name__)
            logger.debug("CPU原始错误详情: %s", e)
            if self.config.cloud_api_key and self.config.auto_fallback:
                print("🔄 尝试云端API...")
                return self._run_cloud(prompt, fallback_depth=fallback_depth + 1)
            raise
        except Exception as e:
            print(f"❌ CPU推理失败 ({type(e).__name__})")
            logger.error("CPU推理失败: %s", type(e).__name__)
            logger.debug("CPU原始错误详情: %s", e)
            if self.config.cloud_api_key and self.config.auto_fallback:
                print("🔄 尝试云端API...")
                return self._run_cloud(prompt, fallback_depth=fallback_depth + 1)
            raise

    # -----------------------------------------------------------------------
    # 内部方法 — 云端 API 推理
    # -----------------------------------------------------------------------

    def _run_cloud(self, prompt: str, fallback_depth: int = 0) -> InferenceResult:
        """云端API推理

        Args:
            prompt: 用户输入
            fallback_depth: 当前降级深度，用于防止递归死循环

        Returns:
            InferenceResult: 推理结果

        Raises:
            RuntimeError: 降级次数超过限制、客户端未初始化或API返回空
        """
        if fallback_depth >= self.config.max_fallback_attempts:
            raise RuntimeError(
                f"所有推理路径均失败，已达最大降级次数"
                f"({self.config.max_fallback_attempts})"
            )

        print(f"☁️ [云端API] 使用: {self.config.cloud_model}")

        client = self._get_cloud_client()
        if not client:
            raise RuntimeError("云端客户端未初始化，请配置API密钥")

        start: float = time.time()
        try:
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
                raise RuntimeError("云端API返回空choices列表")

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
            logger.debug("云端原始错误详情: %s", e)
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
            logger.debug("云端原始错误详情: %s", e)
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
            logger.debug("云端原始错误详情: %s", e)
            with self._cloud_lock:
                self._cloud_client = None
            raise RuntimeError(
                "云端API密钥无效或已过期，请检查配置"
            ) from e
        except Exception as e:
            error_type = type(e).__name__
            print(f"❌ 云端API调用失败 ({error_type})，尝试本地模型...")
            logger.error("云端API未知错误: %s", error_type)
            logger.debug("云端原始错误详情: %s", e)
            with self._cloud_lock:
                self._cloud_client = None
            if not self.config.auto_fallback:
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

        使用 ThreadPoolExecutor 将 ollama.chat 包装在独立线程中，
        通过 future.result(timeout) 实现超时控制。

        Args:
            model: 模型名称
            messages: 消息列表
            options: Ollama 选项字典

        Returns:
            Any: ollama.chat 的响应对象

        Raises:
            TimeoutError: 调用超时
            Exception: ollama.chat 抛出的其他异常
        """
        timeout: int = self.config.local_timeout

        # Windows 不支持 signal.alarm，使用 ThreadPoolExecutor 方式
        future = self._executor.submit(
            ollama.chat,
            model=model,
            messages=messages,
            options=options,
        )
        try:
            return future.result(timeout=timeout)
        except Exception:
            # 取消任务（如果可能）
            future.cancel()
            raise

    # -----------------------------------------------------------------------
    # 内部方法 — 统计与模型列表
    # -----------------------------------------------------------------------

    def print_stats(self) -> None:
        """打印统计信息"""
        with self._stats_lock:
            total: int = (
                int(self._stats["gpu_calls"])
                + int(self._stats["cpu_calls"])
                + int(self._stats["cloud_calls"])
            )
            if total == 0:
                print("暂无统计信息")
                return

            gpu_calls: int = int(self._stats["gpu_calls"])
            cpu_calls: int = int(self._stats["cpu_calls"])
            cloud_calls: int = int(self._stats["cloud_calls"])
            total_latency: float = float(self._stats["total_latency"])

            print("\n📈 使用统计:")
            print(f"   GPU调用: {gpu_calls} ({gpu_calls / total:.0%})")
            print(f"   CPU调用: {cpu_calls} ({cpu_calls / total:.0%})")
            print(f"   云端调用: {cloud_calls} ({cloud_calls / total:.0%})")
            avg_latency: float = total_latency / max(1, total)
            print(f"   总耗时: {total_latency:.2f}s")
            print(f"   平均延迟: {avg_latency:.2f}s")

    def list_available_models(self, use_cache: bool = True) -> List[str]:
        """列出Ollama中可用的模型（带缓存）

        Args:
            use_cache: 是否使用缓存，为 False 时强制刷新

        Returns:
            List[str]: 可用模型名称列表
        """
        with self._models_cache_lock:
            if use_cache and self._cached_models is not None:
                if time.time() - self._cached_models_time < MODEL_LIST_CACHE_TTL:
                    logger.debug("返回缓存的模型列表")
                    return list(self._cached_models)

            try:
                models = ollama.list()
                result: List[str] = [
                    str(m["model"]) for m in models.get("models", [])
                ]
                self._cached_models = result
                self._cached_models_time = time.time()
                logger.info("刷新模型列表，共 %d 个模型", len(result))
                return result
            except (ConnectionError, TimeoutError, ollama.ResponseError) as e:
                print(f"获取模型列表失败 ({type(e).__name__})")
                logger.warning("获取模型列表失败: %s", type(e).__name__)
                logger.debug("模型列表原始错误: %s", e)
                return []
            except Exception as e:
                print(f"获取模型列表失败 ({type(e).__name__})")
                logger.error("获取模型列表失败: %s", type(e).__name__)
                logger.debug("模型列表原始错误: %s", e)
                return []

    def reset_stats(self) -> None:
        """重置统计信息"""
        with self._stats_lock:
            self._stats = {
                "gpu_calls": 0,
                "cpu_calls": 0,
                "cloud_calls": 0,
                "total_latency": 0.0,
            }
        logger.info("统计信息已重置")
