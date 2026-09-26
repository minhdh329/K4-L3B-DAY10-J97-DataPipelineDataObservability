# Day 10 — Tải dependency trước (Mac / Linux / Windows)

> **Luồng làm việc:** tải sẵn **trước giờ lab** → khi có link repo, clone/copy vào → cài **offline-ish** từ cache (không cả lớp đổ lên PyPI cùng lúc).
>
> **Python:** `3.11` – `3.13`

---

## Tổng quan 2 bước

| Bước | Làm khi nào | Việc cần làm |
|------|-------------|--------------|
| **A — Tải trước** | Trước lab (mạng ổn / ở nhà) | Cài `uv`, tải wheel cache + model embedding MiniLM |
| **B — Gắn repo** | Khi GV gửi link GitHub | Clone repo → `uv sync --frozen` (đọc cache sẵn, rất nhanh) |

**Không cần clone repo ở bước A.**

---

## Bước A — Tải trước (chưa cần link repo)

### A1. Cài Python + uv

#### macOS

```bash
# Python 3.12 (Homebrew) — nếu chưa có
brew install python@3.12

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# mở terminal mới, rồi:
uv --version
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip curl

curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"   # hoặc mở terminal mới
uv --version
```

#### Windows (PowerShell — Run as User)

```powershell
# Python 3.12: tải từ https://www.python.org/downloads/ (tick "Add to PATH")

# uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv --version
```

---

### A2. Tạo thư mục cache dùng chung (một lần)

Chọn **một chỗ cố định** trên máy (hoặc USB/NAS cho phòng lab):

#### macOS / Linux

```bash
mkdir -p "$HOME/lab-cache/day10/uv-cache"
mkdir -p "$HOME/lab-cache/day10/huggingface"

export UV_CACHE_DIR="$HOME/lab-cache/day10/uv-cache"
export HF_HOME="$HOME/lab-cache/day10/huggingface"
export TRANSFORMERS_CACHE="$HF_HOME/hub"
export SENTENCE_TRANSFORMERS_HOME="$HF_HOME"
```

Ghi các dòng `export` vào `~/.zshrc` hoặc `~/.bashrc` để không phải gõ lại.

#### Windows (PowerShell — User)

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\lab-cache\day10\uv-cache"
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\lab-cache\day10\huggingface"

[System.Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "$env:USERPROFILE\lab-cache\day10\uv-cache", "User")
[System.Environment]::SetEnvironmentVariable("HF_HOME", "$env:USERPROFILE\lab-cache\day10\huggingface", "User")
[System.Environment]::SetEnvironmentVariable("TRANSFORMERS_CACHE", "$env:USERPROFILE\lab-cache\day10\huggingface\hub", "User")
[System.Environment]::SetEnvironmentVariable("SENTENCE_TRANSFORMERS_HOME", "$env:USERPROFILE\lab-cache\day10\huggingface", "User")
```

Mở **terminal/PowerShell mới** sau khi set biến User.

---

### A3. Tải trước toàn bộ Python packages (nặng nhất — torch, chromadb, …)

Cách nhẹ nhất: tạo **file tạm** chỉ để kéo dependency Day 10, không cần source lab.

#### macOS / Linux

```bash
mkdir -p "$HOME/lab-prefetch/day10" && cd "$HOME/lab-prefetch/day10"

cat > pyproject.toml <<'EOF'
[project]
name = "day10-prefetch"
version = "0.0.0"
requires-python = ">=3.11,<3.14"
dependencies = [
  "chromadb>=1.0.12",
  "datasets>=4.0.0",
  "great-expectations>=1.16.1",
  "langchain>=1.0.0",
  "langchain-anthropic>=0.3.15",
  "langchain-google-genai>=2.0.0",
  "langchain-ollama>=0.3.3",
  "langchain-openai>=1.0.1",
  "pandas>=2.2.2",
  "python-dotenv>=1.0.1",
  "ragas>=0.3.0",
  "requests>=2.32.3",
  "sentence-transformers>=5.0.0",
]
EOF

export UV_HTTP_TIMEOUT=300
uv sync
uv run python -c "import chromadb, great_expectations, sentence_transformers; print('Packages OK')"
```

#### Windows (PowerShell)

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\lab-prefetch\day10" | Out-Null
Set-Location "$env:USERPROFILE\lab-prefetch\day10"

@'
[project]
name = "day10-prefetch"
version = "0.0.0"
requires-python = ">=3.11,<3.14"
dependencies = [
  "chromadb>=1.0.12",
  "datasets>=4.0.0",
  "great-expectations>=1.16.1",
  "langchain>=1.0.0",
  "langchain-anthropic>=0.3.15",
  "langchain-google-genai>=2.0.0",
  "langchain-ollama>=0.3.3",
  "langchain-openai>=1.0.1",
  "pandas>=2.2.2",
  "python-dotenv>=1.0.1",
  "ragas>=0.3.0",
  "requests>=2.32.3",
  "sentence-transformers>=5.0.0",
]
'@ | Set-Content -Encoding utf8 pyproject.toml

$env:UV_HTTP_TIMEOUT = "300"
uv sync
uv run python -c "import chromadb, great_expectations, sentence_transformers; print('Packages OK')"
```

