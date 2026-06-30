# Ollama Smart Router 🧠⚡

インテリジェントモデルルーター - タスクの複雑さに応じて最適な推論パスを自動選択します。

ローカルの小規模モデルで単純なタスクを処理し、複雑なタスクは自動的に大規模モデルまたはクラウドAPIに切り替え、時間とコストを節約します。

**[简体中文](README.md) | [English](README_EN.md) | [繁體中文](README_TW.md) | 日本語 | [한국어](README_KR.md) | [Español](README_ES.md)**

---

## 📋 目次

- [要件](#要件)
- [クイックスタート（5分で始める）](#クイックスタート5分で始める)
- [インストール手順](#インストール手順)
- [使い方](#使い方)
- [よくある質問](#よくある質問)
- [連絡先](#連絡先)

---

## 要件

### ✅ 必須条件

| 項目 | 要件 | 確認方法 |
|------|------|----------|
| **OS** | Windows 10+/macOS/Linux | - |
| **Python** | 3.9 以上 | `python --version` |
| **Ollama** | インストール済みかつ実行中 | タスクバーに羊驼アイコン |
| **メモリ** | 最低 8GB（推奨 16GB） | - |
| **ネットワーク** | GitHub と PyPI にアクセス可能 | ブラウザで github.com が開ける |

### ⚠️ オプション条件（より強力な機能）

| 項目 | 説明 |
|------|------|
| **NVIDIA グラフィックスカード** | GPU があれば小規模モデルの推論を高速化 |
| **クラウド API キー** | DeepSeek/OpenAI など、複雑なタスク用 |

---

## クイックスタート（5分で始める）

### ステップ 1：環境確認（30秒）

ターミナル/PowerShell を開いて実行：

```bash
# Windows
python --version
# Python 3.9.x 以上が表示されるはず

# macOS/Linux
python3 --version
```

### ステップ 2：プロジェクトをダウンロード（1分）

**方法 A：git がある場合**
```bash
git clone https://github.com/Yesssssbabe/ollama-smart-router.git
cd ollama-smart-router
```

**方法 B：git がない場合**
1. ページの緑色ボタン `<> Code` → `Download ZIP` をクリック
2. 任意のフォルダに展開
3. 展開後のフォルダに移動

### ステップ 3：ワンクリックインストール（2分）

**Windows：**
```powershell
# PowerShell で
python check_env.py      # 環境確認
python install.py        # 自動インストール
```

**Mac/Linux：**
```bash
python3 check_env.py     # 環境確認
python3 install.py       # 自動インストール
```

### ステップ 4：テスト実行（1分）

```bash
# ハードウェア状態の確認
python -m src --status

# 簡単なテスト
python -m src "こんにちは、自己紹介してください"
```

🎉 **おめでとうございます！** 応答が表示されればインストール成功です！

---

## インストール手順（詳細版）

### 1. Python のインストール

**インストール済みか確認：**
```bash
python --version      # Windows
python3 --version     # Mac/Linux
```

**未インストールの場合：**
- Windows/Mac: [python.org/downloads](https://python.org/downloads) からダウンロードしてインストール
- **重要**：インストール時に `Add Python to PATH` をチェック

### 2. Ollama のインストール

1. [ollama.com](https://ollama.com) にアクセス
2. ご使用のシステム用インストーラーをダウンロード
3. インストール後、Ollama を実行（タスクバーに羊驼アイコンが表示される）
4. 少なくとも 1 つのモデルをダウンロード：
   ```bash
   ollama pull gemma3:4b    # 小規模モデル、必須
   ollama pull qwen2.5:7b   # 中規模モデル、推奨
   ```

### 3. 本プロジェクトのインストール

```bash
# プロジェクトをダウンロード
git clone https://github.com/Yesssssbabe/ollama-smart-router.git
cd ollama-smart-router

# 依存関係をインストール
pip install -r requirements.txt

# インストールを確認
python check_env.py
```

---

## 使い方

### コマンドライン（初心者におすすめ）

```bash
# 自動ルーティング（最も簡単）
python -m src "Pythonのクイックソートを書いて"

# インタラクティブモード（ChatGPTのように対話）
python -m src -i

# GPU を強制使用
python -m src "質問" --strategy gpu

# クラウドを強制使用（API キーの設定が必要）
python -m src "複雑な質問" --strategy cloud

# ハードウェア状態を確認
python -m src --status

# 利用可能なモデルを一覧表示
python -m src --list-models
```

### Python コードでの使用

```python
from src.router import SmartRouter

# ルーターを作成
router = SmartRouter()

# 自動ルーティング
result = router.route("Pythonのクイックソートを書いて")
print(result.content)

# どのパスを使用したか確認
print(f"ルーティング先: {result.source}")  # local_gpu / local_cpu / cloud
print(f"所要時間: {result.latency:.2f}秒")
```

### クラウド API の設定（オプション）

**方法 1：環境変数（推奨）**
```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY="your-api-key-here"

# Mac/Linux
export DEEPSEEK_API_KEY="your-api-key-here"
```

**方法 2：設定ファイル**
`config.yaml` を編集：
```yaml
cloud:
  api_key: "your-api-key-here"
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
```

---

## ⚡ 主要機能

| 機能 | 説明 |
|------|------|
| 🎯 **インテリジェントルーティング** | タスクの複雑さを自動分析し、ローカル GPU/CPU/クラウドを自動選択 |
| 🎮 **VRAM 保護** | GPU VRAM をリアルタイム監視し、クラッシュを防止 |
| 💻 **柔軟なフォールバック** | GPU 不足時に自動的に CPU 推論に切り替え |
| ☁️ **クラウドフォールバック** | 複雑なタスクを DeepSeek などの API にシームレスに切り替え |
| 📊 **複雑さ分析** | 簡単/中程度/複雑なタスクを自動識別 |

### ルーティング判定ロジック

```
あなたの入力
      ↓
[複雑さ分析器] タスクの難易度を判定
      ↓
┌─────────────────────────────────────┐
│ 簡単 + GPU VRAM 十分 → ローカル小モデル │
│ 簡単 + GPU VRAM 不足 → ローカル小モデル │
│ 中程度 + GPU VRAM 十分 → ローカル中モデル │
│ 中程度 + GPU VRAM 不足 → ローカル中モデル │
│ 複雑 + API 設定済み → クラウド大モデル   │
│ 複雑 + API なし    → ローカル大モデル   │
└─────────────────────────────────────┘
      ↓
   回答を返す
```

---

## よくある質問

### Q1: `python` が内部コマンドではありませんと表示される？
**A:** Python が PATH に追加されていません。Python を再インストールし、**"Add Python to PATH"** をチェックしてください。

### Q2: `ollama` 接続に失敗すると表示される？
**A:** Ollama が実行中であることを確認：
- Windows: タスクバーに羊驼アイコンがあること
- コマンドラインテスト: `ollama list` がモデルを一覧表示すること

### Q3: モデルが存在しないと表示される？
**A:** 先にモデルをダウンロード：
```bash
ollama pull gemma3:4b    # 必須
ollama pull qwen2.5:7b   # 推奨
```

### Q4: GPU がなくても使えますか？
**A:** **完全に可能です！** GPU がない場合は自動的に CPU が使用されます。速度は少し遅くなります。

### Q5: CPU のみを使用するには？
**A:**
```bash
python -m src "質問" --strategy cpu
```

### Q6: Windows でターミナルを開くには？
**A:**
1. プロジェクトフォルダの空白部分で `Shift` + 右クリック
2. "ここで PowerShell ウィンドウを開く" または "ターミナル" を選択

---

## 📁 プロジェクト構成

```
ollama-smart-router/
├── src/                      # ソースコード
│   ├── router.py            # インテリジェントルーティング核心
│   ├── gpu_monitor.py       # GPU/CPU 監視
│   ├── complexity_analyzer.py # 複雑さ分析
│   └── cli.py               # コマンドラインインターフェース
├── examples/                 # 使用例
├── check_env.py             # 環境確認ツール ⭐
├── install.py               # ワンクリックインストールスクリプト ⭐
├── config.yaml              # 設定ファイル
├── requirements.txt         # 依存関係リスト
├── README.md                # 簡体中文ドキュメント
├── README_EN.md             # 英語ドキュメント
├── README_TW.md             # 繁体中文ドキュメント
├── README_JP.md             # 日本語ドキュメント（本ファイル）
└── README_KR.md             # 韓国語ドキュメント
└── README_ES.md             # スペイン語ドキュメント
```

---

## 🛠️ 高度な設定

### デフォルトモデルの変更

`config.yaml` を編集：
```yaml
models:
  small: { name: "gemma3:4b" }    # 簡単なタスク
  medium: { name: "qwen2.5:7b" }   # 中程度のタスク
  large: { name: "llama3.2:8b" }   # 複雑なタスク
```

### VRAM 閾値の調整

```yaml
gpu_thresholds:
  min_free_vram_gb: 4.0    # これ以下になると CPU に切り替え
  safety_margin_gb: 1.0    # 安全余量
```

---

## 🤝 貢献

Issue と PR を歓迎します！

---

## 📞 作者への連絡

<img src="wechat-qr.jpg" width="200" alt="微信二维码">

**WeChat QR コードをスキャンして、プロジェクトについて相談や改善提案をお送りください**

> 友達追加時の備考：**ollama-smart-router**

---

## 📜 ライセンス

MIT License
