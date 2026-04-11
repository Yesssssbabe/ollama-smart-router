# Ollama Smart Router 🧠⚡

Intelligent Model Router - Automatically selects the best inference path based on task complexity.

Let local small models handle simple tasks, and automatically switch to large models or cloud APIs for complex tasks, saving time and costs.

[简体中文](README.md) | [繁體中文](README_TW.md)

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🎯 **Smart Routing** | Automatically analyzes task complexity, intelligently selects local GPU/CPU/Cloud |
| 🎮 **VRAM Protection** | Real-time GPU memory monitoring, prevents OOM crashes |
| 💻 **Flexible Fallback** | Automatically switches to CPU inference when GPU is insufficient |
| ☁️ **Cloud Backup** | Seamlessly switches to DeepSeek and other APIs for complex tasks |
| 📊 **Complexity Analysis** | Heuristic algorithm automatically evaluates task difficulty |
| ⚡ **Streaming Output** | Supports streaming responses for smoother experience |

---

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/ollama-smart-router.git
cd ollama-smart-router

# Install dependencies
pip install -r requirements.txt

# Optional: Install cloud API support
pip install openai
```

### Basic Usage

```python
from src.router import SmartRouter

router = SmartRouter()

# Auto routing - System automatically selects the best path based on task complexity
result = router.route("Write a Python quick sort algorithm")
print(result.content)
```

### CLI Usage

```bash
# Auto routing
python -m src "Hello"

# Specify strategy
python -m src "Complex question" --strategy cloud

# Interactive mode
python -m src -i

# Check hardware status
python -m src --status
```

---

## 🧠 Routing Strategy

### Auto Routing Decision

```
Task Type     GPU Status      Routing Target
─────────────────────────────────────────────────
Simple    →   VRAM OK    →   Local Small Model (GPU)
Simple    →   VRAM Low   →   Local Small Model (CPU)
Medium    →   VRAM OK    →   Local Medium Model (GPU)
Medium    →   VRAM Low   →   Local Medium Model (CPU)
Complex   →   API Ready  →   Cloud Large Model
Complex   →   No API     →   Local Large Model (CPU)
```

### Manual Strategy Selection

```python
from src.router import RoutingStrategy

# Force GPU usage
result = router.route("Prompt", strategy=RoutingStrategy.LOCAL_GPU)

# Force CPU usage
result = router.route("Prompt", strategy=RoutingStrategy.LOCAL_CPU)

# Force cloud usage
result = router.route("Prompt", strategy=RoutingStrategy.CLOUD)

# Manually specify complexity
result = router.route("Prompt", complexity="simple")  # simple/medium/complex
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# Cloud API key (recommended)
export DEEPSEEK_API_KEY="your-api-key"

# Or configure other providers
export OPENAI_API_KEY="your-key"
```

### Config File (config.yaml)

```yaml
# Model configuration
models:
  small: { name: "gemma3:4b" }
  medium: { name: "qwen2.5:7b" }
  large: { name: "llama3.2:8b" }

# Cloud configuration
cloud:
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
```

---

## 📊 Complexity Detection

The system automatically evaluates task complexity based on:

- **Text Length**: Longer texts are usually more complex
- **Keyword Matching**: Code, analysis, academic keywords
- **Code Blocks**: Tasks containing code are routed to stronger models
- **Reasoning Requirements**: Math, logic, multi-step tasks

```python
from src.complexity_analyzer import ComplexityAnalyzer

analyzer = ComplexityAnalyzer()
analysis = analyzer.analyze("Write a Python quick sort")

print(analysis.complexity)      # TaskComplexity.MEDIUM
print(analysis.confidence)      # 0.85
print(analysis.requires_code)   # True
```

---

## 🎮 Hardware Monitoring

```python
from src.gpu_monitor import GPUMonitor, CPUMonitor

gpu = GPUMonitor()
cpu = CPUMonitor()

# Get VRAM info
info = gpu.get_gpu_memory()
print(f"Free VRAM: {info.free_gb:.1f}GB")

# Check if can run a model
if gpu.can_fit_model(vram_required=6.0):
    print("Can run this model")

# Print status
gpu.print_status()
cpu.print_status()
```

---

## 📁 Project Structure

```
ollama-smart-router/
├── src/
│   ├── router.py             # Smart routing core
│   ├── gpu_monitor.py        # GPU/CPU monitoring
│   ├── complexity_analyzer.py # Complexity analysis
│   └── cli.py                # CLI interface
├── examples/                 # Usage examples
├── tests/                    # Test code
├── config.yaml               # Config file
└── README.md                 # This file
```

---

## 🔧 Recommended Models

```bash
# Small model - Translation, simple Q&A
ollama pull gemma3:4b

# Medium model - Code, analysis
ollama pull qwen2.5:7b

# Large model - Complex reasoning
ollama pull llama3.2:8b
```

---

## 🌐 Cloud API Integration

Supports multiple cloud providers:

| Provider | Config | Pricing |
|----------|--------|---------|
| DeepSeek | `https://api.deepseek.com` | Low cost |
| SiliconFlow | `https://api.siliconflow.cn/v1` | Low cost |
| OpenRouter | `https://openrouter.ai/api/v1` | Multi-model |

---

## 🤝 Contributing

Issues and PRs are welcome!

---

## 📞 Contact Author

<img src="wechat-qr.jpg" width="200" alt="WeChat QR Code">

**Scan to add WeChat for project consultation and suggestions**

> Please include in friend request: **ollama-smart-router**

---

## 📜 License

MIT License
