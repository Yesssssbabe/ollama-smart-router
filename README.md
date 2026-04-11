# Ollama Smart Router 🧠⚡

智能模型调度器 - 根据任务复杂度和硬件状态自动选择最佳推理路径。

解决显存不足跑大模型的痛点，自动在本地GPU、CPU和云端API之间智能切换。

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🎯 **智能路由** | 自动检测任务复杂度，选择本地GPU/CPU或云端API |
| 🎮 **显存感知** | 实时监控GPU显存，避免OOM崩溃 |
| 💻 **CPU兜底** | 大模型CPU推理兜底，多核并行优化 |
| ☁️ **云端备用** | 复杂任务自动切换DeepSeek等云端API |
| 📊 **复杂度分析** | 启发式算法自动评估任务难度 |
| ⚡ **流式输出** | 支持流式响应，体验更流畅 |

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/ollama-smart-router.git
cd ollama-smart-router

# 安装依赖
pip install -r requirements.txt

# 可选: 安装云端API支持
pip install openai
```

### 基础用法

```python
from src.router import SmartRouter

router = SmartRouter()

# 自动路由 - 系统会根据任务复杂度自动选择最佳路径
result = router.route("写个Python快速排序")
print(result.content)
```

### 命令行使用

```bash
# 自动路由
python -m src "你好"

# 指定策略
python -m src "复杂问题" --strategy cloud

# 交互模式
python -m src -i

# 查看硬件状态
python -m src --status
```

## 🧠 路由策略

### 自动路由决策逻辑

```
任务类型        GPU显存状态        路由目标
─────────────────────────────────────────────
简单任务    +   > 4GB空闲     →   本地GPU (4B模型)
简单任务    +   < 4GB空闲     →   本地CPU (4B模型)
中等任务    +   > 6GB空闲     →   本地GPU (7B模型)
中等任务    +   < 6GB空闲     →   本地CPU (7B模型，多核并行)
复杂任务    +   API已配置     →   云端API (DeepSeek)
复杂任务    +   无API配置     →   本地CPU (8B模型)
```

### 手动指定策略

```python
from src.router import RoutingStrategy

# 强制使用GPU
result = router.route("提示词", strategy=RoutingStrategy.LOCAL_GPU)

# 强制使用CPU
result = router.route("提示词", strategy=RoutingStrategy.LOCAL_CPU)

# 强制使用云端
result = router.route("提示词", strategy=RoutingStrategy.CLOUD)

# 手动指定复杂度
result = router.route("提示词", complexity="simple")  # simple/medium/complex
```

## ⚙️ 配置

### 环境变量

```bash
# 云端API密钥 (推荐)
export DEEPSEEK_API_KEY="your-api-key"

# 或配置其他提供商
export OPENAI_API_KEY="your-key"
```

### 配置文件 (config.yaml)

```yaml
# 模型配置
models:
  small: { name: "gemma3:4b", vram_gb: 3.0 }
  medium: { name: "qwen2.5:7b", vram_gb: 6.0 }
  large: { name: "llama3.2:8b", vram_gb: 7.0 }

# GPU阈值
gpu_thresholds:
  min_free_vram_gb: 4.0

# 云端配置
cloud:
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
```

## 📊 复杂度检测

系统自动分析以下维度评估任务复杂度：

- **文本长度**: 长文本通常更复杂
- **关键词匹配**: 代码、分析、学术等关键词
- **代码块**: 包含代码的任务路由到更强模型
- **推理需求**: 数学、逻辑、多步骤任务

```python
from src.complexity_analyzer import ComplexityAnalyzer

analyzer = ComplexityAnalyzer()
analysis = analyzer.analyze("写个Python快速排序")

print(analysis.complexity)      # TaskComplexity.MEDIUM
print(analysis.confidence)      # 0.85
print(analysis.requires_code)   # True
```

## 🎮 硬件监控

```python
from src.gpu_monitor import GPUMonitor, CPUMonitor

gpu = GPUMonitor()
cpu = CPUMonitor()

# 获取显存信息
info = gpu.get_gpu_memory()
print(f"空闲显存: {info.free_gb:.1f}GB")

# 检查是否能运行某模型
if gpu.can_fit_model(vram_required=6.0):
    print("可以运行7B模型")

# 打印状态
gpu.print_status()  # 🎮 GPU状态: 2.5/8.0 GB (30% 利用率)
cpu.print_status()  # 💻 CPU: 8核/16线程 | 内存: 12.5/16.0 GB 可用
```

## 📁 项目结构

```
ollama-smart-router/
├── src/
│   ├── __init__.py           # 包入口
│   ├── router.py             # 智能路由核心
│   ├── gpu_monitor.py        # GPU/CPU监控
│   ├── complexity_analyzer.py # 复杂度分析
│   └── cli.py                # 命令行接口
├── examples/
│   ├── basic_usage.py        # 基础用法
│   ├── hybrid_with_cloud.py  # 云端混合
│   ├── streaming_example.py  # 流式输出
│   ├── hardware_monitor.py   # 硬件监控
│   └── benchmark.py          # 性能测试
├── tests/                    # 测试代码
├── config.yaml               # 配置文件
├── requirements.txt          # 依赖
└── README.md                 # 本文件
```

## 🔧 推荐模型组合

针对 **8GB显存 + 16GB+内存** 配置的推荐：

```bash
# 小模型 (GPU) - 翻译、简单问答
ollama pull gemma3:4b

# 中模型 (CPU) - 代码、分析
ollama pull qwen2.5:7b

# 大模型 (CPU Fallback) - 复杂推理
ollama pull llama3.2:8b
```

显存占用参考：
- 4B模型: ~3GB VRAM
- 7B模型: ~6GB VRAM  
- 8B模型: ~7GB VRAM
- 14B模型: >8GB VRAM (必须使用CPU)

## 🌐 云端API集成

支持多个云端提供商：

| 提供商 | 配置 | 价格参考 |
|--------|------|----------|
| DeepSeek | base_url: `https://api.deepseek.com` | ¥1-2/百万tokens |
| 硅基流动 | base_url: `https://api.siliconflow.cn/v1` | ¥1-4/百万tokens |
| OpenRouter | base_url: `https://openrouter.ai/api/v1` | 多模型聚合 |

## 📈 性能对比

测试环境参考 (8GB显存 + 多核CPU) ：

| 任务类型 | GPU (4B) | CPU (7B) | 云端 |
|----------|----------|----------|------|
| 简单问答 | 0.5s ✅ | 2-4s | 1s |
| 代码生成 | 1s | 5-8s | 2s |
| 长文本分析 | 2s | 8-15s ✅ | 3s |
| 复杂推理 | OOM ❌ | 15s+ | 5s ✅ |

## 🤝 贡献

欢迎提交Issue和PR！

## 📜 许可证

MIT License
