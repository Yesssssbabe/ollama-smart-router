# Ollama Smart Router 🧠⚡

智能模型调度器 - 根据任务复杂度自动选择最佳推理路径。

让本地小模型处理简单任务，复杂任务自动切换大模型或云端API，节省时间和成本。

[English](README_EN.md) | [繁體中文](README_TW.md)

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🎯 **智能路由** | 自动分析任务复杂度，智能选择本地GPU/CPU/云端 |
| 🎮 **显存保护** | 实时监控GPU显存，避免OOM崩溃 |
| 💻 **灵活降级** | GPU不足时自动切换CPU推理 |
| ☁️ **云端兜底** | 复杂任务无缝切换DeepSeek等API |
| 📊 **复杂度分析** | 启发式算法自动评估任务难度 |
| ⚡ **流式输出** | 支持流式响应，体验更流畅 |

---

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

---

## 🧠 路由策略

### 自动路由决策

```
任务类型     GPU状态         路由目标
─────────────────────────────────────────────
简单任务  →  显存充足   →   本地小模型(GPU)
简单任务  →  显存不足   →   本地小模型(CPU)
中等任务  →  显存充足   →   本地中模型(GPU)
中等任务  →  显存不足   →   本地中模型(CPU)
复杂任务  →  API已配置  →   云端大模型
复杂任务  →  无API配置  →   本地大模型(CPU)
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

---

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
  small: { name: "gemma3:4b" }
  medium: { name: "qwen2.5:7b" }
  large: { name: "llama3.2:8b" }

# 云端配置
cloud:
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
```

---

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

---

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
    print("可以运行该模型")

# 打印状态
gpu.print_status()
cpu.print_status()
```

---

## 📁 项目结构

```
ollama-smart-router/
├── src/
│   ├── router.py             # 智能路由核心
│   ├── gpu_monitor.py        # GPU/CPU监控
│   ├── complexity_analyzer.py # 复杂度分析
│   └── cli.py                # 命令行接口
├── examples/                 # 使用示例
├── tests/                    # 测试代码
├── config.yaml               # 配置文件
└── README.md                 # 本文件
```

---

## 🔧 推荐模型

```bash
# 小模型 - 翻译、简单问答
ollama pull gemma3:4b

# 中模型 - 代码、分析
ollama pull qwen2.5:7b

# 大模型 - 复杂推理
ollama pull llama3.2:8b
```

---

## 🌐 云端API集成

支持多个云端提供商：

| 提供商 | 配置 | 价格参考 |
|--------|------|----------|
| DeepSeek | `https://api.deepseek.com` | 低价 |
| 硅基流动 | `https://api.siliconflow.cn/v1` | 低价 |
| OpenRouter | `https://openrouter.ai/api/v1` | 多模型 |

---

## 🤝 贡献

欢迎提交Issue和PR！

---

## 📞 联系作者

<img src="wechat-qr.jpg" width="200" alt="微信二维码">

**扫码加微信咨询项目、提出改进建议**

> 加好友请备注：**ollama-smart-router**

---

## 📜 许可证

MIT License
