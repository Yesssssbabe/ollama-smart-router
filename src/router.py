"""
智能路由核心模块
根据任务复杂度和硬件状态自动选择最佳推理路径
"""

import os
import time
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
from enum import Enum

import ollama

from .gpu_monitor import GPUMonitor, CPUMonitor
from .complexity_analyzer import ComplexityAnalyzer, TaskComplexity


class RoutingStrategy(Enum):
    """路由策略"""
    AUTO = "auto"           # 自动选择
    LOCAL_GPU = "gpu"       # 强制本地GPU
    LOCAL_CPU = "cpu"       # 强制本地CPU
    CLOUD = "cloud"         # 强制云端


@dataclass
class RouterConfig:
    """路由器配置"""
    # GPU阈值 (GB)
    gpu_vram_threshold: float = 4.0  # 低于此值转CPU
    
    # 模型配置
    small_model: str = "gemma3:4b"      # 小模型 4B
    medium_model: str = "qwen2.5:7b"    # 中模型 7B CPU
    large_model: str = "llama3.2:8b"    # 大模型 8B CPU (fallback)
    
    # 模型预估显存占用 (GB)
    small_model_vram: float = 3.0
    medium_model_vram: float = 6.0
    large_model_vram: float = 7.0
    
    # 云端配置
    cloud_api_key: Optional[str] = None
    cloud_base_url: str = "https://api.deepseek.com"
    cloud_model: str = "deepseek-chat"
    
    # 超时设置
    local_timeout: int = 120
    cloud_timeout: int = 60
    
    # 性能优化
    use_gpu_offload: bool = True  # 是否使用GPU卸载
    num_ctx: int = 4096           # 上下文长度
    
    # 路由行为
    prefer_cloud_for_complex: bool = True
    auto_fallback: bool = True
    max_fallback_attempts: int = 2


class InferenceResult:
    """推理结果"""
    def __init__(self, content: str, source: str, latency: float, tokens: int = 0):
        self.content = content
        self.source = source  # "local_gpu", "local_cpu", "cloud"
        self.latency = latency
        self.tokens = tokens
        self.timestamp = time.time()
        
    def __str__(self):
        return f"[{self.source}] {self.content[:100]}..."


