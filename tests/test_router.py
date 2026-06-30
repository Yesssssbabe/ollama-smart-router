# test_router.py — 核心路由测试
import dataclasses
import pytest
from unittest.mock import Mock, patch
import threading
import time
import ollama

from src.router import (
    SmartRouter, RouterConfig, RoutingStrategy, InferenceResult
)
from src.complexity_analyzer import TaskComplexity, TaskAnalysis


class TestSmartRouterRoute:
    """测试路由主入口"""

    def test_route_auto_simple_to_gpu(self, router, mock_ollama_response):
        """简单任务 + 充足 GPU 显存 → 路由到 GPU"""
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router.route("你好")
        
        assert isinstance(result, InferenceResult)
        assert result.source == "local_gpu"
        assert result.content == "Hello, this is a test response."
        assert result.tokens == 30  # 10 + 20

    def test_route_auto_simple_gpu_insufficient(
        self, default_config, mock_gpu_monitor_low, mock_cpu_monitor, mock_ollama_response
    ):
        """简单任务 + GPU 不足 → 降级到 CPU"""
        router = SmartRouter(default_config)
        router.gpu_monitor = mock_gpu_monitor_low
        router.cpu_monitor = mock_cpu_monitor
        
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router.route("你好")
        
        assert result.source == "local_cpu"

    def test_route_auto_medium(self, router, mock_ollama_response):
        """中等任务自动路由"""
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router.route("写个Python排序函数")
        
        assert isinstance(result, InferenceResult)
        assert result.source in ["local_gpu", "local_cpu"]

    def test_route_auto_complex(self, router, mock_openai_client):
        """复杂任务优先云端"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router.config = dataclasses.replace(router.config, prefer_cloud_for_complex=True)
        router._cloud_client = mock_openai_client

        # 固定分析器返回 complex，避免不同环境下启发式分析结果不一致
        with patch.object(
            router.analyzer,
            "analyze",
            return_value=TaskAnalysis(
                complexity=TaskComplexity.COMPLEX,
                confidence=0.9,
                estimated_tokens=100,
                requires_code=False,
                requires_reasoning=True,
            ),
        ):
            result = router.route("设计一个支持百万并发的分布式系统架构")

        assert result.source == "cloud"
        assert result.content == "Cloud response here."

    def test_route_strategy_override_local_cpu(self, router, mock_ollama_response):
        """强制 LOCAL_CPU 策略覆盖自动路由"""
        with patch('ollama.chat', return_value=mock_ollama_response) as mock_chat:
            result = router.route(
                "设计一个分布式系统", 
                strategy=RoutingStrategy.LOCAL_CPU
            )
        
        assert result.source == "local_cpu"
        # 验证调用参数中 num_gpu=0
        call_kwargs = mock_chat.call_args[1]['options']
        assert call_kwargs['num_gpu'] == 0

    def test_route_strategy_override_local_gpu(self, router, mock_ollama_response):
        """强制 LOCAL_GPU 策略"""
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router.route("任意内容", strategy=RoutingStrategy.LOCAL_GPU)
        
        assert result.source == "local_gpu"

    def test_route_strategy_override_cloud(self, router, mock_openai_client):
        """强制 CLOUD 策略"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router._cloud_client = mock_openai_client
        
        result = router.route("任意内容", strategy=RoutingStrategy.CLOUD)
        
        assert result.source == "cloud"

    def test_route_manual_complexity(self, router, mock_ollama_response):
        """手动指定复杂度，跳过分析器"""
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router.route("任意内容", complexity="simple")
        
        assert result.source == "local_gpu"

    def test_route_stats_accumulation(self, router, mock_ollama_response):
        """多次调用后统计正确累加"""
        with patch('ollama.chat', return_value=mock_ollama_response):
            router.route("你好")
            router.route("写代码")
        
        stats = router._stats
        assert stats["gpu_calls"] == 2
        assert stats["total_latency"] > 0

    def test_route_none_input(self, router):
        """None 输入抛出 ValueError"""
        with pytest.raises(ValueError, match="不能为 None"):
            router.route(None)

    def test_route_empty_string(self, router):
        """空字符串输入抛出 ValueError"""
        with pytest.raises(ValueError, match="不能为空"):
            router.route("   ")

    def test_route_super_long_input(self, router):
        """超长输入抛出 ValueError"""
        with pytest.raises(ValueError, match="过长"):
            router.route("x" * 200001)

    def test_route_invalid_complexity(self, router):
        """无效 complexity 参数抛出 ValueError"""
        with pytest.raises(ValueError, match="complexity"):
            router.route("hello", complexity="invalid")

    def test_route_non_string_input(self, router):
        """非字符串输入抛出 TypeError"""
        with pytest.raises(TypeError, match="字符串"):
            router.route(12345)

    def test_route_valid_long_input(self, router, mock_ollama_response):
        """接近上限但合法的输入应通过"""
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router.route("x" * 200000)
        assert result is not None

    def test_route_with_context_manager(self, default_config, mock_ollama_response):
        """上下文管理器支持"""
        with SmartRouter(default_config) as router:
            router.gpu_monitor = Mock()
            router.gpu_monitor.get_free_vram_gb.return_value = 6.0
            router.cpu_monitor = Mock()
            router.cpu_monitor.get_memory_info.return_value = {
                "total_gb": 32.0, "available_gb": 20.0, "percent_used": 30.0
            }
            with patch('ollama.chat', return_value=mock_ollama_response):
                result = router.route("你好")
            assert result.source == "local_gpu"


