# Ollama Smart Router 🧠⚡

Intelligent Model Router - Automatically selects the best inference path based on task complexity.

Let local small models handle simple tasks, and automatically switch to large models or cloud APIs for complex tasks, saving time and costs.

**[简体中文](README.md) | [繁體中文](README_TW.md) | [日本語](README_JP.md) | [한국어](README_KR.md) | [Español](README_ES.md)**

---

## 📋 Table of Contents

- [Requirements](#requirements)
- [Quick Start (5 minutes)](#quick-start-5-minutes)
- [Installation](#installation)
- [Usage](#usage)
- [FAQ](#faq)
- [Contact](#contact)

---

## Requirements

### ✅ Required

| Item | Requirement | Check Method |
|------|-------------|--------------|
| **OS** | Windows 10+/macOS/Linux | - |
| **Python** | 3.9 or higher | `python --version` |
| **Ollama** | Installed and running | Ollama icon in taskbar |
| **RAM** | At least 8GB (16GB recommended) | - |
| **Network** | Access to GitHub and PyPI | Browser can open github.com |

### ⚠️ Optional (Enhanced Features)

| Item | Description |
|------|-------------|
| **NVIDIA GPU** | Accelerates small model inference |
| **Cloud API Key** | DeepSeek/OpenAI for complex tasks |

---

## Quick Start (5 minutes)

### Step 1: Check Environment (30 seconds)

Open terminal/PowerShell and run:

```bash
# Windows
python --version
# Should show Python 3.9.x or higher

# macOS/Linux
python3 --version
```

### Step 2: Download Project (1 minute)

**Option A: With git**
```bash
git clone https://github.com/Yesssssbabe/ollama-smart-router.git
cd ollama-smart-router
```

**Option B: Without git**
1. Click the green `<> Code` button → `Download ZIP`
2. Extract to any folder
3. Navigate to the extracted folder

### Step 3: One-Click Install (2 minutes)

**Windows:**
```powershell
# In PowerShell
python check_env.py      # Check environment
python install.py        # Auto install
```

**Mac/Linux:**
```bash
python3 check_env.py     # Check environment
python3 install.py       # Auto install
```

### Step 4: Test Run (1 minute)

```bash
# Check hardware status
python -m src --status

# Simple test
python -m src "Hello, introduce yourself"
```

🎉 **Congratulations!** If you see a response, installation is successful!

---

## Installation (Detailed)

### 1. Install Python

**Check if installed:**
```bash
python --version      # Windows
python3 --version     # Mac/Linux
```

**If not installed:**
- Windows/Mac: Download from [python.org/downloads](https://python.org/downloads)
- **Important**: Check `Add Python to PATH` during installation

### 2. Install Ollama

1. Visit [ollama.com](https://ollama.com)
2. Download installer for your OS
3. Run Ollama (icon appears in taskbar)
4. Download at least one model:
   ```bash
   ollama pull gemma3:4b    # Small model, required
   ollama pull qwen2.5:7b   # Medium model, recommended
   ```

### 3. Install This Project

```bash
# Download project
git clone https://github.com/Yesssssbabe/ollama-smart-router.git
cd ollama-smart-router

# Install dependencies
pip install -r requirements.txt

# Verify installation
python check_env.py
```

---

## Usage

### Command Line (Recommended for Beginners)

```bash
# Auto routing (easiest)
python -m src "Write a Python quick sort"

# Interactive mode (chat like ChatGPT)
python -m src -i

# Force GPU usage
python -m src "question" --strategy gpu

# Force cloud (requires API key configuration)
python -m src "complex question" --strategy cloud

# Check hardware status
python -m src --status

# List available models
python -m src --list-models
```

### Use in Python Code

```python
from src.router import SmartRouter

# Create router
router = SmartRouter()

# Auto routing
result = router.route("Write a Python quick sort")
print(result.content)

# Check which path was used
print(f"Routed to: {result.source}")  # local_gpu / local_cpu / cloud
print(f"Latency: {result.latency:.2f}s")
```

### Configure Cloud API (Optional)

**Option 1: Environment Variable (Recommended)**
```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY="your-api-key-here"

# Mac/Linux
export DEEPSEEK_API_KEY="your-api-key-here"
```

**Option 2: Config File**
Edit `config.yaml`:
```yaml
cloud:
  api_key: "your-api-key-here"
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
```

---

## ⚡ Core Features

| Feature | Description |
|---------|-------------|
| 🎯 **Smart Routing** | Auto-analyzes task complexity, intelligently selects local GPU/CPU/Cloud |
| 🎮 **VRAM Protection** | Real-time GPU memory monitoring, prevents crashes |
| 💻 **Flexible Fallback** | Auto-switches to CPU when GPU is insufficient |
| ☁️ **Cloud Backup** | Seamlessly switches to DeepSeek and other APIs |
| 📊 **Complexity Analysis** | Auto-identifies simple/medium/complex tasks |

---

## FAQ

### Q1: Error `python` is not recognized?
**A:** Python is not in PATH. Reinstall Python and **check "Add Python to PATH"**.

### Q2: Error `ollama` connection failed?
**A:** Ensure Ollama is running:
- Windows: Taskbar should have Ollama icon
- Test in terminal: `ollama list` should list models

### Q3: Error model not found?
**A:** Download the model first:
```bash
ollama pull gemma3:4b    # Required
ollama pull qwen2.5:7b   # Recommended
```

### Q4: Can I use without GPU?
**A:** **Absolutely!** Without GPU, it will automatically use CPU, just slightly slower.

### Q5: How to use CPU only?
**A:** 
```bash
python -m src "question" --strategy cpu
```

### Q6: How to open terminal on Windows?
**A:** 
1. In project folder, hold `Shift` + right-click
2. Select "Open PowerShell window here" or "Terminal"

---

## 📁 Project Structure

```
ollama-smart-router/
├── src/                      # Source code
│   ├── router.py            # Smart routing core
│   ├── gpu_monitor.py       # GPU/CPU monitoring
│   ├── complexity_analyzer.py # Complexity analysis
│   └── cli.py               # CLI interface
├── examples/                 # Usage examples
├── check_env.py             # Environment checker ⭐
├── install.py               # One-click installer ⭐
├── config.yaml              # Config file
├── requirements.txt         # Dependencies
├── README.md                # Simplified Chinese documentation
├── README_EN.md             # English documentation (this file)
├── README_TW.md             # Traditional Chinese documentation
├── README_JP.md             # Japanese documentation
├── README_KR.md             # Korean documentation
└── README_ES.md             # Spanish documentation
```

---

## 🤝 Contributing

Issues and PRs are welcome!

---

## Contact

<img src="wechat-qr.jpg" width="200" alt="WeChat QR Code">

**Scan to add WeChat for project consultation and suggestions**

> Please include in friend request: **ollama-smart-router**

---

## License

MIT License
