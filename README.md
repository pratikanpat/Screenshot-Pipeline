<div align="center">

# 📸 Screenshot Knowledge Base

**Turn your screenshot folder into a fully searchable, auto-organised knowledge library.**

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org)
[![SQLite](https://img.shields.io/badge/SQLite-FTS5-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Drop a folder of screenshots → OCR extracts every word → CLIP understands what's in each image → keyword & semantic search just works.
**100% free. 100% local. No cloud. No API keys. No subscriptions.**

</div>

---

## 📋 Table of Contents

- [What This Does](#-what-this-does)
- [How It Works](#-how-it-works)
- [Prerequisites](#-prerequisites)
- [Where to Run Commands](#-where-to-run-commands)
- [Installation — Step by Step](#-installation--step-by-step)
- [Running the App](#-running-the-app)
- [Using the App](#-using-the-app)
- [CLI Reference](#-cli-reference)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)
- [Configuration](#-configuration)
- [Troubleshooting](#-troubleshooting)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 What This Does

| Capability | Detail |
|---|---|
| 🔍 **Keyword Search** | Type `"upi payment"` → instantly see every screenshot containing those words |
| 🧠 **Semantic Search** | Type `"money transactions"` → finds receipt screenshots even if those exact words never appear |
| 🗂️ **Auto-Organisation** | Every screenshot is classified into categories: Finance, Technology, Social, Learning, Personal… |
| 📝 **OCR** | Text is extracted from every screenshot using PaddleOCR (best-in-class for phone screenshots) |
| 🌐 **Web Interface** | A clean dark-mode web app to browse, search and read OCR text |
| 🔒 **Private by Design** | Everything runs on your own machine — your screenshots never leave your computer |

---

## ⚙️ How It Works

```
Your Screenshot Folder
        │
        ▼
  ┌─────────────┐
  │  Ingestion  │  Scan files, compute SHA-256 hash (dedup + resume)
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │     OCR     │  PaddleOCR (primary) → Tesseract (fallback if low confidence)
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │  Classifier │  CLIP zero-shot + keyword rules → category, subcategory, tags
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │  Embeddings │  CLIP image vectors stored in ChromaDB (powers semantic search)
  └──────┬──────┘
         │
  ┌──────▼──────────────────────────────┐
  │  SQLite + FTS5  │  ChromaDB         │
  │  (keyword search)  (semantic search)│
  └──────┬──────────────────────────────┘
         │
  ┌──────▼──────┐
  │  FastAPI    │  REST API on http://localhost:8000
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │  Next.js    │  Web UI on http://localhost:3000
  └─────────────┘
```

---

## 🖥️ Prerequisites

Install these before starting. Click each link for the official download page.

| Tool | Minimum Version | Download |
|---|---|---|
| **Python** | 3.11+ | [python.org/downloads](https://www.python.org/downloads/) |
| **Node.js** | 18+ | [nodejs.org](https://nodejs.org/) |
| **Tesseract OCR** | 5.x | [UB Mannheim installer (Windows)](https://github.com/UB-Mannheim/tesseract/wiki) |
| **Git** | any | [git-scm.com](https://git-scm.com/) |

### Verify your installs

Open a terminal and run:

```bash
python --version       # Should print Python 3.11.x or higher
node --version         # Should print v18.x or higher
npm --version          # Should print 9.x or higher
tesseract --version    # Should print tesseract 5.x.x
git --version          # Should print git version 2.x
```

> **Windows users:** If `tesseract` is not found, add `C:\Program Files\Tesseract-OCR` to your system PATH, or the OCR engine will auto-detect it.

---

## 🖱️ Where to Run Commands

All commands in this guide are run in a **terminal (command line)**. Here are three ways to open one:

### Option A — VS Code Integrated Terminal ✅ Recommended

1. Open VS Code
2. Open the project folder: **File → Open Folder → Screenshot-Knowledge-Base**
3. Press `` Ctrl + ` `` (backtick) to open the terminal
4. The terminal opens **already inside the project folder** — no `cd` needed

### Option B — Windows PowerShell

1. Press `Win + R`, type `powershell`, press Enter
2. Navigate to the project:
   ```powershell
   cd "C:\Users\YourName\Documents\Screenshot-Knowledge-Base"
   ```

### Option C — Windows Terminal / CMD

1. Open Windows Terminal (search it in Start Menu)
2. Navigate to the project:
   ```cmd
   cd C:\Users\YourName\Documents\Screenshot-Knowledge-Base
   ```

> **Important:** You will need **two terminal windows open at the same time** when running the full app — one for the Python backend and one for the Next.js frontend.

---

## 📦 Installation — Step by Step

### Step 1 — Clone the Repository

```bash
git clone https://github.com/pratikanpat/Screenshot-Pipeline.git
cd Screenshot-Pipeline
```

> **Alternative:** If you downloaded a ZIP, extract it and open that folder in your terminal.

---

### Step 2 — Create a Python Virtual Environment

A virtual environment keeps this project's dependencies isolated from your system Python.

```bash
# Create the virtual environment
python -m venv .venv
```

**Activate it** (you must do this every time you open a new terminal for this project):

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

You will see `(.venv)` appear at the start of your terminal prompt — that means it's active.

---

### Step 3 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs: PaddleOCR, Tesseract bindings, CLIP (sentence-transformers), ChromaDB, FastAPI, Pillow, and all other dependencies.

> ⚠️ **This takes 5–10 minutes** on first run. PyTorch (~800 MB) and PaddleOCR (~200 MB) are large packages. Let it finish.

> 💡 **Low disk space?** The minimum install (Tesseract-only, no CLIP/ChromaDB) uses ~200 MB. Comment out the `paddlepaddle`, `paddleocr`, `torch`, `sentence-transformers`, and `chromadb` lines in `requirements.txt` — keyword search will still work, semantic search won't.

---

### Step 4 — Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

> This installs Next.js and all UI dependencies into `frontend/node_modules/`. Takes ~1 minute.

---

### Step 5 — Verify Everything Works

```bash
# Check Python can find key packages
python -c "import fastapi; import PIL; print('Python deps OK')"

# Check Tesseract
tesseract --version

# Check Node
node --version
```

All three should print without errors.

---

## 🚀 Running the App

You need **two terminals** running side by side.

### Terminal 1 — Python Backend (API + Pipeline)

```bash
# 1. Activate your virtual environment first
.venv\Scripts\Activate.ps1        # Windows
# source .venv/bin/activate        # macOS/Linux

# 2. Run the full pipeline on your screenshots
#    Replace the path with your actual screenshots folder
python -m backend.run_pipeline process-all --source "C:\Users\Pratik\Pictures\MobScreenshots"

# 3. After indexing is done, start the API server
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now running at **http://localhost:8000**

---

### Terminal 2 — Next.js Frontend

```bash
cd frontend
npm run dev
```

The web app is now running at **http://localhost:3000**

---

### Open the App

| URL | What you get |
|---|---|
| **http://localhost:3000** | Web app (home, search, library, image detail) |
| **http://localhost:8000** | API info JSON |
| **http://localhost:8000/docs** | Interactive API explorer (Swagger UI) |
| **http://localhost:8000/redoc** | API docs (ReDoc) |

---

## 📖 Using the App

### For New Users — First Time Setup

1. **Index your screenshots** (run this once, takes 10–30 min for 8,000+ images):
   ```bash
   python -m backend.run_pipeline process-all --source "C:\path\to\your\screenshots"
   ```

2. **Watch the progress** — it prints a live progress bar:
   ```
   Ingest: 100%|████████████| 8616/8616 [02:14<00:00, 64.1img/s]
   OCR:    100%|████████████| 8616/8616 [18:40<00:00,  7.7img/s]
   Classify: 100%|██████████| 8616/8616 [04:22<00:00, 32.8img/s]
   ```

3. **If it gets interrupted**, just run the same command again — it resumes exactly where it stopped (SHA-256 based deduplication).

4. **Open http://localhost:3000** and start searching!

---

### Search

**Keyword Search** — finds screenshots where those exact words appear in the image text:
```
invoice april 2025
python error traceback
upi payment successful
```

**Semantic Search** — finds screenshots by meaning (requires CLIP/ChromaDB installed):
```
money transactions          → finds receipts even without the word "receipt"
coding tutorials            → finds code screenshots
motivational content        → finds quote screenshots
```

**Hybrid Search** — combines both for best results.

---

### Browse by Category

The Library page organises your screenshots into:

```
Technology      → Code, AI, Open Source, Tutorials
Finance         → Receipts, Bank Statements, UPI, Shopping
Social & Content→ LinkedIn, Twitter/X, Instagram, YouTube, Quotes
Learning        → Articles, Notes, Books, Courses
Personal        → Chats, Reminders, Calendar, Contacts
Maps & Places   → Navigation, Locations
Media & Entertainment → Movies, Music, Gaming
```

---

### Image Detail Page

Click any screenshot to see:
- Full-resolution original image
- All extracted OCR text (with copy button)
- Category, subcategory, content type
- Tags (each tag is a clickable search link)
- OCR confidence, engine used, word count
- File metadata (date, dimensions, size)

---

## 🛠️ CLI Reference

All commands use `python -m backend.run_pipeline`. Run from the project root with the venv active.

### `ingest` — Scan and register screenshots

```bash
python -m backend.run_pipeline ingest --source "C:\path\to\screenshots"

# Options:
#   --source PATH    Folder containing screenshots (default: ~/Pictures/MobScreenshots)
#   --limit  N       Only process first N files (useful for testing)
#   --db     PATH    Custom database path (default: data/library.db)
```

### `ocr` — Extract text from images

```bash
python -m backend.run_pipeline ocr

# Options:
#   --limit N          Process N images
#   --retry-failed     Retry previously failed images
#   --force            Re-run OCR on all images (overwrites existing results)
#   --db PATH          Custom database path
```

### `classify` — Auto-categorise screenshots

```bash
python -m backend.run_pipeline classify

# Options:
#   --limit N     Classify N images
#   --force       Re-classify already-classified images
#   --db PATH     Custom database path
```

### `embed` — Generate CLIP vectors for semantic search

```bash
python -m backend.run_pipeline embed

# Options:
#   --limit N     Embed N images
#   --force       Re-embed already embedded images
#   --db PATH     Custom database path
```

### `process-all` — Run the full pipeline in one command ✅

```bash
python -m backend.run_pipeline process-all --source "C:\path\to\screenshots"

# Options:
#   --source PATH    Screenshot folder
#   --limit  N       Limit per stage (good for testing: --limit 50)
#   --db     PATH    Custom database path
```

### `status` — Check pipeline progress

```bash
python -m backend.run_pipeline status

# Output example:
# Total images   : 8,616
# Classified     : 8,214
# Pending        : 402
# Failed         : 0
```

---

## 🌐 API Reference

The API runs at `http://localhost:8000`. Full interactive docs at `/docs`.

### Search

```
GET /search?q=<query>&mode=keyword|semantic|hybrid&limit=20&offset=0
```

```bash
# Examples
curl "http://localhost:8000/search?q=upi+payment&mode=keyword"
curl "http://localhost:8000/search?q=code+tutorials&mode=semantic"
curl "http://localhost:8000/search?q=github&mode=hybrid&limit=10"
```

**Response:**
```json
{
  "query": "upi payment",
  "mode": "keyword",
  "total": 14,
  "results": [
    {
      "image_id": 423,
      "filename": "Screenshot_20261101-142301.png",
      "category": "Finance",
      "subcategory": "UPI Transactions",
      "tags": ["upi", "payment", "gpay"],
      "snippet": "Payment <b>UPI</b> successful ₹500 to...",
      "score": 8.42
    }
  ],
  "time_ms": 12.4
}
```

### Images

```
GET /images                    → paginated list
GET /images/{id}               → full detail + OCR text
GET /images/{id}/thumbnail     → JPEG thumbnail (400×400, letterboxed)
GET /images/{id}/file          → original file
```

### Categories

```
GET /categories                → all categories with counts
GET /categories/tree           → nested category tree
GET /categories/{name}/images  → images in a category
```

### Pipeline

```
GET  /process/status           → current pipeline state
POST /process/start            → start pipeline in background
```

```bash
# Start pipeline via API
curl -X POST http://localhost:8000/process/start \
  -H "Content-Type: application/json" \
  -d '{"source": "C:\\Users\\Pratik\\Pictures\\MobScreenshots", "steps": ["ingest","ocr","classify","embed"]}'
```

---

## 📂 Project Structure

```
Screenshot-Knowledge-Base/
│
├── backend/                        # Python backend
│   ├── config.py                   # All paths, settings, thresholds
│   ├── run_pipeline.py             # CLI entry point (ingest/ocr/classify/embed)
│   │
│   ├── pipeline/                   # Processing stages
│   │   ├── ingestion.py            # File scan, SHA-256, metadata
│   │   ├── preprocessor.py         # Image enhancement before OCR
│   │   ├── ocr.py                  # PaddleOCR + Tesseract fallback
│   │   ├── classifier.py           # CLIP zero-shot classification
│   │   ├── rules.py                # Keyword rule engine
│   │   ├── embeddings.py           # CLIP vectors → ChromaDB
│   │   └── logger.py               # Rotating file + console logging
│   │
│   ├── db/                         # Database layer
│   │   ├── schema.py               # SQLite DDL (tables, FTS5, indexes)
│   │   ├── database.py             # Connection factory (WAL, FK, pragma)
│   │   ├── ocr.py                  # OCR result read/write
│   │   ├── categories.py           # Category + FTS5 operations
│   │   └── search.py               # Keyword + hybrid search queries
│   │
│   ├── api/                        # FastAPI application
│   │   ├── main.py                 # App setup, CORS, lifespan
│   │   ├── models.py               # Pydantic response schemas
│   │   └── routes/
│   │       ├── search.py           # GET /search
│   │       ├── images.py           # GET /images, thumbnails
│   │       ├── categories.py       # GET /categories
│   │       └── process.py          # POST /process/start
│   │
│   └── data/
│       └── categories.json         # Editable category tree
│
├── frontend/                       # Next.js 15 web app
│   ├── app/
│   │   ├── layout.tsx              # Root layout, navbar, fonts
│   │   ├── page.tsx                # Home: search + stats + categories
│   │   ├── search/page.tsx         # Search results grid
│   │   ├── library/page.tsx        # Category browser + sidebar
│   │   └── image/[id]/page.tsx     # Image detail + OCR text
│   ├── components/
│   │   ├── SearchBar.tsx           # Search input (⌘K shortcut, mode toggle)
│   │   ├── ImageCard.tsx           # Thumbnail + category badge + tags
│   │   ├── ImageGrid.tsx           # Masonry grid with skeleton loading
│   │   ├── Sidebar.tsx             # Category tree navigation
│   │   └── Navbar.tsx              # Top navigation bar
│   └── lib/
│       └── api.ts                  # Typed fetch client for the backend
│
├── data/                           # Runtime data (not committed)
│   ├── library.db                  # SQLite database (images + OCR + FTS5)
│   ├── chroma/                     # ChromaDB vector store
│   └── logs/                       # Pipeline logs
│
├── scripts/                        # Legacy/diagnostic scripts
├── requirements.txt                # Python dependencies
├── .gitignore
└── README.md
```

---

## ⚙️ Configuration

All settings live in `backend/config.py`. You can override them by editing that file directly — no environment variables required for a local install.

| Setting | Default | Description |
|---|---|---|
| `DEFAULT_SOURCE` | `~/Pictures/MobScreenshots` | Default screenshot folder |
| `DATABASE` | `data/library.db` | SQLite database path |
| `CHROMA_DIR` | `data/chroma/` | ChromaDB vector store |
| `LOGS_DIR` | `data/logs/` | Log file directory |
| `OCR_CONFIDENCE_THRESHOLD` | `50` | Below this, Tesseract fallback kicks in |
| `OCR_MIN_WORDS` | `3` | Below this word count, also try fallback |
| `PADDLE_LANG` | `en` | PaddleOCR language (`en`, `ch`, `hi`) |
| `CLIP_MODEL` | `clip-ViT-B-32` | CLIP model for embeddings + classification |
| `CHECKPOINT_INTERVAL` | `50` | Commit to DB every N images |
| `THUMBNAIL_SIZE` | `(400, 400)` | Thumbnail dimensions in pixels |
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8000` | API server port |

### Custom categories

Edit `backend/data/categories.json` to add your own categories:

```json
{
  "Work": ["Meetings", "Projects", "Emails"],
  "Health": ["Fitness", "Nutrition", "Medical"],
  "Technology": ["Code & Development", "AI & Machine Learning"]
}
```

The rule engine (`backend/pipeline/rules.py`) can also be extended with your own keywords.

---

## 🔧 Troubleshooting

### "tesseract is not installed or it's not in your PATH"

**Windows:** Install Tesseract from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki), then either:
- Add `C:\Program Files\Tesseract-OCR` to your Windows PATH, or
- The app will auto-detect it at that path on Windows

**macOS:** `brew install tesseract`

**Linux:** `sudo apt install tesseract-ocr`

---

### "ModuleNotFoundError: No module named 'paddleocr'"

PaddleOCR didn't install correctly (common on some Python versions). The app will automatically fall back to Tesseract-only mode and still work. To fix:

```bash
pip install paddlepaddle paddleocr
```

---

### "Cannot connect to backend" in the web app

The FastAPI server isn't running. In Terminal 1, make sure this is running:

```bash
uvicorn backend.api.main:app --reload
```

---

### Pipeline stopped halfway through

Just run the same command again:

```bash
python -m backend.run_pipeline process-all --source "C:\path\to\screenshots"
```

It will skip already-processed images (SHA-256 dedup) and continue from where it stopped.

---

### "No module named 'backend'"

You're running the command from the wrong directory. Make sure you're in the project root (where `backend/` folder is):

```bash
# You should see: backend/  frontend/  data/  requirements.txt  README.md
ls   # macOS/Linux
dir  # Windows
```

If not, `cd` to the project root first.

---

### Semantic search returns no results

ChromaDB embeddings haven't been generated yet. Run:

```bash
python -m backend.run_pipeline embed
```

---

### Frontend won't start — "npm: command not found"

Node.js isn't installed. Download it from [nodejs.org](https://nodejs.org/), install, then restart your terminal.

---

## 🗺️ Roadmap

| Version | Features |
|---|---|
| **v1.0** ✅ | OCR pipeline, keyword search (FTS5), auto-categorisation, REST API, web UI |
| **v1.1** 🔄 | Semantic search (CLIP + ChromaDB), hybrid search, duplicate detection UI |
| **v2.0** 📋 | Natural language queries via local LLM (Ollama), "connections" between screenshots |
| **v2.1** 📋 | Desktop app (Tauri), one-click installer for non-technical users |
| **v3.0** 📋 | Multi-user support, collection sharing, mobile-friendly UI |

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. **Fork** the repository on GitHub
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Screenshot-Pipeline.git
   ```
3. **Create a branch** for your feature:
   ```bash
   git checkout -b feature/my-feature-name
   ```
4. **Make your changes**, commit them:
   ```bash
   git add .
   git commit -m "feat: add my feature"
   ```
5. **Push** and open a Pull Request:
   ```bash
   git push origin feature/my-feature-name
   ```

### Commit message format

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add natural language search
fix: handle corrupt image files gracefully
docs: update installation guide
refactor: split classifier into rule and CLIP modules
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for full text.

```
Copyright (c) 2026 Pratik Anpat

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software.
```

---

<div align="center">

Built with 💙 by [Pratik Anpat](https://github.com/pratikanpat)

**[⭐ Star this repo](https://github.com/pratikanpat/Screenshot-Pipeline)** if it's useful to you!

</div>
