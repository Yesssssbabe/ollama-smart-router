# Ollama Smart Router 🧠⚡

智慧模型調度器 - 根據任務複雜度自動選擇最佳推理路徑。

讓本地小模型處理簡單任務，複雜任務自動切換大模型或雲端API，節省時間和成本。

**[简体中文](README.md) | [English](README_EN.md) | [日本語](README_JP.md) | [한국어](README_KR.md) | [Español](README_ES.md)**

---

## 📋 目錄

- [配置要求](#配置要求)
- [快速開始（5分鐘上手）](#快速開始5分鐘上手)
- [安裝步驟](#安裝步驟)
- [使用方法](#使用方法)
- [常見問題](#常見問題)
- [聯絡方式](#聯絡方式)

---

## 配置要求

### ✅ 必要條件

| 項目 | 要求 | 檢查方法 |
|------|------|----------|
| **作業系統** | Windows 10+/macOS/Linux | - |
| **Python** | 3.9 或更高版本 | `python --version` |
| **Ollama** | 已安裝並運行 | 任務欄有羊駝圖標 |
| **記憶體** | 至少 8GB（推薦 16GB） | - |
| **網路** | 能訪問 GitHub 和 PyPI | 瀏覽器能打開 github.com |

### ⚠️ 可選條件（功能更強）

| 項目 | 說明 |
|------|------|
| **NVIDIA 顯卡** | 有 GPU 可以加速小模型推理 |
| **雲端 API 金鑰** | DeepSeek/OpenAI 等，用於複雜任務 |

---

## 快速開始（5分鐘上手）

### 第 1 步：檢查環境（30秒）

打開終端/PowerShell，運行：

```bash
# Windows
python --version
# 應該顯示 Python 3.9.x 或更高

# macOS/Linux
python3 --version
```

### 第 2 步：下載專案（1分鐘）

**方式 A：有 git**
```bash
git clone https://github.com/你的使用者名稱/ollama-smart-router.git
cd ollama-smart-router
```

**方式 B：沒有 git**
1. 點擊頁面綠色按鈕 `<> Code` → `Download ZIP`
2. 解壓到任意資料夾
3. 進入解壓後的資料夾

### 第 3 步：一鍵安裝（2分鐘）

**Windows：**
```powershell
# 在 PowerShell 中
python check_env.py      # 檢查環境
python install.py        # 自動安裝
```

**Mac/Linux：**
```bash
python3 check_env.py     # 檢查環境
python3 install.py       # 自動安裝
```

### 第 4 步：運行測試（1分鐘）

```bash
# 檢查硬體狀態
python -m src --status

# 簡單測試
python -m src "你好，請自我介紹"
```

🎉 **恭喜！** 如果看到回覆，說明安裝成功！

---

## 安裝步驟（詳細版）

### 1. 安裝 Python

**檢查是否已安裝：**
```bash
python --version      # Windows
python3 --version     # Mac/Linux
```

**如果沒有安裝：**
- Windows/Mac: [python.org/downloads](https://python.org/downloads) 下載安裝
- **重要**：安裝時勾選 `Add Python to PATH`

### 2. 安裝 Ollama

1. 訪問 [ollama.com](https://ollama.com)
2. 下載對應系統的安裝包
3. 安裝後運行 Ollama（任務欄出現羊駝圖標）
4. 下載至少一個模型：
   ```bash
   ollama pull gemma3:4b    # 小模型，必須
   ollama pull qwen2.5:7b   # 中模型，推薦
   ```

### 3. 安裝本專案

```bash
# 下載專案
git clone https://github.com/你的使用者名稱/ollama-smart-router.git
cd ollama-smart-router

# 安裝依賴
pip install -r requirements.txt

# 驗證安裝
python check_env.py
```

---

## 使用方法

### 命令列（推薦新手）

```bash
# 自動路由（最簡單）
python -m src "寫個Python快速排序"

# 互動模式（像ChatGPT一樣對話）
python -m src -i

# 強制使用 GPU
python -m src "問題" --strategy gpu

# 強制使用雲端（需要配置API金鑰）
python -m src "複雜問題" --strategy cloud

# 查看硬體狀態
python -m src --status

# 列出可用模型
python -m src --list-models
```

### Python 程式碼中使用

```python
from src.router import SmartRouter

# 創建路由器
router = SmartRouter()

# 自動路由
result = router.route("寫個Python快速排序")
print(result.content)

# 查看這次用了哪個路徑
print(f"路由到: {result.source}")  # local_gpu / local_cpu / cloud
print(f"耗時: {result.latency:.2f}秒")
```

### 配置雲端 API（可選）

**方式 1：環境變數（推薦）**
```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY="your-api-key-here"

# Mac/Linux
export DEEPSEEK_API_KEY="your-api-key-here"
```

**方式 2：配置檔案**
編輯 `config.yaml`：
```yaml
cloud:
  api_key: "your-api-key-here"
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
```

---

## ⚡ 核心功能

| 特性 | 說明 |
|------|------|
| 🎯 **智慧路由** | 自動分析任務複雜度，智慧選擇本地 GPU/CPU/雲端 |
| 🎮 **顯存保護** | 即時監控 GPU 顯存，避免崩潰 |
| 💻 **靈活降級** | GPU 不足時自動切換 CPU 推理 |
| ☁️ **雲端兜底** | 複雜任務無縫切換 DeepSeek 等 API |
| 📊 **複雜度分析** | 自動識別簡單/中等/複雜任務 |

---

## 常見問題

### Q1: 提示 `python` 不是內部命令？
**A:** Python 沒添加到 PATH。重新安裝 Python，**勾選 "Add Python to PATH"**。

### Q2: 提示 `ollama` 連線失敗？
**A:** 確保 Ollama 正在運行：
- Windows: 任務欄應該有羊駝圖標
- 命令列測試: `ollama list` 應該能列出模型

### Q3: 提示模型不存在？
**A:** 先下載模型：
```bash
ollama pull gemma3:4b    # 必須
ollama pull qwen2.5:7b   # 推薦
```

### Q4: 沒有 GPU 能用嗎？
**A:** **完全可以！** 沒有 GPU 會自動使用 CPU，只是速度稍慢。

### Q5: 如何只使用 CPU？
**A:** 
```bash
python -m src "問題" --strategy cpu
```

### Q6: Windows 怎麼打開終端？
**A:** 
1. 在專案資料夾空白處按住 `Shift` + 右鍵
2. 選擇 "在此處打開 PowerShell 視窗" 或 "終端"

---

## 📁 專案結構

```
ollama-smart-router/
├── src/                      # 原始碼
│   ├── router.py            # 智慧路由核心
│   ├── gpu_monitor.py       # GPU/CPU 監控
│   ├── complexity_analyzer.py # 複雜度分析
│   └── cli.py               # 命令列介面
├── examples/                 # 使用範例
├── check_env.py             # 環境檢查工具 ⭐
├── install.py               # 一鍵安裝腳本 ⭐
├── config.yaml              # 配置檔案
├── requirements.txt         # 依賴列表
├── README.md                # 簡體中文文件
├── README_EN.md             # 英文文件
├── README_TW.md             # 繁體中文文件（本文件）
├── README_JP.md             # 日文文件
├── README_KR.md             # 韓文文件
└── README_ES.md             # 西班牙語文件
```

---

## 🤝 貢獻

歡迎提交 Issue 和 PR！

---

## 聯絡方式

<img src="wechat-qr.jpg" width="200" alt="微信二維碼">

**掃碼加微信諮詢專案、提出改進建議**

> 加好友請備註：**ollama-smart-router**

---

## 授權條款

MIT License