class TestSmartRouterExecution:
    """测试各执行路径"""

    def test_run_local_gpu_success(self, router, mock_ollama_response):
        """GPU 推理成功"""
        with patch('ollama.chat', return_value=mock_ollama_response) as mock_chat:
            result = router._run_local_gpu("test prompt")
        
        mock_chat.assert_called_once()
        assert result.source == "local_gpu"
        assert result.tokens == 30
        # 验证 GPU 参数
        options = mock_chat.call_args[1]['options']
        assert options['num_gpu'] == 99
        assert options['num_ctx'] == router.config.num_ctx

    def test_run_local_gpu_oom_fallback(self, router, mock_ollama_response):
        """GPU OOM 自动降级到 CPU"""
        oom_error = Exception("CUDA out of memory")
        
        with patch('ollama.chat', side_effect=[oom_error, mock_ollama_response]) as mock_chat:
            result = router._run_local_gpu("test")
        
        assert mock_chat.call_count == 2
        assert result.source == "local_cpu"

    def test_run_local_gpu_fallback_depth_limit(self, router):
        """GPU 降级深度限制"""
        router.config = dataclasses.replace(router.config, max_fallback_attempts=0)
        
        with pytest.raises(RuntimeError, match="最大降级次数"):
            router._run_local_gpu("test", fallback_depth=1)

    def test_run_local_cpu_model_not_found(self, router):
        """模型不存在时抛出 RuntimeError 并提示下载"""
        error = ollama.ResponseError("model 'qwen2.5:7b' not found, try pulling it")
        
        with patch('ollama.chat', side_effect=error):
            with pytest.raises(RuntimeError) as exc_info:
                router._run_local_cpu("test")
        
        assert "qwen2.5:7b" in str(exc_info.value)
        assert "ollama pull" in str(exc_info.value)

    def test_run_local_cpu_fallback_to_cloud(self, router, mock_openai_client):
        """CPU 失败且配置云端 key → fallback 到云端"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router.config = dataclasses.replace(router.config, auto_fallback=True)
        error = Exception("CPU inference failed")
        
        with patch('ollama.chat', side_effect=error):
            with patch.object(router, '_get_cloud_client', return_value=mock_openai_client):
                result = router._run_local_cpu("test")
        
        assert result.source == "cloud"

    def test_run_local_cpu_no_cloud_fallback(self, router):
        """CPU 失败但没有云端 key → 直接抛出"""
        router.config = dataclasses.replace(router.config, cloud_api_key=None)
        router.config = dataclasses.replace(router.config, auto_fallback=False)
        error = Exception("CPU inference failed")
        
        with patch('ollama.chat', side_effect=error):
            with pytest.raises(Exception, match="CPU inference failed"):
                router._run_local_cpu("test")

    def test_run_cloud_success(self, router, mock_openai_client):
        """云端推理成功"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router._cloud_client = mock_openai_client
        
        result = router._run_cloud("test prompt")
        
        assert result.source == "cloud"
        assert result.content == "Cloud response here."
        assert result.tokens == 30
        mock_openai_client.chat.completions.create.assert_called_once()

    def test_run_cloud_no_api_key(self, router):
        """未配置 API key 抛出 RuntimeError"""
        router.config = dataclasses.replace(router.config, cloud_api_key=None)
        router._cloud_client = None
        
        with pytest.raises(RuntimeError, match="云端客户端未初始化"):
            router._run_cloud("test")

    def test_run_cloud_failure_fallback(self, router, mock_ollama_response):
        """云端失败 fallback 到本地 CPU"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router.config = dataclasses.replace(router.config, auto_fallback=True)
        router._cloud_client = Mock()
        router._cloud_client.chat.completions.create.side_effect = Exception("API timeout")
        
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router._run_cloud("test")
        
        assert result.source == "local_cpu"

    def test_run_cloud_empty_choices(self, router, mock_openai_client):
        """云端返回空 choices 且禁用 fallback 时抛出 RuntimeError"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router.config = dataclasses.replace(router.config, auto_fallback=False)
        mock_response = Mock()
        mock_response.choices = []
        mock_openai_client.chat.completions.create.return_value = mock_response
        router._cloud_client = mock_openai_client

        with pytest.raises(RuntimeError, match="空choices"):
            router._run_cloud("test")

    def test_auto_route_complex_prefer_cloud(self, router, mock_openai_client):
        """复杂任务优先路由到云端"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router.config = dataclasses.replace(router.config, prefer_cloud_for_complex=True)
        router._cloud_client = mock_openai_client
        
        result = router._auto_route("写一篇学术论文", "complex")
        
        assert result.source == "cloud"

    def test_auto_route_complex_no_cloud_fallback_cpu(
        self, default_config, mock_gpu_monitor, mock_cpu_monitor, mock_ollama_response
    ):
        """复杂任务无云端 → fallback 到 CPU 大模型"""
        router = SmartRouter(default_config)
        router.config = dataclasses.replace(router.config, cloud_api_key=None)
        router.config = dataclasses.replace(router.config, prefer_cloud_for_complex=True)
        router.config = dataclasses.replace(router.config, auto_fallback=True)
        router.gpu_monitor = mock_gpu_monitor
        router.cpu_monitor = mock_cpu_monitor
        
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router._auto_route("复杂任务", "complex")
        
        assert result.source == "local_cpu"

    def test_auto_route_resource_exhaustion(self, router):
        """所有资源不足时抛出 RuntimeError"""
        router.config = dataclasses.replace(router.config, cloud_api_key=None)
        router.config = dataclasses.replace(router.config, prefer_cloud_for_complex=True)
        router.gpu_monitor.get_free_vram_gb.return_value = 0.5
        router.cpu_monitor.get_memory_info.return_value = {
            "total_gb": 32.0, "available_gb": 0.5, "percent_used": 99.0
        }
        
        with pytest.raises(RuntimeError, match="资源不足"):
            router._auto_route("非常复杂", "complex")

    def test_auto_route_simple_gpu_insufficient(self, default_config, mock_gpu_monitor_low, mock_cpu_monitor, mock_ollama_response):
        """简单任务 GPU 不足降级到 CPU"""
        router = SmartRouter(default_config)
        router.gpu_monitor = mock_gpu_monitor_low
        router.cpu_monitor = mock_cpu_monitor
        
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router._auto_route("hello", "simple")
        
        assert result.source == "local_cpu"

    def test_auto_route_medium_gpu_sufficient(self, router, mock_ollama_response):
        """中等任务 GPU 充足 → 使用 GPU"""
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router._auto_route("写个代码", "medium")
        
        assert result.source == "local_gpu"

    def test_extract_token_count(self, router):
        """提取 token 计数"""
        assert router._extract_token_count({
            'prompt_eval_count': 10, 'eval_count': 20
        }) == 30
        assert router._extract_token_count({
            'prompt_eval_count': None, 'eval_count': 5
        }) == 5
        assert router._extract_token_count("not a dict") == 0
        assert router._extract_token_count({}) == 0
        assert router._extract_token_count({
            'prompt_eval_count': 'invalid', 'eval_count': 5
        }) == 0

    def test_choose_cpu_fallback_model(self, router):
        """CPU 降级模型选择"""
        config = router.config
        assert router._choose_cpu_fallback_model(config.small_model) == config.small_model
        assert router._choose_cpu_fallback_model(config.medium_model) == config.medium_model
        assert router._choose_cpu_fallback_model(config.large_model) == config.medium_model
        assert router._choose_cpu_fallback_model("unknown") == config.medium_model

    def test_get_cloud_client_lazy_init(self, router):
        """延迟初始化只执行一次"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        
        with patch('builtins.__import__') as mock_import:
            # Mock openai module
            mock_openai = Mock()
            mock_import.side_effect = lambda name, *args, **kwargs: mock_openai if name == 'openai' else __import__(name, *args, **kwargs)
            client1 = router._get_cloud_client()
            client2 = router._get_cloud_client()
        
        assert client1 is client2

    def test_get_cloud_client_import_error(self, router, capsys):
        """未安装 openai 包时返回 None"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router._cloud_client = None
        
        with patch('builtins.__import__', side_effect=ImportError("No module named 'openai'")):
            client = router._get_cloud_client()
        
        assert client is None

    def test_list_available_models(self, router):
        """列出模型"""
        with patch('ollama.list', return_value={
            'models': [{'model': 'gemma3:4b'}, {'model': 'qwen2.5:7b'}]
        }) as mock_list:
            models = router.list_available_models(use_cache=False)
        
        assert models == ['gemma3:4b', 'qwen2.5:7b']
        mock_list.assert_called_once()

    def test_list_available_models_error(self, router):
        """获取模型列表失败返回空列表"""
        with patch('ollama.list', side_effect=Exception("connection refused")):
            models = router.list_available_models(use_cache=False)
        
        assert models == []

    def test_list_available_models_cache(self, router):
        """模型列表缓存"""
        with patch('ollama.list', return_value={
            'models': [{'model': 'gemma3:4b'}]
        }) as mock_list:
            models1 = router.list_available_models(use_cache=False)
            models2 = router.list_available_models(use_cache=True)
        
        assert models1 == models2 == ['gemma3:4b']
        mock_list.assert_called_once()  # 只调用一次，第二次使用缓存

    def test_print_stats(self, router, capsys):
        """打印统计信息"""
        router._stats = {"gpu_calls": 2, "cpu_calls": 1, "cloud_calls": 1, "total_latency": 3.5}
        router.print_stats()
        captured = capsys.readouterr()
        
        assert "GPU调用" in captured.out
        assert "50%" in captured.out  # 2/4
        assert "平均延迟" in captured.out

    def test_print_stats_empty(self, router, capsys):
        """无统计时安全退出"""
        router.print_stats()
        captured = capsys.readouterr()
        
        assert "暂无统计信息" in captured.out

    def test_reset_stats(self, router):
        """重置统计"""
        router._stats = {"gpu_calls": 5, "cpu_calls": 3, "cloud_calls": 2, "total_latency": 10.0}
        router.reset_stats()
        stats = router._stats
        assert stats["gpu_calls"] == 0
        assert stats["total_latency"] == 0.0

    def test_fallback_depth_limit(self, router):
        """降级深度限制防止递归死循环"""
        router.config = dataclasses.replace(router.config, max_fallback_attempts=0)
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router.config = dataclasses.replace(router.config, auto_fallback=True)
        
        # GPU 失败 → CPU（应触发限制）
        with patch('ollama.chat', side_effect=Exception("GPU fail")):
            with pytest.raises(RuntimeError, match="最大降级次数"):
                router._run_local_gpu("test")

    def test_safe_extract_ollama_content(self, router):
        """安全提取 Ollama 响应内容"""
        assert router._safe_extract_ollama_content({
            'message': {'content': 'hello'}
        }) == "hello"

    def test_safe_extract_ollama_content_missing_message(self, router):
        """缺少 message 字段"""
        with pytest.raises(KeyError):
            router._safe_extract_ollama_content({'other': 'value'})

    def test_safe_extract_ollama_content_not_dict(self, router):
        """非字典响应"""
        with pytest.raises(TypeError):
            router._safe_extract_ollama_content("not a dict")

    def test_safe_extract_ollama_content_missing_content(self, router):
        """message 中缺少 content"""
        with pytest.raises(KeyError):
            router._safe_extract_ollama_content({'message': {}})

    def test_stats_thread_safety(self, router):
        """统计信息线程安全"""
        def increment():
            with router._stats_lock:
                router._stats["gpu_calls"] = int(router._stats["gpu_calls"]) + 1
        
        threads = [threading.Thread(target=increment) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        stats = router._stats
        assert stats["gpu_calls"] == 100

    def test_validate_prompt(self, router):
        """_validate_prompt 静态方法"""
        router._validate_prompt("hello")
        with pytest.raises(ValueError, match="不能为 None"):
            router._validate_prompt(None)
        with pytest.raises(TypeError, match="字符串"):
            router._validate_prompt(123)

    def test_validate_complexity(self, router):
        """_validate_complexity 静态方法"""
        router._validate_complexity("simple")
        router._validate_complexity("medium")
        router._validate_complexity("complex")
        with pytest.raises(ValueError, match="complexity"):
            router._validate_complexity("invalid")

    def test_close(self, router):
        """资源释放"""
        router._cloud_client = Mock()
        router.close()
        assert router._cloud_client is None

    def test_context_manager(self, default_config):
        """上下文管理器"""
        with SmartRouter(default_config) as r:
            assert r is not None
        # 退出后资源已释放

    def test_choose_cpu_fallback_model_large(self, router):
        """大模型 GPU 失败降级到中等模型"""
        config = router.config
        assert router._choose_cpu_fallback_model(config.large_model) == config.medium_model

    def test_cloud_authentication_error(self, router, mock_openai_client):
        """云端认证失败"""
        import openai as oa
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        mock_openai_client.chat.completions.create.side_effect = oa.AuthenticationError(
            "Invalid key", response=Mock(), body=Mock()
        )
        router._cloud_client = mock_openai_client
        
        with pytest.raises(RuntimeError, match="密钥无效"):
            router._run_cloud("test")

    def test_cloud_rate_limit_error(self, router, mock_openai_client, mock_ollama_response):
        """云端限流 fallback 到 CPU"""
        import openai as oa
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router.config = dataclasses.replace(router.config, auto_fallback=True)
        mock_openai_client.chat.completions.create.side_effect = oa.RateLimitError(
            "Rate limited", response=Mock(), body=Mock()
        )
        router._cloud_client = mock_openai_client
        
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router._run_cloud("test")
        
        assert result.source == "local_cpu"

    def test_cloud_connection_error(self, router, mock_openai_client, mock_ollama_response):
        """云端连接失败 fallback 到 CPU"""
        import openai as oa
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        router.config = dataclasses.replace(router.config, auto_fallback=True)
        mock_openai_client.chat.completions.create.side_effect = oa.APIConnectionError(
            message="Connection failed",
            request=Mock(),
        )
        router._cloud_client = mock_openai_client
        
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router._run_cloud("test")
        
        assert result.source == "local_cpu"


class TestInferenceResult:
    """测试推理结果对象"""

    def test_init(self):
        result = InferenceResult("content", "local_gpu", 1.5, 100)
        assert result.content == "content"
        assert result.source == "local_gpu"
        assert result.latency == 1.5
        assert result.tokens == 100
        assert result.timestamp > 0

    def test_str_short(self):
        result = InferenceResult("short text", "cloud", 2.0)
        assert str(result) == "[cloud] short text"

    def test_str_long(self):
        text = "a" * 200
        result = InferenceResult(text, "cloud", 2.0)
        assert str(result).startswith("[cloud] " + "a" * 100 + "...")

    def test_str_exact_100(self):
        text = "a" * 100
        result = InferenceResult(text, "local_cpu", 1.0)
        assert str(result) == "[local_cpu] " + text

    def test_repr(self):
        result = InferenceResult("test", "gpu", 1.5, 10)
        repr_str = repr(result)
        assert "InferenceResult" in repr_str
        assert "gpu" in repr_str

    def test_post_init_type_conversion(self):
        """__post_init__ 类型转换"""
        result = InferenceResult(123, 456, "7.5", "10")
        assert result.content == "123"
        assert result.source == "456"
        assert result.latency == 7.5
        assert result.tokens == 10

    def test_post_init_timestamp(self):
        """默认时间戳"""
        before = time.time()
        result = InferenceResult("test", "gpu")
        after = time.time()
        assert before <= result.timestamp <= after


class TestRouterConfig:
    """测试路由器配置"""

    def test_default_config(self):
        config = RouterConfig()
        assert config.small_model == "gemma3:4b"
        assert config.gpu_vram_threshold == 4.0
        assert config.cloud_api_key is None
        assert config.num_ctx == 4096
        assert config.safety_margin_gb == 1.0

    def test_custom_config(self):
        config = RouterConfig(
            small_model="custom:4b",
            cloud_api_key="test-key",
            num_ctx=8192
        )
        assert config.small_model == "custom:4b"
        assert config.cloud_api_key == "test-key"
        assert config.num_ctx == 8192

    def test_post_init_negative_vram_threshold(self):
        """负数显存阈值"""
        with pytest.raises(ValueError, match="负数"):
            RouterConfig(gpu_vram_threshold=-1.0)

    def test_post_init_negative_model_vram(self):
        """负数模型显存"""
        with pytest.raises(ValueError, match="负数"):
            RouterConfig(small_model_vram=-1.0)

    def test_post_init_negative_fallback_attempts(self):
        """负数降级次数"""
        with pytest.raises(ValueError, match="负数"):
            RouterConfig(max_fallback_attempts=-1)

    def test_post_init_negative_safety_margin(self):
        """负数安全余量"""
        with pytest.raises(ValueError, match="负数"):
            RouterConfig(safety_margin_gb=-1.0)

    def test_post_init_zero_local_timeout(self):
        """local_timeout 为 0"""
        with pytest.raises(ValueError, match="必须大于 0"):
            RouterConfig(local_timeout=0)

    def test_post_init_zero_cloud_timeout(self):
        """cloud_timeout 为 0"""
        with pytest.raises(ValueError, match="必须大于 0"):
            RouterConfig(cloud_timeout=0)

    def test_post_init_zero_num_ctx(self):
        """num_ctx 为 0"""
        with pytest.raises(ValueError, match="必须大于 0"):
            RouterConfig(num_ctx=0)

    def test_config_immutable(self):
        """配置不可变（frozen dataclass）"""
        config = RouterConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.small_model = "changed"

    def test_config_default_max_fallback(self):
        config = RouterConfig()
        assert config.max_fallback_attempts == 2

    def test_eq_same_config(self):
        """相同配置相等"""
        c1 = RouterConfig()
        c2 = RouterConfig()
        assert c1 == c2

    def test_eq_different_config(self):
        """不同配置不相等"""
        c1 = RouterConfig()
        c2 = RouterConfig(small_model="different")
        assert c1 != c2


class TestRouterConfigSecurity:
    """配置安全相关测试"""

    def test_repr_redacts_api_key(self):
        """RouterConfig.__repr__ 不应泄露 API 密钥"""
        config = RouterConfig(cloud_api_key="sk-abcdef123456")
        repr_str = repr(config)
        assert "sk-abcdef123456" not in repr_str
        assert "***REDACTED***" in repr_str

    def test_nan_infinity_rejected(self):
        """NaN / Infinity 配置值被拒绝"""
        import math
        with pytest.raises(ValueError, match="NaN"):
            RouterConfig(gpu_vram_threshold=float("nan"))
        with pytest.raises(ValueError, match="Infinity"):
            RouterConfig(local_timeout=float("inf"))

    def test_invalid_model_name_rejected(self):
        """非法模型名在 __post_init__ 被拒绝"""
        with pytest.raises(ValueError, match="格式不合法"):
            RouterConfig(small_model="../evil")

    def test_cloud_base_url_must_be_http_or_https(self):
        """cloud_base_url 必须带协议头"""
        with pytest.raises(ValueError, match="http"):
            RouterConfig(cloud_base_url="ftp://example.com")


class TestSmartRouterSecurity:
    """路由安全相关测试"""

    def test_sanitize_exception_masks_api_key(self, router):
        """异常消息脱敏会隐藏 sk- 密钥"""
        exc = Exception("request failed with Authorization: Bearer sk-abc123XYZ")
        sanitized = router._sanitize_exception(exc)
        assert "sk-abc123XYZ" not in sanitized
        assert "sk-***" in sanitized

    def test_memory_error_not_fallback(self, router):
        """MemoryError 不应被降级处理"""
        with patch('ollama.chat', side_effect=MemoryError("out of memory")):
            with pytest.raises(RuntimeError, match="内存不足"):
                router._run_local_gpu("test")

    def test_safe_extract_message_not_dict(self, router):
        """message 非字典时抛出 TypeError"""
        with pytest.raises(TypeError):
            router._safe_extract_ollama_content({"message": "not a dict"})

    def test_get_cloud_client_init_exception_returns_none(self, router, caplog):
        """OpenAI 初始化异常时返回 None"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        with patch('openai.OpenAI', side_effect=RuntimeError("init failed")):
            client = router._get_cloud_client()
        assert client is None

    def test_get_cloud_client_thread_safe_singleton(self, router):
        """双重检查锁保证只创建一个云端客户端"""
        router.config = dataclasses.replace(router.config, cloud_api_key="test-key")
        clients = []
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()
            clients.append(router._get_cloud_client())

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(c is clients[0] for c in clients)


