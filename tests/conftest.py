# 共享 Fixtures
import sys
import os
import pytest
from unittest.mock import Mock, patch
import openai as oa_module

# 确保 src 在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import queue as _queue

from src.router import SmartRouter, RouterConfig, RoutingStrategy, InferenceResult
from src.gpu_monitor import GPUMonitor, CPUMonitor, GPUMemoryInfo
from src.complexity_analyzer import ComplexityAnalyzer, TaskComplexity

# 修复：在 src.router 模块注入 openai，因为 _run_cloud 的 except 块直接使用 openai.xxx
# 但 openai 只在 _get_cloud_client 中局部导入
import src.router as router_mod
router_mod.openai = oa_module


@pytest.fixture(autouse=True)
def mock_multiprocessing_process():
    """自动 mock multiprocessing.Process，使现有 ollama.chat patch 在子进程模式下继续生效。

    C-2 将 _ollama_chat_with_timeout 改为基于 multiprocessing.Process 的实现。
    测试中原先对 ollama.chat 的 patch 无法跨进程生效，因此通过此 fixture 让 Process
    在启动时直接在当前进程调用工作函数，从而复用所有已存在的 chat mock。
    """
    # router.py 在模块顶部执行了 `from multiprocessing import Process, Queue`，
    # 因此必须 patch src.router 中的绑定名，才能真正替换路由代码里的 Process/Queue。
    with patch('src.router.Process') as mock_process_class, \
         patch('src.router.Queue') as mock_queue_class:

        result_queue = _queue.Queue()
        mock_queue_class.return_value = result_queue

        def make_process(*args, **kwargs):
            p = Mock()
            p.is_alive.return_value = False

            target = kwargs.get('target')
            worker_args = kwargs.get('args', ())
            if target is None and args:
                target = args[0]
            if not worker_args and len(args) > 1:
                worker_args = args[1]

            def fake_start():
                # _ollama_worker 内部已捕获异常并写入队列，这里直接调用即可
                try:
                    target(*worker_args)
                except Exception:
                    pass

            p.start.side_effect = fake_start
            return p

        mock_process_class.side_effect = make_process
        yield


@pytest.fixture
def default_config():
    """默认路由器配置"""
    return RouterConfig()


@pytest.fixture
def mock_gpu_monitor():
    """Mock GPU 监控器（充足显存 8GB free，medium 6GB + 1GB margin = 7GB 也能装下）"""
    monitor = Mock(spec=GPUMonitor)
    monitor.get_free_vram_gb.return_value = 8.0
    monitor.get_gpu_memory.return_value = GPUMemoryInfo(
        total_gb=10.0, used_gb=2.0, free_gb=8.0, utilization_percent=30.0
    )
    monitor.can_fit_model.return_value = True
    monitor.get_optimal_batch_size.return_value = 2
    return monitor


@pytest.fixture
def mock_gpu_monitor_low():
    """Mock GPU 监控器（显存不足 1GB free）"""
    monitor = Mock(spec=GPUMonitor)
    monitor.get_free_vram_gb.return_value = 1.0
    monitor.get_gpu_memory.return_value = GPUMemoryInfo(
        total_gb=8.0, used_gb=7.0, free_gb=1.0, utilization_percent=95.0
    )
    monitor.can_fit_model.return_value = False
    monitor.get_optimal_batch_size.return_value = 1
    return monitor


@pytest.fixture
def mock_cpu_monitor():
    """Mock CPU 监控器（充足内存 20GB available）"""
    monitor = Mock(spec=CPUMonitor)
    monitor.get_memory_info.return_value = {
        "total_gb": 32.0, "available_gb": 20.0, "percent_used": 30.0
    }
    monitor.get_cpu_percent.return_value = 15.0
    return monitor


@pytest.fixture
def mock_cpu_monitor_low():
    """Mock CPU 监控器（内存不足 2GB available）"""
    monitor = Mock(spec=CPUMonitor)
    monitor.get_memory_info.return_value = {
        "total_gb": 32.0, "available_gb": 2.0, "percent_used": 95.0
    }
    monitor.get_cpu_percent.return_value = 90.0
    return monitor


@pytest.fixture
def router(default_config, mock_gpu_monitor, mock_cpu_monitor):
    """已注入 Mock 依赖的 SmartRouter"""
    router = SmartRouter(default_config)
    router.gpu_monitor = mock_gpu_monitor
    router.cpu_monitor = mock_cpu_monitor
    return router


@pytest.fixture
def mock_ollama_response():
    """Mock Ollama 成功响应"""
    return {
        'message': {'content': 'Hello, this is a test response.'},
        'prompt_eval_count': 10,
        'eval_count': 20
    }


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI 客户端"""
    client = Mock()
    response = Mock()
    choice = Mock()
    choice.message.content = 'Cloud response here.'
    response.choices = [choice]
    response.usage = Mock()
    response.usage.total_tokens = 30
    client.chat.completions.create.return_value = response
    return client
