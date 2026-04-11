# Ollama Smart Router 🧠⚡

智能模型调度器 - 根据任务复杂度自动选择最佳推理路径。

让本地小模型处理简单任务，复杂任务自动切换大模型或云端API，节省时间和成本。

**[English](README_EN.md) | [繁體中文](README_TW.md)**

---

## 📋 目录

- [配置要求](#配置要求)
- [快速开始（5分钟上手）](#快速开始5分钟上手)
- [安装步骤](#安装步骤)
- [使用方法](#使用方法)
- [常见问题](#常见问题)
- [联系方式](#联系方式)

---

## 配置要求

### ✅ 必须条件

| 项目 | 要求 | 检查方法 |
|------|------|----------|
| **操作系统** | Windows 10+/macOS/Linux | - |
| **Python** | 3.9 或更高版本 | `python --version` |
| **Ollama** | 已安装并运行 | 任务栏有羊驼图标 |
| **内存** | 至少 8GB（推荐 16GB） | - |
| **网络** | 能访问 GitHub 和 PyPI | 浏览器能打开 github.com |

### ⚠️ 可选条件（功能更强）

| 项目 | 说明 |
|------|------|
| **NVIDIA 显卡** | 有 GPU 可以加速小模型推理 |
| **云端 API 密钥** | DeepSeek/OpenAI 等，用于复杂任务 |

---

## 快速开始（5分钟上手）

### 第 1 步：检查环境（30秒）

打开终端/PowerShell，运行：

```bash
# Windows
python --version
# 应该显示 Python 3.9.x 或更高

# macOS/Linux
python3 --version
```

### 第 2 步：下载项目（1分钟）

**方式 A：有 git**
```bash
git clone https://github.com/你的用户名/ollama-smart-router.git
cd ollama-smart-router
```

**方式 B：没有 git**
1. 点击页面绿色按钮 `<> Code` → `Download ZIP`
2. 解压到任意文件夹
3. 进入解压后的文件夹

### 第 3 步：一键安装（2分钟）

**Windows：**
```powershell
# 在 PowerShell 中
python check_env.py      # 检查环境
python install.py        # 自动安装
```

**Mac/Linux：**
```bash
python3 check_env.py     # 检查环境
python3 install.py       # 自动安装
```

### 第 4 步：运行测试（1分钟）

```bash
# 检查硬件状态
python -m src --status

# 简单测试
python -m src "你好，请自我介绍"
```

🎉 **恭喜！** 如果看到回复，说明安装成功！

---

## 安装步骤（详细版）

### 1. 安装 Python

**检查是否已安装：**
```bash
python --version      # Windows
python3 --version     # Mac/Linux
```

**如果没有安装：**
- Windows/Mac: [python.org/downloads](https://python.org/downloads) 下载安装
- **重要**：安装时勾选 `Add Python to PATH`

### 2. 安装 Ollama

1. 访问 [ollama.com](https://ollama.com)
2. 下载对应系统的安装包
3. 安装后运行 Ollama（任务栏出现羊驼图标）
4. 下载至少一个模型：
   ```bash
   ollama pull gemma3:4b    # 小模型，必须
   ollama pull qwen2.5:7b   # 中模型，推荐
   ```

### 3. 安装本项目

```bash
# 下载项目
git clone https://github.com/你的用户名/ollama-smart-router.git
cd ollama-smart-router

# 安装依赖
pip install -r requirements.txt

# 验证安装
python check_env.py
```

---

## 使用方法

### 命令行（推荐新手）

```bash
# 自动路由（最简单）
python -m src "写个Python快速排序"

# 交互模式（像ChatGPT一样对话）
python -m src -i

# 强制使用 GPU
python -m src "问题" --strategy gpu

# 强制使用云端（需要配置API密钥）
python -m src "复杂问题" --strategy cloud

# 查看硬件状态
python -m src --status

# 列出可用模型
python -m src --list-models
```

### Python 代码中使用

```python
from src.router import SmartRouter

# 创建路由器
router = SmartRouter()

# 自动路由
result = router.route("写个Python快速排序")
print(result.content)

# 查看这次用了哪个路径
print(f"路由到: {result.source}")  # local_gpu / local_cpu / cloud
print(f"耗时: {result.latency:.2f}秒")
```

### 配置云端 API（可选）

**方式 1：环境变量（推荐）**
```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY="your-api-key-here"

# Mac/Linux
export DEEPSEEK_API_KEY="your-api-key-here"
```

**方式 2：配置文件**
编辑 `config.yaml`：
```yaml
cloud:
  api_key: "your-api-key-here"
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
```

---

## ⚡ 核心功能

| 特性 | 说明 |
|------|------|
| 🎯 **智能路由** | 自动分析任务复杂度，智能选择本地 GPU/CPU/云端 |
| 🎮 **显存保护** | 实时监控 GPU 显存，避免崩溃 |
| 💻 **灵活降级** | GPU 不足时自动切换 CPU 推理 |
| ☁️ **云端兜底** | 复杂任务无缝切换 DeepSeek 等 API |
| 📊 **复杂度分析** | 自动识别简单/中等/复杂任务 |

### 路由决策逻辑

```
你输入的问题
      ↓
[复杂度分析器] 判断任务难度
      ↓
┌─────────────────────────────────────┐
│ 简单任务 + GPU 显存够 → 本地小模型  │
│ 简单任务 + GPU 显存少 → 本地小模型  │
│ 中等任务 + GPU 显存够 → 本地中模型  │
│ 中等任务 + GPU 显存少 → 本地中模型  │
│ 复杂任务 + API 已配置 → 云端大模型  │
│ 复杂任务 + 无 API    → 本地大模型  │
└─────────────────────────────────────┘
      ↓
   返回答案
```

---

## 常见问题

### Q1: 提示 `python` 不是内部命令？
**A:** Python 没添加到 PATH。重新安装 Python，**勾选 "Add Python to PATH"**。

### Q2: 提示 `ollama` 连接失败？
**A:** 确保 Ollama 正在运行：
- Windows: 任务栏应该有羊驼图标
- 命令行测试: `ollama list` 应该能列出模型

### Q3: 提示模型不存在？
**A:** 先下载模型：
```bash
ollama pull gemma3:4b    # 必须
ollama pull qwen2.5:7b   # 推荐
```

### Q4: 没有 GPU 能用吗？
**A:** **完全可以！** 没有 GPU 会自动使用 CPU，只是速度稍慢。

### Q5: 如何只使用 CPU？
**A:** 
```bash
python -m src "问题" --strategy cpu
```

### Q6: Windows 怎么打开终端？
**A:** 
1. 在项目文件夹空白处按住 `Shift` + 右键
2. 选择 "在此处打开 PowerShell 窗口" 或 "终端"

---

## 📁 项目结构

```
ollama-smart-router/
├── src/                      # 源代码
│   ├── router.py            # 智能路由核心
│   ├── gpu_monitor.py       # GPU/CPU 监控
│   ├── complexity_analyzer.py # 复杂度分析
│   └── cli.py               # 命令行界面
├── examples/                 # 使用示例
├── check_env.py             # 环境检查工具 ⭐
├── install.py               # 一键安装脚本 ⭐
├── config.yaml              # 配置文件
├── requirements.txt         # 依赖列表
└── README.md                # 本文件
```

---

## 🛠️ 高级配置

### 修改默认模型

编辑 `config.yaml`：
```yaml
models:
  small: { name: "gemma3:4b" }    # 简单任务
  medium: { name: "qwen2.5:7b" }   # 中等任务
  large: { name: "llama3.2:8b" }   # 复杂任务
```

### 调整显存阈值

```yaml
gpu_thresholds:
  min_free_vram_gb: 4.0    # 低于此值转 CPU
  safety_margin_gb: 1.0    # 安全余量
```

---

## 🤝 贡献

欢迎提交 Issue 和 PR！

---

## 📞 联系作者

<img src="wechat-qr.jpg" width="200" alt="微信二维码">

**扫码加微信咨询项目、提出改进建议**

> 加好友请备注：**ollama-smart-router**

---

## 📜 许可证

MIT License
