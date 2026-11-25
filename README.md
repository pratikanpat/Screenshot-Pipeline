<div align="center">

# 📸 ScreenshotKB

**Turn your scattered screenshots into a searchable, organized knowledge base.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![100% Local](https://img.shields.io/badge/Privacy-100%25%20Local-green)](README.md)

[Features](#-features) · [How It Works](#-how-it-works) · [Installation](#-installation) · [Usage](#-usage) · [Architecture](#-architecture) · [Contributing](#-contributing)

</div>

---

ScreenshotKB is a **local-first, privacy-respecting** pipeline that automatically indexes your mobile screenshots. Point it at a folder, and it extracts text with OCR, classifies every image with AI, and builds a full-text + semantic search index — all on your machine, with no cloud APIs.

> **Your screenshots never leave your device.**

---

## ✨ Features

- 🔍 **Three search modes** — Keyword (FTS5), Semantic (CLIP), and Hybrid
- 🧠 **AI visual classification** — CLIP zero-shot classifies images without text (faces, maps, screenshots with no words)
- 📂 **50+ categories** — Finance, Social Media platforms, People & Faces, Maps, Gaming, Health, and more
- 🔑 **OCR text extraction** — Tesseract with dark-mode inversion and 2× upscaling pre-processing
- 🗃️ **SQLite + ChromaDB** — fast local databases, no server setup
- 🌐 **Web UI** — Next.js frontend with dark/light mode, search, library browser, detail view
- ⚡ **Idempotent pipeline** — run it 100 times, same result (SHA-256 dedup)
- 🔒 **Read-only** — your original files are never modified, moved, or deleted

---

## 🔧 How It Works

ScreenshotKB runs a **4-stage pipeline** on your screenshot folder:

```
📁 Screenshots Folder
        │
   ① Ingest        — Scan, hash, deduplicate, store metadata
        │
   ② OCR           — Preprocess image → Tesseract → extract text
        │
   ③ Classify      — Keyword rules → CLIP zero-shot → assign category + tags
        │
   ④ Embed         — CLIP image encoder → 512-dim vector → ChromaDB
        │
   🌐 Web UI       — FastAPI + Next.js → Search, Browse, Explore
```

**Classification is two-stage:**
- **Stage 1 — Keyword rules:** 50+ deterministic keyword dictionaries (PhonePe, Instagram, etc.) — fast and 100% accurate for text-heavy screenshots
- **Stage 2 — CLIP zero-shot:** For images with little/no text — the AI visually compares the screenshot against 50 natural-language descriptions ("a portrait photo of a single person's face") and picks the best match

---

## 📋 Requirements

### System Dependencies

| Dependency | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Backend pipeline and API |
| Node.js | 18+ | Frontend (Next.js) |
| Tesseract OCR | 5.x | Text extraction binary |

### Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.115 | REST API framework |
| `uvicorn[standard]` | 0.32 | ASGI server |
| `pillow` | 11.0 | Image processing |
| `pytesseract` | 0.3.13 | Tesseract OCR wrapper |
| `torch` (CPU) | 2.5.1 | CLIP model inference |
| `sentence-transformers` | 3.3.1 | CLIP embeddings (image + text) |
| `chromadb` | 0.5.23 | Vector database (semantic search) |
| `click` | 8.1 | CLI framework |
| `tqdm` | 4.67 | Progress bars |
| `pydantic` | 2.10 | Data validation |
| `python-dotenv` | 1.0 | Environment config |

> **Storage estimate:** ~2 GB for CLIP model cache · ~60 MB per 1,000 screenshots in ChromaDB

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/pratikanpat/Screenshot-Pipeline.git
cd Screenshot-Pipeline
```

---

### 2. Install Tesseract OCR

Tesseract is the OCR binary that reads text from images. **This is a system-level install, not Python.**

**Windows:**
```powershell
winget install UB-Mannheim.TesseractOCR
# After install, add to PATH: C:\Program Files\Tesseract-OCR\
```

**macOS:**
```bash
brew install tesseract
```

**Ubuntu / Debian:**
```bash
sudo apt-get install tesseract-ocr
```

Verify:
```bash
tesseract --version
```

---

### 3. Install Python Dependencies

```bash
# Install all backend dependencies (this takes a few minutes — PyTorch is ~1 GB)
pip install -r requirements.txt
```

> **Note:** `torch` is pinned to the CPU-only build to keep the install lean. If you have an NVIDIA GPU and want CUDA acceleration, replace the torch line in `requirements.txt`:
> ```
> # Remove the CPU line and run:
> pip install torch --index-url https://download.pytorch.org/whl/cu121
> ```

Verify everything installed:
```bash
python -c "import fastapi, PIL, pytesseract, sentence_transformers, chromadb; print('All good!')"
```

---

### 4. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

---

### 5. Configure Your Screenshots Folder

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and set your screenshots folder path:
```env
SCREENSHOT_SOURCE=/path/to/your/screenshots

# Examples:
# Windows: SCREENSHOT_SOURCE=C:\Users\YourName\Pictures\Screenshots
# macOS:   SCREENSHOT_SOURCE=/Users/yourname/Pictures/Screenshots
# Linux:   SCREENSHOT_SOURCE=/home/yourname/Pictures/Screenshots
```

---

## ▶️ Usage

### Step 1 — Run the Pipeline

Process all your screenshots (ingest → OCR → classify → embed):

```bash
python -m backend.run_pipeline process-all
```

Or run each stage individually:

```bash
# 1. Scan and register all screenshots
python -m backend.run_pipeline ingest

# 2. Extract text from every image
python -m backend.run_pipeline ocr

# 3. Classify into categories (Finance, Social, etc.)
python -m backend.run_pipeline classify

# 4. Generate CLIP embeddings for semantic search
python -m backend.run_pipeline embed
```

**Useful flags:**

```bash
# Check current pipeline status
python -m backend.run_pipeline status

# Process only the first 100 images (great for testing)
python -m backend.run_pipeline ocr --limit 100

# Re-classify everything from scratch
python -m backend.run_pipeline classify --force

# Re-generate embeddings (e.g. after adding new screenshots)
python -m backend.run_pipeline embed --force

# Retry images that previously failed OCR
python -m backend.run_pipeline ocr --retry-failed
```

> **First run timing:** OCR is ~1–2 img/sec. Embedding (CLIP) is ~5 img/sec on CPU. For 8,000 images expect ~90 min OCR + ~30 min embedding. Subsequent runs only process new images.

---

### Step 2 — Start the Backend API

```bash
uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

API is live at `http://localhost:8000`  
Interactive docs at `http://localhost:8000/docs`

---

### Step 3 — Start the Web UI

In a **new terminal:**

```bash
cd frontend
npm run dev
```

Open `http://localhost:3000` in your browser.

---

### Running Both Together (optional)

You can use two terminal windows, or if you prefer one command on Unix:

```bash
# Terminal 1
uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2
cd frontend && npm run dev
```

---

## 🏗️ Architecture

```
Screenshot-Knowledge-Base/
│
├── backend/
│   ├── config.py                 # Central config (paths, model names)
│   ├── run_pipeline.py           # CLI entry point (Click commands)
│   │
│   ├── pipeline/
│   │   ├── ingestion.py          # Scan + hash + dedup → images table
│   │   ├── preprocessor.py       # Enhance images before OCR (Pillow)
│   │   ├── ocr.py                # Tesseract OCR → ocr_results table
│   │   ├── classifier.py         # Rules + CLIP → categories + fts_index
│   │   ├── rules.py              # 50+ keyword dictionaries
│   │   ├── embeddings.py         # CLIP encode → ChromaDB + embeddings table
│   │   └── logger.py             # Rotating file loggers
│   │
│   ├── db/
│   │   ├── database.py           # SQLite connection factory
│   │   ├── schema.py             # CREATE TABLE statements
│   │   ├── ocr.py                # OCR read/write helpers
│   │   ├── categories.py         # Category + FTS5 helpers
│   │   └── search.py             # Keyword / hybrid search queries
│   │
│   └── api/
│       ├── main.py               # FastAPI app + CORS + lifespan
│       ├── models.py             # Pydantic response models
│       └── routes/
│           ├── images.py         # GET /images, /images/{id}, /thumbnail
│           ├── search.py         # GET /search (keyword/semantic/hybrid)
│           ├── categories.py     # GET /categories
│           └── process.py        # POST /process (trigger pipeline via API)
│
├── data/
│   ├── library.db                # SQLite database (auto-created)
│   └── chroma/                   # ChromaDB vector index (auto-created)
│
├── frontend/                     # Next.js 15 App Router
│   ├── app/
│   │   ├── page.tsx              # / — Home dashboard
│   │   ├── search/page.tsx       # /search — Results
│   │   ├── library/page.tsx      # /library — Full browser
│   │   └── image/[id]/page.tsx   # /image/{id} — Detail view
│   └── components/
│       ├── AppSidebar.tsx
│       ├── ImageCard.tsx
│       ├── ImageGrid.tsx
│       └── SearchBar.tsx
│
├── scripts/                      # Debug and inspection utilities
├── requirements.txt
└── .env.example
```

### Database Schema (SQLite)

```sql
images          — master registry (one row per screenshot)
ocr_results     — extracted text, confidence, word count
categories      — category, subcategory, tags, classification method
embeddings      — pointer to ChromaDB vector (512-dim CLIP embedding)
fts_index       — FTS5 virtual table (Porter stemmer, full-text search)
```

All child tables use `ON DELETE CASCADE` — removing an image cleans up everything automatically.

### Search Modes

| Mode | How it works | Best for |
|------|-------------|---------|
| **Keyword** | SQLite FTS5 `MATCH` with Porter stemming | Exact words, receipt numbers, names |
| **Semantic** | CLIP text → ChromaDB cosine similarity | Concepts ("payment"), visual content |
| **Hybrid** | Both combined, re-ranked by merged score | Best overall results |

---

## 🎨 Categories

The pipeline classifies screenshots into these categories out of the box:

| Category | Subcategories |
|----------|--------------|
| **Finance** | UPI Transactions, Payment Apps, Receipts & Invoices, Bank Statements, Budgets, Shopping |
| **Social & Content** | Instagram Posts/Chats/Stories, Twitter/X, LinkedIn, YouTube, Reddit, Facebook, Snapchat |
| **Personal** | WhatsApp Chats, Telegram Chats, Calendar & Events, Contacts, Reminders |
| **People & Faces** | Portraits, Group Photos, Profile Pictures |
| **Maps & Places** | Navigation, Food & Restaurants |
| **Technology** | Code & Development, AI & ML, Tutorials, Open Source |
| **Learning** | Courses, Books & Reading, Articles & Blogs, Notes |
| **Media & Entertainment** | Movies & Shows, Music, Gaming |
| **Health & Fitness** | Activity Tracking, Medical |

To extend or modify categories, edit:
- `backend/data/categories.json` — taxonomy definition
- `backend/pipeline/rules.py` — keyword rules per subcategory
- `backend/pipeline/classifier.py` — CLIP label descriptions

---

## 🔌 API Reference

Once the backend is running, full interactive docs are at `http://localhost:8000/docs`.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/images` | GET | Paginated image list with category metadata |
| `/images/{id}` | GET | Full detail: OCR text, category, tags, confidence |
| `/images/{id}/thumbnail` | GET | On-demand JPEG thumbnail (400×400) |
| `/search?q=&mode=` | GET | Search (mode: `keyword`, `semantic`, `hybrid`) |
| `/categories` | GET | Category list with counts |
| `/process/ingest` | POST | Trigger ingestion from the web UI |

---

## ⚙️ Configuration

All config lives in `.env` (copy from `.env.example`):

```env
# Required
SCREENSHOT_SOURCE=/path/to/your/screenshots

# Optional (defaults shown)
DATABASE=data/library.db
CHROMA_DIR=data/chroma
CLIP_MODEL=clip-ViT-B-32
CHECKPOINT_INTERVAL=100
API_HOST=127.0.0.1
API_PORT=8000
```

---

## 🛠️ Troubleshooting

**`TesseractNotFoundError`**
Tesseract binary is not in PATH. Add `C:\Program Files\Tesseract-OCR\` to your system PATH and restart your terminal.

**`ModuleNotFoundError: No module named 'backend'`**
Run the pipeline as a module from the project root:
```bash
# ✅ Correct
python -m backend.run_pipeline ingest

# ❌ Wrong
python backend/run_pipeline.py
```

**ChromaDB or CLIP not available (semantic search skipped)**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers chromadb
```

**Frontend can't reach backend**
Make sure the backend is running on port 8000 before starting the frontend. Check `frontend/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000`.

**SQLite `permission denied` on git add**
The database is locked by a running process. Stop the pipeline/API, then:
```bash
git add README.md requirements.txt  # add specific files, not -A
```

---

## 🤝 Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

```bash
# Fork the repo, then:
git checkout -b feature/your-feature-name
# Make changes
git commit -m "feat: describe your change"
git push origin feature/your-feature-name
# Open a Pull Request
```

**Ideas for contributions:**
- Better OCR with PaddleOCR (multi-language, tables, dense text)
- More category rules or CLIP labels
- Mobile-responsive UI improvements
- Natural language query parsing (LLM integration)
- Export to Notion / Obsidian

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [OpenAI CLIP](https://github.com/openai/CLIP) — vision-language model for semantic understanding
- [sentence-transformers](https://www.sbert.net/) — CLIP Python wrapper
- [ChromaDB](https://www.trychroma.com/) — local vector database
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) — open-source OCR engine
- [FastAPI](https://fastapi.tiangolo.com/) — modern Python web framework
- [Next.js](https://nextjs.org/) — React framework

---

<div align="center">
Built with ❤️ — 100% local, 100% private, 100% free.
</div>
