"""
路由器单元测试
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, '..')

from src.router import SmartRouter, RouterConfig, RoutingStrategy
from src.complexity_analyzer import ComplexityAnalyzer, TaskComplexity
from src.gpu_monitor import GPUMemoryInfo


class TestComplexityAnalyzer(unittest.TestCase):
    """测试复杂度分析器"""
    
    def setUp(self):
        self.analyzer = ComplexityAnalyzer()
    
    def test_simple_greeting(self):
        """测试简单问候语"""
        result = self.analyzer.analyze("你好")
        self.assertEqual(result.complexity, TaskComplexity.SIMPLE)
        self.assertTrue(result.confidence > 0.5)
    
    def test_code_task(self):
        """测试代码任务"""
        result = self.analyzer.analyze("写个Python排序函数")
        self.assertEqual(result.complexity, TaskComplexity.MEDIUM)
        self.assertTrue(result.requires_code)
    
    def test_complex_task(self):
        """测试复杂任务"""
        result = self.analyzer.analyze("设计一个支持百万并发的分布式系统架构")
        self.assertEqual(result.complexity, TaskComplexity.COMPLEX)


class TestSmartRouter(unittest.TestCase):
    """测试智能路由器"""
    
    def setUp(self):
        self.config = RouterConfig()
        self.router = SmartRouter(self.config)
    
    @patch('src.router.GPUMonitor.get_gpu_memory')
    def test_gpu_memory_check(self, mock_get_gpu):
        """测试GPU内存检查"""
        mock_get_gpu.return_value = GPUMemoryInfo(
            total_gb=8.0, used_gb=2.0, free_gb=6.0, utilization_percent=30.0
        )
        
        free_mem = self.router.gpu_monitor.get_free_vram_gb()
        self.assertEqual(free_mem, 6.0)
    
    def test_can_fit_model(self):
        """测试模型适配检查"""
        with patch.object(self.router.gpu_monitor, 'get_free_vram_gb', return_value=6.0):
            self.assertTrue(self.router.gpu_monitor.can_fit_model(3.0))
            self.assertFalse(self.router.gpu_monitor.can_fit_model(10.0))


class TestRouterConfig(unittest.TestCase):
    """测试路由器配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = RouterConfig()
        self.assertEqual(config.small_model, "gemma3:4b")
        self.assertEqual(config.gpu_vram_threshold, 4.0)
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = RouterConfig(
            small_model="custom:4b",
            cloud_api_key="test-key"
        )
        self.assertEqual(config.small_model, "custom:4b")
        self.assertEqual(config.cloud_api_key, "test-key")


if __name__ == '__main__':
    unittest.main()
