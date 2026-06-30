# Ollama Smart Router 🧠⚡

지능형 모델 라우터 - 작업 복잡도에 따라 최적의 추론 경로를 자동으로 선택합니다.

로컬 소형 모델로 간단한 작업을 처리하고, 복잡한 작업은 자동으로 대형 모델 또는 클라우드 API로 전환하여 시간과 비용을 절약합니다.

**[简体中文](README.md) | [English](README_EN.md) | [繁體中文](README_TW.md) | [日本語](README_JP.md) | 한국어 | [Español](README_ES.md)**

---

## 📋 목차

- [요구사항](#요구사항)
- [빠른 시작(5분 안에 시작하기)](#빠른-시작5분-안에-시작하기)
- [설치 단계](#설치-단계)
- [사용 방법](#사용-방법)
- [자주 묻는 질문](#자주-묻는-질문)
- [연락처](#연락처)

---

## 요구사항

### ✅ 필수 조건

| 항목 | 요구사항 | 확인 방법 |
|------|------|----------|
| **운영체제** | Windows 10+/macOS/Linux | - |
| **Python** | 3.9 이상 | `python --version` |
| **Ollama** | 설치되어 실행 중 | 작업 표시줄에 라마 아이콘 |
| **메모리** | 최소 8GB(권장 16GB) | - |
| **네트워크** | GitHub 및 PyPI 접근 가능 | 브라우저에서 github.com 접속 |

### ⚠️ 선택 조건(더 강력한 기능)

| 항목 | 설명 |
|------|------|
| **NVIDIA 그래픽 카드** | GPU가 있으면 소형 모델 추론 가속 |
| **클우드 API 키** | DeepSeek/OpenAI 등, 복잡한 작업용 |

---

## 빠른 시작(5분 안에 시작하기)

### 1단계: 환경 확인(30초)

터미널/PowerShell을 열고 실행:

```bash
# Windows
python --version
# Python 3.9.x 이상이 표시되어야 함

# macOS/Linux
python3 --version
```

### 2단계: 프로젝트 다운로드(1분)

**방식 A: git이 있는 경우**
```bash
git clone https://github.com/Yesssssbabe/ollama-smart-router.git
cd ollama-smart-router
```

**방식 B: git이 없는 경우**
1. 페이지의 녹색 버튼 `<> Code` → `Download ZIP` 클릭
2. 원하는 폴터에 압축 해제
3. 압축 해제된 폴터로 이동

### 3단계: 원클릭 설치(2분)

**Windows:**
```powershell
# PowerShell에서
python check_env.py      # 환경 확인
python install.py        # 자동 설치
```

**Mac/Linux:**
```bash
python3 check_env.py     # 환경 확인
python3 install.py       # 자동 설치
```

### 4단계: 테스트 실행(1분)

```bash
# 하드웨어 상태 확인
python -m src --status

# 간단한 테스트
python -m src "안녕하세요, 자기소개 부탁드려요"
```

🎉 **축하합니다!** 응답이 보이면 설치 성공입니다!

---

## 설치 단계(상세版)

### 1. Python 설치

**설치 여부 확인:**
```bash
python --version      # Windows
python3 --version     # Mac/Linux
```

**설치되어 있지 않은 경우:**
- Windows/Mac: [python.org/downloads](https://python.org/downloads)에서 다운로드 및 설치
- **중요**: 설치 시 `Add Python to PATH` 선택

### 2. Ollama 설치

1. [ollama.com](https://ollama.com) 방문
2. 해당 시스템용 설치 패키지 다운로드
3. 설치 후 Ollama 실행(작업 표시줄에 라마 아이콘 표시)
4. 최소 1개 모델 다운로드:
   ```bash
   ollama pull gemma3:4b    # 소형 모델, 필수
   ollama pull qwen2.5:7b   # 중형 모델, 권장
   ```

### 3. 본 프로젝트 설치

```bash
# 프로젝트 다운로드
git clone https://github.com/Yesssssbabe/ollama-smart-router.git
cd ollama-smart-router

# 의존성 설치
pip install -r requirements.txt

# 설치 확인
python check_env.py
```

---

## 사용 방법

### 명령줄(초보자 추천)

```bash
# 자동 라우팅(가장 간단)
python -m src "Python 퀵소트 작성해줘"

# 대화 모드(ChatGPT처럼 대화)
python -m src -i

# GPU 강제 사용
python -m src "질문" --strategy gpu

# 클라우드 강제 사용(API 키 설정 필요)
python -m src "복잡한 질문" --strategy cloud

# 하드웨어 상태 확인
python -m src --status

# 사용 가능한 모델 목록
python -m src --list-models
```

### Python 코드에서 사용

```python
from src.router import SmartRouter

# 라우터 생성
router = SmartRouter()

# 자동 라우팅
result = router.route("Python 퀵소트 작성해줘")
print(result.content)

# 어떤 경로를 사용했는지 확인
print(f"라우팅 경로: {result.source}")  # local_gpu / local_cpu / cloud
print(f"소요 시간: {result.latency:.2f}초")
```

### 클라우드 API 설정(선택)

**방식 1: 환경 변수(권장)**
```bash
# Windows PowerShell
$env:DEEPSEEK_API_KEY="your-api-key-here"

# Mac/Linux
export DEEPSEEK_API_KEY="your-api-key-here"
```

**방식 2: 설정 파일**
`config.yaml` 편집:
```yaml
cloud:
  api_key: "your-api-key-here"
  base_url: "https://api.deepseek.com"
  model: "deepseek-chat"
```

---

## ⚡ 핵심 기능

| 기능 | 설명 |
|------|------|
| 🎯 **지능형 라우팅** | 작업 복잡도를 자동 분석하여 로컬 GPU/CPU/클우드 중 선택 |
| 🎮 **VRAM 보호** | GPU VRAM을 실시간 모니터링하여 충돌 방지 |
| 💻 **유연한 폴back** | GPU 부족 시 자동으로 CPU 추론으로 전환 |
| ☁️ **클우드 폴back** | 복잡한 작업을 DeepSeek 등 API로 원활하게 전환 |
| 📊 **복잡도 분석** | 간단/중간/복잡한 작업을 자동 식별 |

### 라우팅 결정 로직

```
당신의 입력
      ↓
[복잡도 분석기] 작업 난이도 판단
      ↓
┌─────────────────────────────────────┐
│ 간단 + GPU VRAM 충분 → 로컬 소형 모델  │
│ 간단 + GPU VRAM 부족 → 로컬 소형 모델  │
│ 중간 + GPU VRAM 충분 → 로컬 중형 모델  │
│ 중간 + GPU VRAM 부족 → 로컬 중형 모델  │
│ 복잡 + API 설정됨 → 클우드 대형 모델   │
│ 복잡 + API 없음    → 로컬 대형 모델   │
└─────────────────────────────────────┘
      ↓
   답변 반환
```

---

## 자주 묻는 질문

### Q1: `python`이 낶부 명령어가 아니라고 표시됩니다?
**A:** Python이 PATH에 추가되지 않았습니다. Python을 재설치하고, **"Add Python to PATH"**를 선택하세요.

### Q2: `ollama` 연결 실패가 표시됩니다?
**A:** Ollama가 실행 중인지 확인:
- Windows: 작업 표시줄에 라마 아이콘이 있어야 함
- 명령줄 테스트: `ollama list`가 모델을 나열해야 함

### Q3: 모델이 존재하지 않는다고 표시됩니다?
**A:** 먼저 모델을 다운로드:
```bash
ollama pull gemma3:4b    # 필수
ollama pull qwen2.5:7b   # 권장
```

### Q4: GPU 없이도 사용할 수 있나요?
**A:** **완전히 가능합니다!** GPU가 없으면 자동으로 CPU가 사용됩니다. 속도가 조금 느려집니다.

### Q5: CPU만 사용하려면?
**A:**
```bash
python -m src "질문" --strategy cpu
```

### Q6: Windows에서 터미널을 여는 방법?
**A:**
1. 프로젝트 폴터의 빈 공간에서 `Shift` + 우클릭
2. "여기서 PowerShell 창 열기" 또는 "터미널" 선택

---

## 📁 프로젝트 구조

```
ollama-smart-router/
├── src/                      # 소스 코드
│   ├── router.py            # 지능형 라우팅 핵심
│   ├── gpu_monitor.py       # GPU/CPU 모니터링
│   ├── complexity_analyzer.py # 복잡도 분석
│   └── cli.py               # 명령줄 인터페이스
├── examples/                 # 사용 예시
├── check_env.py             # 환경 확인 도구 ⭐
├── install.py               # 원클릭 설치 스크립트 ⭐
├── config.yaml              # 설정 파일
├── requirements.txt         # 의존성 목록
├── README.md                # 중국어 간체 문서
├── README_EN.md             # 영어 문서
├── README_TW.md             # 중국어 번체 문서
├── README_JP.md             # 일본어 문서
├── README_KR.md             # 한국어 문서(본 파일)
└── README_ES.md             # 스페인어 문서
```

---

## 🛠️ 고급 설정

### 기본 모델 수정

`config.yaml` 편집:
```yaml
models:
  small: { name: "gemma3:4b" }    # 간단한 작업
  medium: { name: "qwen2.5:7b" }   # 중간 작업
  large: { name: "llama3.2:8b" }   # 복잡한 작업
```

### VRAM 임계값 조정

```yaml
gpu_thresholds:
  min_free_vram_gb: 4.0    # 이 값 이하면 CPU로 전환
  safety_margin_gb: 1.0    # 안전 여유
```

---

## 🤝 기여

Issue와 PR을 환영합니다!

---

## 📞 저자 연락처

<img src="wechat-qr.jpg" width="200" alt="微信二维码">

**WeChat QR 코드를 스캔하여 프로젝트 상담 및 개선 제안을 본내주세요**

> 친구 추가 시 비고:**ollama-smart-router**

---

## 📜 라이선스

MIT License
