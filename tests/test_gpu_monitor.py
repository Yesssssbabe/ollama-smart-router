# test_gpu_monitor.py — GPU/CPU 监控测试
import pytest
from unittest.mock import Mock, patch

from src.gpu_monitor import GPUMonitor, CPUMonitor, GPUMemoryInfo


class TestGPUMonitor:
    """测试 GPU 监控器"""

    def test_init_with_nvidia_smi(self):
        with patch('shutil.which', return_value="/usr/bin/nvidia-smi"):
            monitor = GPUMonitor()
        assert monitor.has_nvidia_smi is True

    def test_init_without_nvidia_smi(self):
        with patch('shutil.which', return_value=None):
            monitor = GPUMonitor()
        assert monitor.has_nvidia_smi is False

    def test_get_gpu_memory_success(self):
        monitor = GPUMonitor()
        monitor.has_nvidia_smi = True
        
        mock_result = Mock()
        mock_result.stdout = "8192, 2048, 6144, 30\n"
        mock_result.returncode = 0
        
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            info = monitor.get_gpu_memory()
        
        assert info is not None
        assert info.total_gb == 8.0  # 8192 / 1024
        assert info.used_gb == 2.0
        assert info.free_gb == 6.0
        assert info.utilization_percent == 30.0
        mock_run.assert_called_once()

    def test_get_gpu_memory_no_nvidia_smi(self):
        monitor = GPUMonitor()
        monitor.has_nvidia_smi = False
        assert monitor.get_gpu_memory() is None

    def test_get_gpu_memory_subprocess_error(self):
        monitor = GPUMonitor()
        monitor.has_nvidia_smi = True
        
        with patch('subprocess.run', side_effect=Exception("command not found")):
            info = monitor.get_gpu_memory()
        
        assert info is None

    def test_get_gpu_memory_parse_error(self):
        monitor = GPUMonitor()
        monitor.has_nvidia_smi = True
        
        mock_result = Mock()
        mock_result.stdout = "invalid output"  # 无法解析
        
        with patch('subprocess.run', return_value=mock_result):
            info = monitor.get_gpu_memory()
        
        assert info is None

    def test_get_gpu_memory_timeout(self):
        monitor = GPUMonitor()
        monitor.has_nvidia_smi = True
        
        with patch('subprocess.run', side_effect=TimeoutError("timeout")):
            info = monitor.get_gpu_memory()
        
        assert info is None

    def test_get_gpu_memory_multi_gpu(self):
        """多GPU系统处理"""
        monitor = GPUMonitor()
        monitor.has_nvidia_smi = True
        
        mock_result = Mock()
        mock_result.stdout = "8192, 2048, 6144, 30\n4096, 1024, 3072, 25\n"
        
        with patch('subprocess.run', return_value=mock_result):
            info = monitor.get_gpu_memory(gpu_index=0)
        
        assert info is not None
        assert info.total_gb == 8.0

    def test_get_free_vram_gb_with_gpu(self):
        monitor = GPUMonitor()
        with patch.object(monitor, 'get_gpu_memory', return_value=GPUMemoryInfo(8, 2, 6, 30)):
            assert monitor.get_free_vram_gb() == 6.0

    def test_get_free_vram_gb_no_gpu(self):
        monitor = GPUMonitor()
        with patch.object(monitor, 'get_gpu_memory', return_value=None):
            assert monitor.get_free_vram_gb() is None

    def test_can_fit_model(self):
        monitor = GPUMonitor()
        with patch.object(monitor, 'get_free_vram_gb', return_value=6.0):
            assert monitor.can_fit_model(3.0) is True   # 3 + 1 = 4 <= 6
            assert monitor.can_fit_model(3.0, 2.0) is True  # 3 + 2 = 5 <= 6
            assert monitor.can_fit_model(6.0) is False  # 6 + 1 = 7 > 6

    def test_can_fit_model_negative_vram(self):
        """负数模型显存"""
        monitor = GPUMonitor()
        assert monitor.can_fit_model(-1.0) is False

    def test_can_fit_model_no_gpu_info(self):
        """无法获取GPU信息"""
        monitor = GPUMonitor()
        with patch.object(monitor, 'get_free_vram_gb', return_value=None):
            assert monitor.can_fit_model(3.0) is False

    def test_can_fit_model_exact_boundary(self):
        """边界条件：刚好等于"""
        monitor = GPUMonitor()
        with patch.object(monitor, 'get_free_vram_gb', return_value=4.0):
            assert monitor.can_fit_model(3.0) is True  # 3 + 1 = 4 <= 4
            assert monitor.can_fit_model(3.1) is False  # 3.1 + 1 = 4.1 > 4

    def test_get_optimal_batch_size(self):
        monitor = GPUMonitor()
        with patch.object(monitor, 'get_gpu_memory', return_value=GPUMemoryInfo(8, 2, 6, 30)):
            # 剩余: 6 - 3 - 1 = 2 → 2/2 + 1 = 2
            assert monitor.get_optimal_batch_size(3.0) == 2

    def test_get_optimal_batch_size_tight(self):
        monitor = GPUMonitor()
        with patch.object(monitor, 'get_gpu_memory', return_value=GPUMemoryInfo(8, 7, 1, 95)):
            # 剩余: 1 - 3 - 1 = -3 → max(0, -3) = 0 → 0/2 + 1 = 1
            assert monitor.get_optimal_batch_size(3.0) == 1

    def test_get_optimal_batch_size_no_gpu(self):
        """无GPU时返回1"""
        monitor = GPUMonitor()
        with patch.object(monitor, 'get_gpu_memory', return_value=None):
            assert monitor.get_optimal_batch_size(3.0) == 1

    def test_print_status(self, capsys):
        monitor = GPUMonitor()
        with patch.object(monitor, 'get_gpu_memory', return_value=GPUMemoryInfo(8, 2, 6, 30)):
            monitor.print_status()
        captured = capsys.readouterr()
        assert "GPU状态" in captured.out
        assert "2.0/8.0" in captured.out

    def test_print_status_no_gpu(self, capsys):
        monitor = GPUMonitor()
        with patch.object(monitor, 'get_gpu_memory', return_value=None):
            monitor.print_status()
        captured = capsys.readouterr()
        assert "无法获取GPU信息" in captured.out

    def test_cache_ttl(self):
        """缓存TTL测试"""
        import time
        monitor = GPUMonitor(cache_ttl=0.5)
        monitor.has_nvidia_smi = True
        
        mock_result = Mock()
        mock_result.stdout = "8192, 2048, 6144, 30\n"
        
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            info1 = monitor.get_gpu_memory()
            info2 = monitor.get_gpu_memory()  # 应使用缓存
            assert mock_run.call_count == 1
            
            time.sleep(0.6)  # 等待缓存过期
            info3 = monitor.get_gpu_memory()  # 应重新查询
            assert mock_run.call_count == 2
        
        assert info1 is not None
        assert info2 is not None
        assert info3 is not None