**Pass:** in ra `Packages OK`. Lúc này wheel đã nằm trong `UV_CACHE_DIR` — **bước B gần như không tải lại từ mạng**.

> **GV/TA phòng lab:** copy cả thư mục `lab-cache/day10/` sang USB; học viên trỏ `UV_CACHE_DIR` / `HF_HOME` vào bản copy.

---

### A4. Tải trước model embedding (~90MB)

Lab dùng `sentence-transformers/all-MiniLM-L6-v2`.

#### macOS / Linux

```bash
# Nếu HuggingFace chậm:
# export HF_ENDPOINT=https://hf-mirror.com

uv run python - <<'PY'
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
print("MiniLM cached, max_seq_length =", m.max_seq_length)
PY
```

#### Windows (PowerShell — trong thư mục lab-prefetch/day10)

```powershell
uv run python -c "from sentence_transformers import SentenceTransformer; m=SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('MiniLM cached', m.max_seq_length)"
```

---

### A5. (Tuỳ chọn) Mirror khi PyPI chậm

Tạo file cấu hình uv **một lần**:

| OS | File |
|----|------|
| macOS / Linux | `~/.config/uv/uv.toml` |
| Windows | `%APPDATA%\uv\uv.toml` |

Nội dung (chọn mirror khi cần):

```toml
[pip]
index-url = "https://pypi.org/simple"
extra-index-url = ["https://pypi.tuna.tsinghua.edu.cn/simple"]
```

Tăng timeout (session hiện tại):

```bash
# macOS / Linux
export UV_HTTP_TIMEOUT=300
```

```powershell
# Windows
$env:UV_HTTP_TIMEOUT = "300"
```

---

## Bước B — Khi có link repo (giờ lab)

Thay `<REPO_URL>` bằng link GV gửi, ví dụ:  
`https://github.com/VinUni-AI20k/K4-L3A-Day10-Data-Pipeline-Data-Observability`

### B1. Clone / copy repo

#### macOS / Linux

```bash
cd ~/Documents   # hoặc thư mục bạn muốn
git clone --depth 1 <REPO_URL>
cd K4-L3A-Day10-Data-Pipeline-Data-Observability
```

#### Windows (PowerShell)

```powershell
Set-Location $env:USERPROFILE\Documents
git clone --depth 1 <REPO_URL>
Set-Location K4-L3A-Day10-Data-Pipeline-Data-Observability
```

> Đã tải repo bằng ZIP trên LMS? Giải nén và `cd` vào thư mục — **không bắt buộc git**.

---

### B2. Cài vào repo (dùng cache bước A)

Đảm bảo biến cache vẫn trỏ đúng (`UV_CACHE_DIR`, `HF_HOME`).

#### macOS / Linux / Windows (cùng lệnh)

```bash
uv sync --frozen
uv run python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
```

**Pass:** `Môi trường sẵn sàng`.

---

### B3. `.env` (không tốn mạng)

#### macOS / Linux

```bash
cp .env.example .env
```

#### Windows (PowerShell)

```powershell
Copy-Item .env.example .env
```

Gợi ý giờ lab — chưa cần API key:

```dotenv
LLM_PROVIDER=mock
```

---

## Dự phòng: không dùng được `uv`

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
```

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -c "import chromadb, great_expectations, sentence_transformers; print('Môi trường sẵn sàng')"
```

> Vẫn hưởng lợi từ **bước A4** (MiniLM đã cache trong `HF_HOME`).

---

## Checklist

**Trước lab (bước A)**

- [ ] Python 3.11–3.13 + `uv`
- [ ] `UV_CACHE_DIR` / `HF_HOME` đã set (mac / linux / win)
- [ ] Prefetch packages → `Packages OK`
- [ ] MiniLM cached

**Có link repo (bước B)**

- [ ] Clone hoặc giải nén ZIP
- [ ] `uv sync --frozen` → `Môi trường sẵn sàng`
- [ ] `cp .env.example .env` (hoặc `Copy-Item` trên Windows)

---

## Trong giờ lab — tránh nghẽn

| Nên | Tránh |
|-----|--------|
| Làm xong bước A trước | Cả lớp `pip install -U` cùng lúc |
| `uv sync --frozen` | Resolve dependency lại không cần thiết |
| `LLM_PROVIDER=mock` lúc test pipeline | Pull Ollama / model LLM lớn |
| Dùng cache USB của TA | Tải lại MiniLM mỗi lần chạy embedding |

---

## Lỗi thường gặp

| Triệu chứng | Cách xử lý |
|-------------|------------|
| `ModuleNotFoundError: core` | Trong repo: `uv sync --frozen` hoặc `pip install -e .` |
| `uv sync` vẫn tải mạng lâu | Kiểm tra `UV_CACHE_DIR` có trỏ cache bước A |
| HuggingFace timeout | `HF_ENDPOINT=https://hf-mirror.com` rồi chạy lại A4 |
| Windows không nhận `uv` | Mở PowerShell mới sau khi cài uv |