class SmartRouter:
    """
    智能模型路由器
    
    适配硬件: U9 275HX (24核) + RTX 5060 8GB + 32GB RAM
    """
    
    def __init__(self, config: Optional[RouterConfig] = None):
        self.config = config or RouterConfig()
        self.gpu_monitor = GPUMonitor()
        self.cpu_monitor = CPUMonitor()
        self.analyzer = ComplexityAnalyzer()
        
        # 统计信息
        self.stats = {
            "gpu_calls": 0,
            "cpu_calls": 0,
            "cloud_calls": 0,
            "total_latency": 0
        }
        
        # 云端客户端延迟初始化
        self._cloud_client = None
        
    def _get_cloud_client(self):
        """延迟初始化云端客户端"""
        if self._cloud_client is None and self.config.cloud_api_key:
            try:
                import openai
                self._cloud_client = openai.OpenAI(
                    api_key=self.config.cloud_api_key,
                    base_url=self.config.cloud_base_url
                )
            except ImportError:
                print("⚠️ 未安装openai包，云端功能不可用。运行: pip install openai")
        return self._cloud_client
    
    def route(self, prompt: str, 
              complexity: Optional[str] = None,
              strategy: RoutingStrategy = RoutingStrategy.AUTO) -> InferenceResult:
        """
        智能路由主入口
        
        Args:
            prompt: 用户输入
            complexity: 手动指定复杂度 ("simple", "medium", "complex")
            strategy: 路由策略
        """
        start_time = time.time()
        
        # 1. 分析任务复杂度
        if complexity is None:
            analysis = self.analyzer.analyze(prompt)
            complexity = analysis.complexity.value
            print(f"📊 任务分析: {complexity} (置信度: {analysis.confidence:.0%}, "
                  f"预估tokens: {analysis.estimated_tokens})")
        
        # 2. 根据策略和复杂度选择执行路径
        if strategy == RoutingStrategy.LOCAL_GPU:
            result = self._run_local_gpu(prompt)
        elif strategy == RoutingStrategy.LOCAL_CPU:
            result = self._run_local_cpu(prompt)
        elif strategy == RoutingStrategy.CLOUD:
            result = self._run_cloud(prompt)
        else:  # AUTO
            result = self._auto_route(prompt, complexity)
        
        latency = time.time() - start_time
        result.latency = latency
        self.stats["total_latency"] += latency
        
        print(f"⏱️ 总耗时: {latency:.2f}s")
        return result
    
    @staticmethod
    def _extract_token_count(response) -> int:
        """从 Ollama 响应中提取 token 数量"""
        if not isinstance(response, dict):
            return 0
        # Ollama 返回 prompt_eval_count + eval_count
        prompt_tokens = response.get('prompt_eval_count', 0) or 0
        eval_tokens = response.get('eval_count', 0) or 0
        return int(prompt_tokens + eval_tokens)

    def _auto_route(self, prompt: str, complexity: str) -> InferenceResult:
        """自动路由决策"""
        gpu_mem = self.gpu_monitor.get_free_vram_gb()
        print(f"🎮 当前GPU空闲显存: {gpu_mem:.1f}GB")
        
        # 获取CPU状态
        cpu_mem = self.cpu_monitor.get_memory_info()
        print(f"💻 系统内存: {cpu_mem['available_gb']:.1f}GB 可用")
        
        # 路由决策逻辑
        if complexity == "simple":
            # 简单任务：优先GPU小模型
            if gpu_mem >= self.config.small_model_vram + 1:
                return self._run_local_gpu(prompt, self.config.small_model)
            else:
                return self._run_local_cpu(prompt, self.config.small_model)
                
        elif complexity == "medium":
            # 中等任务：GPU显存够就用GPU，否则CPU跑7B
            if gpu_mem >= self.config.medium_model_vram + 1:
                return self._run_local_gpu(prompt, self.config.medium_model)
            elif cpu_mem['available_gb'] >= 4:  # CPU需要至少4GB内存
                return self._run_local_cpu(prompt, self.config.medium_model)
            else:
                return self._run_cloud(prompt)
                
        else:  # complex
            # 复杂任务：优先云端API
            if self.config.cloud_api_key and self.config.prefer_cloud_for_complex:
                return self._run_cloud(prompt)
            elif cpu_mem['available_gb'] >= self.config.large_model_vram + 1:
                # fallback到CPU大模型
                return self._run_local_cpu(prompt, self.config.large_model)
            elif cpu_mem['available_gb'] >= self.config.medium_model_vram + 1:
                return self._run_local_cpu(prompt, self.config.medium_model)
            elif gpu_mem >= self.config.small_model_vram + 1:
                return self._run_local_gpu(prompt, self.config.small_model)
            else:
                # 最后尝试云端，即使没有配置密钥也可能有公网模型
                if self.config.cloud_api_key:
                    return self._run_cloud(prompt)
                raise RuntimeError("资源不足，无法处理复杂任务。请释放显存/内存或配置云端API密钥。")
    
    def _run_local_gpu(self, prompt: str, model: Optional[str] = None) -> InferenceResult:
        """本地GPU推理"""
        model = model or self.config.small_model
        print(f"🚀 [本地GPU] 使用模型: {model}")
        
        start = time.time()
        try:
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "num_ctx": self.config.num_ctx,
                    "num_gpu": 99,  # 使用最大GPU层数
                }
            )
            latency = time.time() - start
            self.stats["gpu_calls"] += 1
            
            return InferenceResult(
                content=response['message']['content'],
                source="local_gpu",
                latency=latency,
                tokens=self._extract_token_count(response)
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "out of memory" in error_msg or "oom" in error_msg:
                print(f"⚠️  GPU显存不足，自动切换到CPU...")
            else:
                print(f"⚠️  GPU推理失败: {e}，尝试CPU...")
            # 降级到CPU时，根据当前模型选择CPU上合适的模型
            fallback_model = self._choose_cpu_fallback_model(model)
            return self._run_local_cpu(prompt, fallback_model)

    def _choose_cpu_fallback_model(self, model: str) -> str:
        """根据GPU模型选择对应的CPU fallback模型"""
        if model == self.config.small_model:
            return self.config.small_model
        elif model == self.config.medium_model:
            return self.config.medium_model
        else:
            # 大模型GPU失败，先尝试中模型
            return self.config.medium_model
    
    def _run_local_cpu(self, prompt: str, model: Optional[str] = None) -> InferenceResult:
        """本地CPU推理"""
        model = model or self.config.medium_model
        print(f"💻 [本地CPU] 使用模型: {model} (多核并行)")
        
        start = time.time()
        try:
            # CPU推理：num_gpu=0 表示不卸载到GPU
            response = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "num_ctx": self.config.num_ctx,
                    "num_gpu": 0,  # 纯CPU推理
                    "num_thread": 0,  # 使用所有线程
                }
            )
            latency = time.time() - start
            self.stats["cpu_calls"] += 1
            
            return InferenceResult(
                content=response['message']['content'],
                source="local_cpu",
                latency=latency,
                tokens=self._extract_token_count(response)
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "model" in error_msg and ("not found" in error_msg or "not exist" in error_msg):
                print(f"\n❌ 模型未找到: {model}")
                print(f"💡 请下载模型: ollama pull {model}")
                raise RuntimeError(f"模型 {model} 未下载。运行: ollama pull {model}")
            
            print(f"❌ CPU推理失败: {e}")
            if self.config.cloud_api_key:
                print(f"🔄 尝试云端API...")
                return self._run_cloud(prompt)
            raise
    
    def _run_cloud(self, prompt: str) -> InferenceResult:
        """云端API推理"""
        print(f"☁️ [云端API] 使用: {self.config.cloud_model}")
        
        client = self._get_cloud_client()
        if not client:
            raise RuntimeError("云端客户端未初始化，请配置API密钥")
        
        start = time.time()
        try:
            response = client.chat.completions.create(
                model=self.config.cloud_model,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.config.cloud_timeout
            )
            latency = time.time() - start
            self.stats["cloud_calls"] += 1
            
            return InferenceResult(
                content=response.choices[0].message.content,
                source="cloud",
                latency=latency,
                tokens=response.usage.total_tokens if response.usage else 0
            )
        except Exception as e:
            print(f"❌ 云端API失败: {e}")
            # Fallback到本地
            return self._run_local_cpu(prompt)
    
    def print_stats(self):
        """打印统计信息"""
        total = self.stats["gpu_calls"] + self.stats["cpu_calls"] + self.stats["cloud_calls"]
        if total == 0:
            print("暂无统计信息")
            return

        print("\n📈 使用统计:")
        print(f"   GPU调用: {self.stats['gpu_calls']} ({self.stats['gpu_calls']/total:.0%})")
        print(f"   CPU调用: {self.stats['cpu_calls']} ({self.stats['cpu_calls']/total:.0%})")
        print(f"   云端调用: {self.stats['cloud_calls']} ({self.stats['cloud_calls']/total:.0%})")
        avg_latency = self.stats['total_latency'] / max(1, total)
        print(f"   总耗时: {self.stats['total_latency']:.2f}s")
        print(f"   平均延迟: {avg_latency:.2f}s")
    
    def list_available_models(self) -> List[str]:
        """列出Ollama中可用的模型"""
        try:
            models = ollama.list()
            return [m['model'] for m in models.get('models', [])]
        except Exception as e:
            print(f"获取模型列表失败: {e}")
            return []
