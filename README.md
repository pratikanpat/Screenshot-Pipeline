# Screenshot Knowledge Base

> **Turn your screenshot folder into a searchable, auto-organised knowledge library.**
> Drop screenshots in → OCR extracts text → CLIP classifies content → keyword & semantic search just works.

---

## ✨ Features

| Feature | Detail |
|---|---|
| 📷 **OCR** | PaddleOCR (primary) + pytesseract fallback, confidence-gated |
| 🔍 **Keyword search** | SQLite FTS5 with Porter stemmer — instant, zero infrastructure |
| 🧠 **Semantic search** *(v2)* | CLIP embeddings in ChromaDB — natural language queries |
| 🗂️ **Auto-classification** | CLIP zero-shot + rule engine across 8 top-level categories |
| 🖥️ **REST API** | FastAPI + uvicorn, fully typed with Pydantic v2 |
| ⚛️ **Frontend** *(v2)* | Next.js 15 App Router with live search |
| 🗄️ **Portable DB** | Single SQLite file — copy the repo, everything moves with it |

---

## 🚀 Quick Start

```bash
# 1 — clone & install Python deps
git clone https://github.com/pratikanpat/Screenshot-Pipeline.git
cd Screenshot-Pipeline
pip install -r requirements.txt

# 2 — index your screenshots (defaults to ~/Pictures/MobScreenshots)
python -m backend.pipeline.ingest --source /path/to/screenshots

# 3 — start the API
uvicorn backend.api.main:app --reload
```

Then open <http://localhost:8000/docs> for the interactive API explorer.

---

## 🛠️ Full Setup

### Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.13 |
| Node.js | 24 |
| Tesseract OCR | 5.x (`tesseract --version`) |
| Git | any recent |

### 1 · Clone

```bash
git clone https://github.com/pratikanpat/Screenshot-Pipeline.git
cd Screenshot-Pipeline
```

### 2 · Python environment

```bash
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

> **Note:** `torch` is pinned to the CPU-only wheel.  For GPU support replace
> the `torch` line in `requirements.txt` with the appropriate CUDA wheel.

### 3 · Environment variables (optional)

Copy `.env.example` to `.env` and edit as needed:

```dotenv
SOURCE_DIR=C:\Users\You\Pictures\Screenshots
API_HOST=0.0.0.0
API_PORT=8000
PADDLE_LANG=en
CLIP_MODEL=clip-ViT-B-32
```

### 4 · Frontend *(v2)*

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

---

## 📖 Usage

### Index screenshots

```bash
# Default source (~/Pictures/MobScreenshots)
python -m backend.pipeline.ingest

# Custom source
python -m backend.pipeline.ingest --source D:\MyScreenshots

# Dry-run (discover files, no DB writes)
python -m backend.pipeline.ingest --dry-run
```

### Search via API

```bash
# Keyword search
curl "http://localhost:8000/api/search?q=invoice+april"

# List images by category
curl "http://localhost:8000/api/images?category=Finance"

# Get a single image with OCR text
curl "http://localhost:8000/api/images/42"
```

### API docs

| URL | Description |
|---|---|
| `/docs` | Swagger UI |
| `/redoc` | ReDoc |
| `/openapi.json` | Raw schema |

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| OCR | PaddleOCR 2.8 · pytesseract 0.3 |
| Embeddings | CLIP (`clip-ViT-B-32`) via sentence-transformers |
| Vector store | ChromaDB 0.5 |
| Keyword search | SQLite FTS5 (Porter + unicode61) |
| Database | SQLite 3 (WAL mode, single file) |
| Backend | FastAPI 0.115 · uvicorn 0.32 · Pydantic v2 |
| Frontend | Next.js 15 App Router · TypeScript |
| Image processing | Pillow 11 |

---

## 📂 Repository Layout

```
Screenshot-Knowledge-Base/
├── backend/
│   ├── config.py          # all paths & settings
│   ├── data/
│   │   └── categories.json
│   ├── db/
│   │   ├── schema.py      # DDL — tables, FTS5, indexes
│   │   └── database.py    # connection factory
│   ├── pipeline/          # ingest → OCR → classify → embed  (batch 2+)
│   └── api/               # FastAPI routers                   (batch 3+)
├── frontend/              # Next.js app                       (batch 4+)
├── data/                  # runtime data (gitignored except .gitkeep)
│   ├── library.db         # SQLite knowledge base
│   ├── chroma/            # ChromaDB vector store
│   └── logs/
├── requirements.txt
└── README.md
```

---

## 🗺️ Roadmap

- [x] **Batch 1** — Scaffold, config, DB schema
- [ ] **Batch 2** — Ingestion pipeline (hash → OCR → thumbnail)
- [ ] **Batch 3** — Classification (CLIP + rules) + FTS5 indexing
- [ ] **Batch 4** — FastAPI REST endpoints
- [ ] **Batch 5** — Next.js frontend, keyword search UI
- [ ] **Batch 6** — Semantic search (ChromaDB + CLIP embeddings)
- [ ] **Batch 7** — Natural language query rewriting (v2)

---

## 📄 License

MIT © 2026 Pratik Anpat.  See [LICENSE](LICENSE).