class TestCPUMonitor:
    """测试 CPU 监控器"""

    def test_init_with_psutil(self):
        with patch('src.gpu_monitor.HAS_PSUTIL', True):
            with patch('psutil.cpu_count', return_value=24):
                monitor = CPUMonitor()
        assert monitor.cpu_count == 24

    def test_init_without_psutil(self):
        with patch('src.gpu_monitor.HAS_PSUTIL', False):
            with pytest.raises(ImportError, match="psutil"):
                CPUMonitor()

    def test_get_cpu_percent(self):
        with patch('src.gpu_monitor.HAS_PSUTIL', True):
            with patch('psutil.cpu_count', return_value=24):
                monitor = CPUMonitor()
            with patch('psutil.cpu_percent', return_value=45.5):
                assert monitor.get_cpu_percent() == 45.5

    def test_get_cpu_percent_non_blocking(self):
        """CPU 使用率非阻塞"""
        with patch('src.gpu_monitor.HAS_PSUTIL', True):
            with patch('psutil.cpu_count', return_value=24):
                monitor = CPUMonitor()
            with patch('psutil.cpu_percent', return_value=30.0) as mock_percent:
                result = monitor.get_cpu_percent()
        
        mock_percent.assert_called_once_with(interval=None)
        assert result == 30.0

    def test_get_memory_info(self):
        mock_mem = Mock()
        mock_mem.total = 32 * 1024**3  # 32 GB
        mock_mem.available = 16 * 1024**3
        mock_mem.percent = 50.0
        
        with patch('src.gpu_monitor.HAS_PSUTIL', True):
            with patch('psutil.cpu_count', return_value=24):
                monitor = CPUMonitor()
            with patch('psutil.virtual_memory', return_value=mock_mem):
                info = monitor.get_memory_info()
        
        assert info["total_gb"] == 32.0
        assert info["available_gb"] == 16.0
        assert info["percent_used"] == 50.0

    def test_print_status(self, capsys):
        mock_mem = Mock()
        mock_mem.total = 32 * 1024**3
        mock_mem.available = 16 * 1024**3
        mock_mem.percent = 50.0
        
        with patch('src.gpu_monitor.HAS_PSUTIL', True):
            with patch('psutil.cpu_count', return_value=24):
                with patch('psutil.cpu_count', return_value=24):
                    monitor = CPUMonitor()
                with patch('psutil.virtual_memory', return_value=mock_mem):
                    monitor.print_status()
        
        captured = capsys.readouterr()
        assert "CPU" in captured.out
        assert "内存" in captured.out
