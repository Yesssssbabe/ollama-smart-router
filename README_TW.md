# Ollama Smart Router 🧠⚡

智慧模型調度器 - 根據任務複雜度自動選擇最佳推理路徑。

讓本地小模型處理簡單任務，複雜任務自動切換大模型或雲端API，節省時間和成本。

[简体中文](README.md) | [English](README_EN.md)

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🎯 **智慧路由** | 自動分析任務複雜度，智慧選擇本地GPU/CPU/雲端 |
| 🎮 **顯存保護** | 即時監控GPU顯存，避免OOM崩潰 |
| 💻 **靈活降級** | GPU不足時自動切換CPU推理 |
| ☁️ **雲端兜底** | 複雜任務無縫切換DeepSeek等API |
| 📊 **複雜度分析** | 啟發式演算法自動評估任務難度 |
| ⚡ **流式輸出** | 支援流式回應，體驗更流暢 |

---

## 🚀 快速開始

### 安裝

```bash
# 克隆倉庫
git clone https://github.com/yourusername/ollama-smart-router.git
cd ollama-smart-router

# 安裝依賴
pip install -r requirements.txt

# 可選: 安裝雲端API支援
pip install openai
```

### 基礎用法

```python
from src.router import SmartRouter

router = SmartRouter()

# 自動路由 - 系統會根據任務複雜度自動選擇最佳路徑
result = router.route("寫個Python快速排序")
print(result.content)
```

### 命令列使用

```bash
# 自動路由
python -m src "你好"

# 指定策略
python -m src "複雜問題" --strategy cloud

# 互動模式
python -m src -i

# 查看硬體狀態
python -m src --status
```

---

## 🧠 路由策略

### 自動路由決策

```
任務類型     GPU狀態         路由目標
─────────────────────────────────────────────
簡單任務  →  顯存充足   →   本地小模型(GPU)
簡單任務  →  顯存不足   →   本地小模型(CPU)
中等任務  →  顯存充足   →   本地中模型(GPU)
中等任務  →  顯存不足   →   本地中模型(CPU)
複雜任務  →  API已配置  →   雲端大模型
複雜任務  →  無API配置  →   本地大模型(CPU)
```

### 手動指定策略

```python
from src.router import RoutingStrategy

# 強制使用GPU
result = router.route("提示詞", strategy=RoutingStrategy.LOCAL_GPU)

# 強制使用CPU
result = router.route("提示詞", strategy=RoutingStrategy.LOCAL_CPU)

# 強制使用雲端
result = router.route("提示詞", strategy=RoutingStrategy.CLOUD)

# 手動指定複雜度
result = router.route("提示詞", complexity="simple")  # simple/medium/complex
```

---

## ⚙️ 配置

### 環境變數

```bash
# 雲端API金鑰 (推薦)
export DEEPSEEK_API_KEY="your-api-key"

# 或配置其他提供商
export OPENAI_API_KEY="your-key"
```

### 配置檔案 (config.yaml)

```yaml
# 模型配置
models:
  small: { name: "gemma3:4b" }
  medium: { name: "qwen2.5:7b" }
  large: { name: "llama3.2:8b" }

# 雲端配置
cloud:
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
```

---

## 📊 複雜度檢測

系統自動分析以下維度評估任務複雜度：

- **文字長度**: 長文字通常更複雜
- **關鍵詞匹配**: 程式碼、分析、學術等關鍵詞
- **程式碼區塊**: 包含程式碼的任務路由到更強模型
- **推理需求**: 數學、邏輯、多步驟任務

```python
from src.complexity_analyzer import ComplexityAnalyzer

analyzer = ComplexityAnalyzer()
analysis = analyzer.analyze("寫個Python快速排序")

print(analysis.complexity)      # TaskComplexity.MEDIUM
print(analysis.confidence)      # 0.85
print(analysis.requires_code)   # True
```

---

## 🎮 硬體監控

```python
from src.gpu_monitor import GPUMonitor, CPUMonitor

gpu = GPUMonitor()
cpu = CPUMonitor()

# 獲取顯存資訊
info = gpu.get_gpu_memory()
print(f"空閒顯存: {info.free_gb:.1f}GB")

# 檢查是否能執行某模型
if gpu.can_fit_model(vram_required=6.0):
    print("可以執行該模型")

# 列印狀態
gpu.print_status()
cpu.print_status()
```

---

## 📁 專案結構

```
ollama-smart-router/
├── src/
│   ├── router.py             # 智慧路由核心
│   ├── gpu_monitor.py        # GPU/CPU監控
│   ├── complexity_analyzer.py # 複雜度分析
│   └── cli.py                # 命令列介面
├── examples/                 # 使用範例
├── tests/                    # 測試程式碼
├── config.yaml               # 配置檔案
└── README.md                 # 本文件
```

---

## 🔧 推薦模型

```bash
# 小模型 - 翻譯、簡單問答
ollama pull gemma3:4b

# 中模型 - 程式碼、分析
ollama pull qwen2.5:7b

# 大模型 - 複雜推理
ollama pull llama3.2:8b
```

---

## 🌐 雲端API整合

支援多個雲端提供商：

| 提供商 | 配置 | 價格參考 |
|--------|------|----------|
| DeepSeek | `https://api.deepseek.com` | 低價 |
| 硅基流動 | `https://api.siliconflow.cn/v1` | 低價 |
| OpenRouter | `https://openrouter.ai/api/v1` | 多模型 |

---

## 🤝 貢獻

歡迎提交Issue和PR！

---

## 📞 聯絡作者

<img src="wechat-qr.jpg" width="200" alt="微信二維碼">

**掃碼加微信諮詢專案、提出改進建議**

> 加好友請備註：**ollama-smart-router**

---

## 📜 授權條款

MIT License
