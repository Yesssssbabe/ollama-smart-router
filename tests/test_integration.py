# test_integration.py — 集成测试
import dataclasses
import pytest
from unittest.mock import Mock, patch

from src.router import SmartRouter, RouterConfig, RoutingStrategy, InferenceResult
from src.complexity_analyzer import ComplexityAnalyzer, TaskComplexity, TaskAnalysis
from src.gpu_monitor import GPUMemoryInfo


class TestEndToEnd:
    """端到端集成测试（Mock 所有外部依赖）"""

    @pytest.fixture
    def mock_ollama_response(self):
        return {
            'message': {'content': 'Mock response from Ollama'},
            'prompt_eval_count': 5,
            'eval_count': 15
        }

    @pytest.fixture
    def full_router(self, mock_ollama_response):
        """完全隔离的 router，所有外部调用已 Mock"""
        config = RouterConfig(cloud_api_key="test-key")
        router = SmartRouter(config)
        
        # Mock GPU（充足显存）
        router.gpu_monitor = Mock()
        router.gpu_monitor.get_free_vram_gb.return_value = 6.0
        router.gpu_monitor.get_gpu_memory.return_value = Mock(
            total_gb=8.0, used_gb=2.0, free_gb=6.0, utilization_percent=30.0
        )
        router.gpu_monitor.can_fit_model.return_value = True
        
        # Mock CPU（充足内存）
        router.cpu_monitor = Mock()
        router.cpu_monitor.get_memory_info.return_value = {
            "total_gb": 32.0, "available_gb": 20.0, "percent_used": 30.0
        }
        
        # Mock 云端客户端
        mock_client = Mock()
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "Mock cloud response"
        mock_response.choices = [mock_choice]
        mock_response.usage = Mock(total_tokens=25)
        mock_client.chat.completions.create.return_value = mock_response
        router._cloud_client = mock_client
        
        return router

    def test_simple_task_auto_routes_to_gpu(self, full_router, mock_ollama_response):
        """简单任务自动路由到 GPU"""
        with patch('ollama.chat', return_value=mock_ollama_response) as mock_chat:
            result = full_router.route("你好")
        
        assert result.source == "local_gpu"
        assert result.tokens == 20
        mock_chat.assert_called_once()
        # 验证使用的是小模型
        assert mock_chat.call_args[1]['model'] == full_router.config.small_model

    def test_complex_task_auto_routes_to_cloud(self, full_router):
        """复杂任务自动路由到云端"""
        result = full_router.route("设计一个支持百万并发的分布式系统架构")
        
        assert result.source == "cloud"
        assert result.content == "Mock cloud response"
        full_router._cloud_client.chat.completions.create.assert_called_once()

    def test_full_workflow_with_stats(self, full_router, mock_ollama_response):
        """完整工作流：多次调用 + 统计验证"""
        with patch('ollama.chat', return_value=mock_ollama_response):
            # 3 个简单任务
            full_router.route("你好")
            full_router.route("翻译 Hello")
            full_router.route("天气如何")
            
            # 1 个复杂任务（显式指定复杂度，避免分析器误判为 medium）
            full_router.route("设计系统架构", complexity="complex")

        stats = full_router._stats
        assert stats["gpu_calls"] == 3
        assert stats["cloud_calls"] == 1
        assert stats["cpu_calls"] == 0
        assert stats["total_latency"] > 0

    def test_degradation_chain_gpu_to_cpu_to_cloud(self, full_router, mock_ollama_response):
        """降级链：GPU → CPU → Cloud（GPU失败，CPU失败，Cloud成功）"""
        full_router.config = dataclasses.replace(full_router.config, auto_fallback=True)
        full_router.config = dataclasses.replace(full_router.config, max_fallback_attempts=3)
        
        oom_error = Exception("CUDA out of memory")
        cpu_error = Exception("CPU inference failed")
        
        with patch('ollama.chat', side_effect=[
            oom_error,      # GPU 失败
            cpu_error       # CPU 失败
        ]) as mock_chat:
            result = full_router.route("写个快速排序", strategy=RoutingStrategy.LOCAL_GPU)
        
        assert result.source == "cloud"  # 最终 fallback 到云端

    def test_degradation_chain_max_depth(self, full_router):
        """降级链：GPU → CPU → 失败（达到最大降级次数）"""
        full_router.config = dataclasses.replace(full_router.config, max_fallback_attempts=1)
        full_router.config = dataclasses.replace(full_router.config, auto_fallback=True)
        
        oom_error = Exception("CUDA out of memory")
        
        with patch('ollama.chat', side_effect=oom_error):
            with patch.object(full_router._cloud_client, 'chat.completions.create', side_effect=Exception("Cloud fail")):
                with pytest.raises(RuntimeError, match="最大降级次数"):
                    full_router.route("test", strategy=RoutingStrategy.LOCAL_GPU)

    def test_complex_task_no_cloud_fallback_to_cpu(self, mock_ollama_response):
        """复杂任务无云端 fallback 到 CPU"""
        config = RouterConfig(
            cloud_api_key=None,
            prefer_cloud_for_complex=True,
            auto_fallback=True,
        )
        router = SmartRouter(config)
        
        router.gpu_monitor = Mock()
        router.gpu_monitor.get_free_vram_gb.return_value = 6.0
        router.cpu_monitor = Mock()
        router.cpu_monitor.get_memory_info.return_value = {
            "total_gb": 32.0, "available_gb": 20.0, "percent_used": 30.0
        }
        
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = router.route("设计一个复杂系统")
        
        assert result.source == "local_cpu"

    def test_interactive_mode_full_session(self, full_router, mock_ollama_response):
        """交互模式完整会话（多轮对话）"""
        # 控制复杂度分析结果，确保前两个简单、最后一个复杂
        def fake_analyze(prompt):
            if "复杂" in prompt:
                return TaskAnalysis(
                    complexity=TaskComplexity.COMPLEX,
                    confidence=0.9,
                    estimated_tokens=100,
                    requires_code=False,
                    requires_reasoning=True,
                )
            return TaskAnalysis(
                complexity=TaskComplexity.SIMPLE,
                confidence=0.8,
                estimated_tokens=5,
                requires_code=False,
                requires_reasoning=False,
            )

        with patch('ollama.chat', return_value=mock_ollama_response):
            with patch.object(full_router.analyzer, 'analyze', side_effect=fake_analyze):
                with patch('builtins.input', side_effect=[
                    "你好",
                    "/stats",
                    "写个代码",
                    "/status",
                    "复杂架构设计",
                    "/quit"
                ]) as mock_input:
                    from src.cli import interactive_mode
                    interactive_mode(full_router)

        stats = full_router._stats
        # "你好" + "写个代码" 应该走 GPU，"复杂架构设计" 走云端
        assert stats["gpu_calls"] >= 2
        assert stats["cloud_calls"] >= 1

    def test_all_strategies(self, full_router, mock_ollama_response):
        """测试所有策略"""
        with patch('ollama.chat', return_value=mock_ollama_response):
            gpu_result = full_router.route("test", strategy=RoutingStrategy.LOCAL_GPU)
            cpu_result = full_router.route("test", strategy=RoutingStrategy.LOCAL_CPU)
        
        cloud_result = full_router.route("test", strategy=RoutingStrategy.CLOUD)
        
        assert gpu_result.source == "local_gpu"
        assert cpu_result.source == "local_cpu"
        assert cloud_result.source == "cloud"

    def test_cloud_failure_fallback_to_cpu(self, full_router, mock_ollama_response):
        """云端失败 fallback 到 CPU"""
        full_router._cloud_client.chat.completions.create.side_effect = Exception("API timeout")
        
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = full_router.route("复杂任务", strategy=RoutingStrategy.CLOUD)
        
        assert result.source == "local_cpu"

    def test_no_resources_available(self, full_router):
        """所有资源耗尽"""
        full_router.config = dataclasses.replace(full_router.config, cloud_api_key=None)
        full_router.config = dataclasses.replace(full_router.config, prefer_cloud_for_complex=True)
        full_router.gpu_monitor.get_free_vram_gb.return_value = 0.5
        full_router.cpu_monitor.get_memory_info.return_value = {
            "total_gb": 32.0, "available_gb": 0.5, "percent_used": 99.0
        }

        with pytest.raises(RuntimeError, match="资源不足"):
            full_router.route("复杂任务", complexity="complex")

    def test_concurrent_routing(self, full_router, mock_ollama_response):
        """并发路由线程安全"""
        import concurrent.futures
        
        with patch('ollama.chat', return_value=mock_ollama_response):
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(full_router.route, "你好") for _ in range(10)]
                results = [f.result() for f in futures]
        
        stats = full_router._stats
        assert stats["gpu_calls"] == 10
        assert all(r.source == "local_gpu" for r in results)

    def test_input_validation_integration(self, full_router):
        """输入验证集成"""
        # None 输入
        with pytest.raises(ValueError, match="不能为 None"):
            full_router.route(None)
        
        # 空字符串
        with pytest.raises(ValueError, match="不能为空"):
            full_router.route("   ")
        
        # 超长输入
        with pytest.raises(ValueError, match="过长"):
            full_router.route("x" * 200001)
        
        # 无效 complexity
        with pytest.raises(ValueError, match="complexity"):
            full_router.route("hello", complexity="invalid")

    def test_cloud_with_empty_choices_fallback(self, full_router, mock_ollama_response):
        """云端返回空 choices，fallback 到 CPU"""
        mock_response = Mock()
        mock_response.choices = []
        full_router._cloud_client.chat.completions.create.return_value = mock_response
        full_router.config = dataclasses.replace(full_router.config, auto_fallback=True)
        
        with patch('ollama.chat', return_value=mock_ollama_response):
            result = full_router.route("test", strategy=RoutingStrategy.CLOUD)
        
        assert result.source == "local_cpu"

    def test_context_manager_integration(self, mock_ollama_response):
        """上下文管理器集成"""
        with SmartRouter(RouterConfig()) as router:
            router.gpu_monitor = Mock()
            router.gpu_monitor.get_free_vram_gb.return_value = 6.0
            router.cpu_monitor = Mock()
            router.cpu_monitor.get_memory_info.return_value = {
                "total_gb": 32.0, "available_gb": 20.0, "percent_used": 30.0
            }
            
            with patch('ollama.chat', return_value=mock_ollama_response):
                result = router.route("hello")
            
            assert result.source == "local_gpu"
        # 退出后资源已释放
        assert router._is_closed
        assert router._executor is None