class TestOllamaTimeout:
    """ollama 超时包装测试（C-2: 基于 multiprocessing.Process）"""

    def test_timeout_success(self, router, mock_ollama_response):
        with patch('ollama.chat', return_value=mock_ollama_response) as mock_chat:
            result = router._ollama_chat_with_timeout(
                model="gemma3:4b",
                messages=[{"role": "user", "content": "hi"}],
                options={}
            )
        assert result == mock_ollama_response
        mock_chat.assert_called_once()

    def test_timeout_expired_terminates_process(self, router):
        """超时后应强制终止子进程，避免线程泄漏"""
        router.config = dataclasses.replace(router.config, local_timeout=0.1)

        mock_process = Mock()
        mock_process.is_alive.return_value = True
        mock_queue = Mock()
        mock_queue.empty.return_value = True

        with patch('src.router.Process', return_value=mock_process) as mock_process_class:
            with patch('src.router.Queue', return_value=mock_queue):
                with pytest.raises(TimeoutError):
                    router._ollama_chat_with_timeout(
                        model="gemma3:4b",
                        messages=[{"role": "user", "content": "hi"}],
                        options={}
                    )

        mock_process_class.assert_called_once()
        mock_process.start.assert_called_once()
        mock_process.terminate.assert_called_once()

    def test_timeout_propagates_exception(self, router):
        err = ollama.ResponseError("model not found")
        with patch('ollama.chat', side_effect=err):
            with pytest.raises(ollama.ResponseError):
                router._ollama_chat_with_timeout(
                    model="gemma3:4b",
                    messages=[{"role": "user", "content": "hi"}],
                    options={}
                )
