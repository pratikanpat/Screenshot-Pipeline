# ScreenshotKB — Developer Documentation

> **A private visual knowledge base that turns scattered screenshots into a searchable, organized archive.**
> 100% local · 100% free · No cloud APIs · Windows / Python 3.13 / SQLite

---

## Table of Contents

1. [What is ScreenshotKB?](#1-what-is-screenshotkb)
2. [Architecture Overview](#2-architecture-overview)
3. [The 6 Pipeline Stages — Step by Step](#3-the-6-pipeline-stages)
4. [Database Schema — Every Table Explained](#4-database-schema)
5. [Technology Map — What Each Tool Does Here](#5-technology-map)
6. [File & Folder Structure with Connections](#6-file--folder-structure)
7. [How to Run — All Commands](#7-how-to-run)
8. [Current State of the Project](#8-current-state)
9. [Design System & Frontend](#9-design-system--frontend)
10. [Errors Encountered & Fixes](#10-errors--fixes)
11. [Roadmap](#11-roadmap)

---

## 1. What is ScreenshotKB?

ScreenshotKB is a **private, local-first visual archive** for your phone screenshots. You point it at a folder of screenshots (`C:\Users\Pratik\Pictures\MobScreenshots`) and it:

1. Scans every image file and records it in a SQLite database
2. Deduplicates by content hash (never re-processes the same file twice)
3. Runs OCR (Optical Character Recognition) to extract all visible text
4. Classifies each screenshot into a category (Finance, Social, Technology, etc.)
5. Builds a full-text search index so you can search by any word in any screenshot
6. Generates CLIP AI embeddings so you can search by meaning ("show me payment screenshots") even when the word doesn't appear literally
7. Serves a web UI at `http://localhost:3000` where you can browse, search, and explore your screenshots

**Everything runs on your machine. No internet required after setup.**

---

## 2. Architecture Overview

```
C:\Users\Pratik\Pictures\MobScreenshots\
         (source screenshots — NEVER modified)
                    │
                    ▼
        ┌─────────────────────┐
        │   run_pipeline.py   │  ← CLI entry point (Click commands)
        │   (ingest/ocr/      │
        │  classify/embed)    │
        └─────────┬───────────┘
                  │
        ┌─────────▼───────────────────────────────┐
        │              pipeline/                  │
        │  ingestion.py → ocr.py → classifier.py  │
        │  preprocessor.py  rules.py  embeddings.py│
        └─────────┬───────────────────────────────┘
                  │ reads/writes
        ┌─────────▼───────────────────────────────┐
        │          data/library.db (SQLite)        │
        │  images | ocr_results | categories       │
        │  embeddings | fts_index (FTS5)           │
        └─────────┬───────────────────────────────┘
                  │ also writes to
        ┌─────────▼───────────┐
        │   data/chroma/      │  ← ChromaDB (8,615 CLIP vectors)
        └─────────────────────┘
                  │
        ┌─────────▼───────────┐
        │  backend/api/       │  ← FastAPI + Uvicorn (port 8000)
        │  main.py + routes/  │
        └─────────┬───────────┘
                  │ HTTP REST API
        ┌─────────▼───────────┐
        │  frontend/          │  ← Next.js 16 (port 3000)
        │  (React + Tailwind) │
        └─────────────────────┘
```

---

## 3. The 6 Pipeline Stages

### Stage 1 — Scan (`ingestion.py::scan_folder`)

**What it does:**
Walks the directory `C:\Users\Pratik\Pictures\MobScreenshots` recursively. Filters files by extension: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.gif`. Returns a sorted `list[Path]`.

**What data flows in:** A folder path (string)
**What data flows out:** `list[Path]` — absolute paths to all image files found

**Key code:**
```python
SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}
paths = sorted(p for p in source.rglob("*") if p.suffix.lower() in SUPPORTED)
```

No database access in this step — it's just filesystem walking.

---

### Stage 2 — Hash & Dedup (`ingestion.py::calculate_sha256` + `run_ingestion`)

**What it does:**
For every file from Stage 1:
1. Reads the file in **1 MB chunks** using `hashlib.sha256`
2. Produces a 64-character hex string (e.g. `a3f9b2c1...`) — the SHA-256 fingerprint
3. Checks the `images` table: `SELECT id FROM images WHERE sha256 = ?`
4. If found → skips (counted as "skipped") — no duplicate records
5. If new → extracts metadata:
   - File modification time (mtime) in seconds and nanoseconds
   - Date from filename using regex `\d{4}-\d{2}-\d{2}` (e.g. `Screenshot_2024-03-15_...`)
   - Width/height using `PIL.Image.open(path).size`
6. Inserts one row into the `images` table with `status = 'pending'`

**What data flows in:** `list[Path]` from Stage 1
**What data flows out:** Rows in the `images` table with `status='pending'`

**Files involved:**
- `backend/pipeline/ingestion.py` — does the work
- `backend/db/database.py` — provides the SQLite connection
- `backend/db/schema.py` — defines the `images` table DDL

---

### Stage 3 — OCR (`pipeline/ocr.py` + `pipeline/preprocessor.py`)

**What it does:**
Queries `images` where `status = 'pending'` (or `'error'` if `--retry-failed`). For each image:

**Sub-step A — Image Preprocessing (`preprocessor.py`):**
1. Opens the image with Pillow
2. Upscales by 2× using `Image.LANCZOS` (makes small text bigger for OCR)
3. Sharpens using `ImageFilter.SHARPEN`
4. Checks if the image is dark-mode (mean pixel brightness < 100) → if yes, inverts colors (dark-mode text becomes black on white)
5. Converts to grayscale

**Sub-step B — Tesseract OCR:**
1. Calls `pytesseract.image_to_data(enhanced_img, config='--oem 3 --psm 6')`
   - `--oem 3` = use LSTM neural network (most accurate)
   - `--psm 6` = assume a uniform block of text
2. Gets back a dict with per-word `text` and `conf` (confidence 0–100)
3. Filters out words with confidence < 50 or empty strings
4. Counts words: if < 3 words found → stores empty string (image has no readable text)
5. Calculates mean confidence across all accepted words

**Writes to database:**
- `ocr_results` table: `extracted_text`, `confidence`, `engine='tesseract'`, `word_count`, `processed_at`
- Updates `images.status` → `'ocr_done'`

**Files involved:**
- `backend/pipeline/ocr.py` — orchestrates OCR
- `backend/pipeline/preprocessor.py` — image enhancement (Pillow only, no DB)
- `backend/db/ocr.py` — `get_pending_images()` and `save_ocr_result()`

---

### Stage 4 — Classify (`pipeline/classifier.py` + `pipeline/rules.py`)

**What it does:**
Queries `images JOIN ocr_results` for all images with OCR text but no category yet.

**Two-stage classification:**

**Stage 4A — Rule Engine (`rules.py::classify_by_rules`):**
Checks the OCR text against 50+ keyword dictionaries. These are deterministic:
```python
PAYMENT_APPS_KEYWORDS = ["phonepe", "gpay", "google pay", "paytm", "mobikwik", "upi", ...]
INSTAGRAM_CHAT_KEYWORDS = ["instagram", "direct", "message request", "seen", ...]
```
If a keyword set matches → assigns category/subcategory directly with `confidence = 0.95`, `method = 'rule_based'`.

**Stage 4B — CLIP Zero-Shot (`classifier.py::_clip_classify`):**
If NO rule matched (image had unusual/no text):
1. Opens the image with Pillow → converts to RGB
2. Calls `model.encode(image)` → 512-dimensional float array (the visual embedding)
3. Calls `model.encode(label_text)` for each of 50 natural-language descriptions (e.g. "a PhonePe payment confirmation screen")
4. Computes cosine similarity between image embedding and each label embedding
5. Picks the label with highest similarity score
6. Maps that label index to `(category, subcategory, content_type)` via `CLIP_LABEL_MAPPING`
7. Saves with `method = 'clip_zeroshot'`

**After classification:**
- `save_category()` → writes to `categories` table
- `build_fts_index()` → writes to `fts_index` virtual table (see Stage 5)
- Updates `images.status` → `'classified'`

**Files involved:**
- `backend/pipeline/classifier.py` — CLIP + orchestration
- `backend/pipeline/rules.py` — keyword matching (pure Python, no DB)
- `backend/db/categories.py` — `save_category()`, `build_fts_index()`

---

### Stage 5 — Index (`db/categories.py::build_fts_index`)

**What it does:**
This happens inside Stage 4, right after each image is classified. It populates the FTS5 full-text search virtual table:

```python
conn.execute("DELETE FROM fts_index WHERE image_id = ?", (image_id,))
conn.execute(
    "INSERT INTO fts_index(image_id, text_content, tags) VALUES (?, ?, ?)",
    (image_id, ocr_text, " ".join(tags_list))
)
```

The FTS5 engine processes this text with the **Porter stemmer** — meaning "searching" is indexed as "search", so a query for "search" also finds documents with "searching" and "searches". SQLite handles this automatically.

**What data flows in:** `image_id`, OCR text, list of tags (e.g. `["phonepe", "payment", "upi"]`)
**What data flows out:** Rows in `fts_index` virtual table

---

### Stage 6 — Serve (`api/main.py` + `api/routes/`)

**What it does:**
FastAPI + Uvicorn runs a REST API server on `http://localhost:8000`. The Next.js frontend at `http://localhost:3000` calls it.

**API Endpoints:**

| Method | Path | What it does |
|--------|------|-------------|
| `GET` | `/images` | List all images (paginated). Reads `images + categories` tables. |
| `GET` | `/images/{id}` | Get one image's full details (OCR text, category, tags). Reads `images + ocr_results + categories`. |
| `GET` | `/images/{id}/thumbnail` | Generate a 400×400 JPEG thumbnail on-the-fly with Pillow. Streams bytes. |
| `GET` | `/search?q=...&mode=keyword` | FTS5 keyword search with Porter stemming + HTML snippets |
| `GET` | `/search?q=...&mode=semantic` | CLIP semantic search via ChromaDB |
| `GET` | `/search?q=...&mode=hybrid` | Both keyword + semantic, merged and re-ranked |
| `GET` | `/categories` | List all categories with counts |
| `POST` | `/process/ingest` | Trigger ingestion from API |

**Files involved:**
- `backend/api/main.py` — FastAPI app setup, CORS, lifespan
- `backend/api/routes/images.py` — image endpoints
- `backend/api/routes/search.py` — search endpoints (all 3 modes)
- `backend/api/routes/categories.py` — category listing
- `backend/api/routes/process.py` — trigger pipeline from API
- `backend/api/models.py` — Pydantic response models

---

## 4. Database Schema

The database file is `data/library.db` (SQLite). Created automatically on first run.

### Table: `images` ← Master Registry

Every screenshot gets exactly one row here. This is the source of truth.

```sql
CREATE TABLE IF NOT EXISTS images (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT    NOT NULL,
    original_path   TEXT    NOT NULL UNIQUE,  -- absolute Windows path
    sha256          TEXT    NOT NULL,          -- 64-char hex, used for dedup
    file_size       INTEGER NOT NULL,          -- bytes
    width           INTEGER,                   -- pixels (from Pillow)
    height          INTEGER,                   -- pixels
    image_format    TEXT,                      -- "PNG", "JPEG", "WEBP", etc.
    captured_at     TEXT,                      -- ISO-8601 from filename regex
    modified_at     TEXT    NOT NULL,          -- file mtime (ISO-8601 string)
    modified_at_ns  INTEGER NOT NULL,          -- file mtime in nanoseconds
    status          TEXT    NOT NULL DEFAULT 'pending',
                            -- Values: pending | ocr_done | classified | error
    indexed_at      TEXT                       -- when last classified
);
```

**Indexes on `images`:**
```sql
CREATE INDEX idx_images_sha256 ON images(sha256);
CREATE INDEX idx_images_status ON images(status);
```

**Who writes here:** `ingestion.py` (INSERT), `ocr.py` (UPDATE status), `classifier.py` (UPDATE status)

---

### Table: `ocr_results` ← Text Extracted from Each Image

One row per image (1:1 relationship with `images`).

```sql
CREATE TABLE IF NOT EXISTS ocr_results (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id       INTEGER NOT NULL UNIQUE REFERENCES images(id) ON DELETE CASCADE,
    extracted_text TEXT    NOT NULL DEFAULT '',  -- full text from Tesseract
    language       TEXT,                         -- detected language
    confidence     REAL,                         -- 0.0–100.0 (mean word confidence)
    engine         TEXT    NOT NULL,             -- "tesseract" (or "paddleocr" if installed)
    word_count     INTEGER NOT NULL DEFAULT 0,
    processed_at   TEXT    NOT NULL              -- ISO-8601 timestamp
);
```

**Index:**
```sql
CREATE INDEX idx_ocr_image ON ocr_results(image_id);
```

**Who writes here:** `pipeline/ocr.py` via `db/ocr.py::save_ocr_result()`
**Who reads here:** `classifier.py` (JOINs to get the text), `api/routes/images.py` (for detail view)

---

### Table: `categories` ← Classification Results

One row per image (1:1 with `images`).

```sql
CREATE TABLE IF NOT EXISTS categories (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id     INTEGER NOT NULL UNIQUE REFERENCES images(id) ON DELETE CASCADE,
    category     TEXT    NOT NULL,          -- e.g. "Finance"
    subcategory  TEXT,                      -- e.g. "Payment Apps"
    content_type TEXT,                      -- e.g. "transaction", "chat", "post"
    tags         TEXT    NOT NULL DEFAULT '[]',  -- JSON array: '["phonepe","upi"]'
    confidence   REAL,                      -- 0.0–1.0
    method       TEXT    NOT NULL,          -- "rule_based" | "clip_zeroshot" | "fallback"
    created_at   TEXT    NOT NULL
);
```

**Indexes:**
```sql
CREATE INDEX idx_categories_image    ON categories(image_id);
CREATE INDEX idx_categories_category ON categories(category);
```

**Who writes here:** `pipeline/classifier.py` via `db/categories.py::save_category()`
**Who reads here:** `api/routes/search.py` (for category info in results), `api/routes/categories.py`

**Note on `tags` column:** Stored as a JSON string in SQLite (e.g. `'["phonepe","upi","500"]'`). Pydantic automatically parses this back to `list[str]` before sending to the frontend.

---

### Table: `embeddings` ← Pointer to ChromaDB Vectors

One row per image. The actual 512-float vectors live in `data/chroma/`, NOT in SQLite.

```sql
CREATE TABLE IF NOT EXISTS embeddings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id   INTEGER NOT NULL UNIQUE REFERENCES images(id) ON DELETE CASCADE,
    model      TEXT    NOT NULL,   -- "clip-ViT-B-32"
    created_at TEXT    NOT NULL
);
```

**Index:**
```sql
CREATE INDEX idx_embeddings_image ON embeddings(image_id);
```

**Who writes here:** `pipeline/embeddings.py` (after upserting to ChromaDB)
**Who reads here:** `api/routes/search.py` (to verify embedding exists before semantic search)

**Where the actual vectors are:** `data/chroma/` — ChromaDB's HNSW (Hierarchical Navigable Small World) index. Keyed by `str(image_id)` (e.g. `"5777"`).

---

### Table: `fts_index` ← Full-Text Search Virtual Table (FTS5)

This is a **SQLite FTS5 virtual table** — it has no physical rows in the normal sense. The FTS5 engine manages its own B-tree indexes internally.

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS fts_index USING fts5(
    image_id     UNINDEXED,    -- not tokenized; just a join key back to images
    text_content,              -- full OCR text (Porter-stemmed at insert time)
    tags,                      -- space-separated tag list
    tokenize = 'porter unicode61'   -- English stemming + Unicode support
);
```

**What "Porter stemmer" means here:**
When you insert "PhonePe payment confirmed", FTS5 stores tokens like: `phonepe`, `payment`, `confirm`. When you search "payments", FTS5 also stems it to `payment` and finds the same documents. This is why searching "confirming" finds screenshots that say "confirmed".

**Who writes here:** `db/categories.py::build_fts_index()` (called by classifier after every classification)
**Who reads here:** `db/search.py::keyword_search()` using `MATCH` syntax

---

### Entity Relationship Diagram

```
images (1) ─────────────── (1) ocr_results
   │                              (extracted_text, confidence, engine)
   │
   ├─────────────────────── (1) categories
   │                              (category, subcategory, tags, method)
   │
   ├─────────────────────── (1) embeddings
   │                              (model → points to data/chroma/)
   │
   └─────────────────────── (1) fts_index [virtual]
                                   (text_content, tags — for MATCH queries)
```

All child tables use `ON DELETE CASCADE` — deleting an image from `images` automatically removes its OCR result, category, embedding pointer, and FTS entry.

---

## 5. Technology Map

### hashlib (Python stdlib)

**Used in:** `backend/pipeline/ingestion.py::calculate_sha256()`

**What it does here:** Reads each image file in **1 MB chunks** (not all at once — avoids RAM spikes on large images), feeds chunks to `hashlib.sha256().update()`, then calls `.hexdigest()` to get a 64-character string like `a3f9b2c1d4e5...`.

This hex string is stored in `images.sha256`. On every ingest run, the pipeline checks this column first — if the hash already exists, it skips the file entirely. This prevents duplicates even if you rename or move a file.

```python
def calculate_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1_048_576), b""):
            h.update(chunk)
    return h.hexdigest()
```

---

### Pillow (PIL)

**Used in 4 distinct places:**

**1. During ingestion** (`ingestion.py`):
```python
with Image.open(path) as img:
    width, height = img.size       # e.g. (1080, 2400)
    image_format = img.format      # "PNG", "JPEG", etc.
```
Gets dimensions and format for the `images` table. The image is immediately closed — no transformation.

**2. During OCR preprocessing** (`preprocessor.py`):
```python
img = img.resize((w*2, h*2), Image.LANCZOS)   # 2× upscale for better OCR
img = img.filter(ImageFilter.SHARPEN)           # sharpen edges
if mean_brightness < 100:
    img = ImageOps.invert(img.convert("RGB"))   # invert dark-mode screenshots
img = img.convert("L")                          # grayscale for Tesseract
```
The result is a preprocessed image in memory — never saved to disk.

**3. During CLIP classification** (`classifier.py`):
```python
with Image.open(image_path) as img:
    image = img.convert("RGB")     # CLIP needs RGB, no alpha channel
# image → model.encode(image) → 512-dim vector
```

**4. During thumbnail generation** (`api/routes/images.py`):
```python
img.thumbnail((400, 400), Image.LANCZOS)   # letterbox within 400×400
buf = io.BytesIO()
img.save(buf, "JPEG", quality=85)
buf.seek(0)
return StreamingResponse(buf, media_type="image/jpeg")
```
Thumbnails are **never saved to disk** — generated on every request and streamed directly to the browser.

---

### pytesseract + Tesseract OCR

**Used in:** `backend/pipeline/ocr.py`

**What it does here:**
```python
data = pytesseract.image_to_data(
    enhanced_img,
    config="--oem 3 --psm 6",
    output_type=pytesseract.Output.DICT
)
```

This calls the **Tesseract binary** at `C:\Program Files\Tesseract-OCR\tesseract.exe`. The `-c` flags mean:
- `--oem 3` = LSTM neural network mode (best accuracy, slowest)
- `--psm 6` = Assume uniform block of text (good for phone screenshots)

The return value is a Python dict with parallel arrays:
```python
{
    "text": ["PhonePe", "₹500", "sent", "to", ...],
    "conf": [92.3, 87.1, 94.5, 88.0, ...],   # confidence per word
    ...
}
```

The pipeline:
1. Zips `text` and `conf` together
2. Filters out conf < 50 (low-confidence noise)
3. Joins remaining words to form `extracted_text`
4. Averages the confidence values → stored in `ocr_results.confidence`
5. If fewer than 3 words remain → `word_count = 0`, `extracted_text = ''`

---

### Click

**Used in:** `backend/run_pipeline.py`

**What it does here:** Turns Python functions into shell commands with flags. `@cli.command()` registers a function as a subcommand. `@click.option()` adds flags.

```python
@cli.command("ocr")
@click.option("--limit", default=None, type=int, help="Max images to OCR")
@click.option("--force", is_flag=True, default=False, help="Re-run OCR on already-processed")
def ocr_cmd(limit, force, ...):
    ...
```

This is why you can run:
```powershell
python -m backend.run_pipeline ocr --limit 100 --force
python -m backend.run_pipeline classify --force
python -m backend.run_pipeline embed
python -m backend.run_pipeline process-all
python -m backend.run_pipeline status
```

The `--force` flag becomes the `force=True` Python argument passed to `run_classification(conn, force=True)`, which changes the SQL query to include already-classified images.

---

### tqdm

**Used in:** `ingestion.py`, `ocr.py`, `classifier.py`, `embeddings.py`

**What it does here:**
```python
with tqdm(rows, desc="Classify", unit="img", dynamic_ncols=True) as bar:
    for row in bar:
        ...
```

This wraps the list of DB rows and prints a live progress bar like:
```
Classify: 57%|████████         | 4928/8615 [21:07<16:08,  6.79img/s]
```

It knows the total (length of `rows`), tracks time per iteration, and calculates ETA. `dynamic_ncols=True` adjusts to the terminal width. No configuration needed — it just works.

---

### Pydantic

**Used in:** `backend/api/models.py`, consumed by all FastAPI routes

**What it does here:**

SQLite returns rows as Python dicts (via `conn.row_factory = sqlite3.Row`). These are raw — the `tags` column is a JSON string like `'["phonepe","upi"]'`, not a Python list.

Pydantic models act as validators AND serializers:

```python
class ImageDetail(BaseModel):
    id: int
    filename: str
    original_path: str
    width: int | None = None
    height: int | None = None
    extracted_text: str = ""
    ocr_confidence: float | None = None
    engine: str = "tesseract"
    word_count: int = 0
    category: str = ""
    subcategory: str = ""
    tags: list[str] = []          # ← Pydantic parses '["a","b"]' → ["a","b"]
    confidence: float = 0.0
    method: str = ""
```

When FastAPI does `response_model=ImageDetail`, it:
1. Takes the SQLite dict row
2. Passes it as `ImageDetail(**row)`
3. Pydantic validates each field's type
4. Pydantic parses the JSON string in `tags` → Python `list[str]`
5. FastAPI serializes the model to JSON for the HTTP response

If a field is wrong type or missing, Pydantic raises `ValidationError` → FastAPI returns HTTP 422 automatically.

---

### FastAPI

**Used in:** `backend/api/main.py` + `backend/api/routes/`

**What it does here — specifically:**

```python
app = FastAPI(title="ScreenshotKB API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"])
```

The `lifespan` context manager runs `init_db(conn)` on startup — this creates all 5 tables if they don't exist.

**Route example (thumbnail):**
```python
@router.get("/images/{image_id}/thumbnail")
async def get_thumbnail(image_id: int, db: Connection = Depends(get_db)):
    row = db.execute("SELECT original_path FROM images WHERE id=?", (image_id,)).fetchone()
    with Image.open(row["original_path"]) as img:
        img.thumbnail((400, 400), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")
```

**Route example (keyword search):**
```python
@router.get("/search", response_model=SearchResponse)
async def search(q: str, mode: str = "keyword", limit: int = 50, db=Depends(get_db)):
    if mode == "semantic":
        results = semantic_search(q, n_results=limit)   # ChromaDB
    elif mode == "hybrid":
        results = hybrid_search(q, db, limit)
    else:
        results = keyword_search(q, db, limit)           # FTS5
    return SearchResponse(query=q, results=results, ...)
```

CORS middleware allows the Next.js frontend (`localhost:3000`) to call the FastAPI backend (`localhost:8000`) cross-origin.

---

### Uvicorn

**Used to serve FastAPI**

**What it does here:**
```powershell
uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

Uvicorn is an ASGI (Asynchronous Server Gateway Interface) server. It:
- Loads `backend/api/main.py` and finds the `app` object
- Listens on `127.0.0.1:8000`
- `--reload` watches the `backend/` directory for `.py` file changes and restarts automatically (dev mode)
- Handles concurrent HTTP requests using Python `asyncio` (non-blocking I/O)

---

### SQLite FTS5

**Used in:** `db/categories.py` (write), `db/search.py` (read)

**What it does here:**

**Writing:**
```python
conn.execute(
    "INSERT INTO fts_index(image_id, text_content, tags) VALUES (?,?,?)",
    (image_id, ocr_text, " ".join(tags))
)
```
FTS5 immediately tokenizes and indexes `text_content` and `tags`.

**Querying (keyword search):**
```python
def _safe_fts_query(raw: str) -> str:
    # Strips FTS5 special chars, allows "quoted phrases" and word* prefix
    return cleaned

results = conn.execute("""
    SELECT i.id, i.filename, i.original_path,
           snippet(fts_index, 1, '<b>', '</b>', '…', 20) AS snippet,
           -fts_index.rank AS score
    FROM fts_index
    JOIN images i ON fts_index.image_id = i.id
    WHERE fts_index MATCH ?
    ORDER BY fts_index.rank
    LIMIT ?
""", (safe_query, limit)).fetchall()
```

- `MATCH ?` — FTS5 full-text search with stemming
- `snippet(fts_index, 1, '<b>', '</b>', '…', 20)` — returns a highlighted excerpt like `…<b>PhonePe</b> payment confirmed…`
- `-fts_index.rank` — rank is negative (more negative = more relevant); negate it to get a positive score where higher = better

---

### ChromaDB

**Used in:** `pipeline/embeddings.py::get_chroma_collection()`, `pipeline/embeddings.py::semantic_search()`

**What it does here:**

**Setup:**
```python
client = chromadb.PersistentClient(path=str(CHROMA_DIR))  # data/chroma/
collection = client.get_or_create_collection(
    name="screenshots",
    metadata={"hnsw:space": "cosine"}   # use cosine distance metric
)
```

**Writing one embedding:**
```python
collection.upsert(
    ids=["5777"],                              # str(image_id)
    embeddings=[[0.023, -0.187, ..., 0.041]], # 512 floats
    metadatas=[{"filename": "Screenshot_2024-03-15.png"}]
)
```

**Querying:**
```python
query_emb = model.encode("payment confirmation").tolist()   # 512 floats
results = collection.query(
    query_embeddings=[query_emb],
    n_results=20
)
# returns: {"ids": [["5777","1203","4421",...]], "distances": [[0.12, 0.19, 0.23,...]]}
```

ChromaDB uses an **HNSW (Hierarchical Navigable Small World)** graph index stored in `data/chroma/` — it finds approximate nearest neighbours in milliseconds even with 8,615 vectors. Distance = cosine distance (0 = identical, 2 = completely opposite). Score = `1 - distance`.

---

### sentence-transformers (CLIP)

**Used in:** `pipeline/classifier.py`, `pipeline/embeddings.py`

**What it does here:**

The model is `clip-ViT-B-32` — a Vision-Language model trained by OpenAI. It maps both images AND text into the same 512-dimensional vector space. Similar concepts end up close together.

**Loading (singleton — loaded once per process):**
```python
_clip_model = SentenceTransformer("clip-ViT-B-32")
```
Downloads ~400 MB of model weights to `~/.cache/torch/` on first run. Subsequent runs load from cache.

**Encoding an image:**
```python
img_emb = model.encode(image)        # PIL Image → 512-dim float32 numpy array
```

**Encoding text for classification:**
```python
label_embs = model.encode([
    "a PhonePe payment confirmation screen",
    "an Instagram direct message chat conversation",
    ... # 50 labels total
])  # → (50, 512) numpy array
```

**Cosine similarity to pick best label:**
```python
sims = torch.nn.functional.cosine_similarity(img_emb.unsqueeze(0), label_embs, dim=1)
best_idx = int(sims.argmax())   # index of best-matching label
```

**Encoding text for semantic search:**
```python
query_emb = model.encode("payment confirmation").tolist()
# → 512 floats in the same vector space as image embeddings
# ChromaDB finds images nearest to this query vector
```

This is why searching "payment confirmation" in Semantic mode finds PhonePe screenshots even if the word "payment" doesn't appear in the OCR text — the visual content of the image is similar to the concept of "payment confirmation".

---

### Next.js (App Router)

**Used in:** `frontend/`

**Pages and what they render:**

| File | Route | What it shows |
|------|-------|---------------|
| `app/page.tsx` | `/` | Home/dashboard — recent screenshots, stats |
| `app/search/page.tsx` | `/search?q=...&mode=...` | Search results grid |
| `app/library/page.tsx` | `/library` | Full library browser with category sidebar |
| `app/image/[id]/page.tsx` | `/image/5777` | Detail view — full image + OCR text + metadata |
| `app/layout.tsx` | All pages | AppSidebar + theme initialization script |

App Router means each folder with `page.tsx` = one route. `[id]` in a folder name = dynamic segment.

---

### Tailwind CSS v4

**Used in:** `frontend/app/globals.css`, `frontend/postcss.config.mjs`

**How it's set up here:**
```js
// frontend/postcss.config.mjs
export default {
  plugins: { "@tailwindcss/postcss": {} }
}
```
```css
/* globals.css */
@import "tailwindcss";
```

**How the design tokens work (custom CSS properties):**

The design uses CSS custom properties (not Tailwind utility classes) for the color system:
```css
:root {
  --bg-canvas: #F3F0E9;
  --bg-surface: #FBFAF7;
  --text-primary: #24231F;
  --accent: #B65F43;
  /* ... */
}
[data-theme="dark"] {
  --bg-canvas: #191917;
  --bg-surface: #22221F;
  --text-primary: #EEEAE2;
  --accent: #D58A6D;
}
```

The 60-30-10 rule is applied: 60% canvas/surface colors, 30% secondary text colors, 10% accent. Tailwind utility classes are used only for layout (flex, grid, padding, margin).

---

### SWR (Stale-While-Revalidate)

**Used in:** Frontend React components

**What it does here:**
```typescript
const { data, error, isLoading } = useSWR('/api/images?limit=20', fetcher)
```

SWR is a React hook that:
1. Makes the API call immediately (using `fetcher = url => fetch(url).then(r => r.json())`)
2. Caches the result in memory (keyed by URL)
3. Returns cached data instantly on re-render (no loading flicker)
4. Revalidates in the background on window focus
5. Shares data between components that use the same key (no duplicate requests)

---

## 6. File & Folder Structure

```
Screenshot-Knowledge-Base/
│
├── backend/                        # All Python backend code
│   ├── config.py                   # Centralized paths & settings — imported by ALL other backend files
│   ├── run_pipeline.py             # CLI entry point (Click commands)
│   │
│   ├── pipeline/                   # Data processing logic
│   │   ├── ingestion.py            # Scan folder, hash files, insert to images table
│   │   ├── preprocessor.py         # Enhance images for OCR (pure Pillow, no DB)
│   │   ├── ocr.py                  # Tesseract OCR → ocr_results table
│   │   ├── classifier.py           # Rule engine + CLIP → categories table + fts_index
│   │   ├── rules.py                # Keyword dictionaries (pure Python, no DB)
│   │   ├── embeddings.py           # CLIP encode → ChromaDB + embeddings table
│   │   └── logger.py               # Setup rotating file loggers (no DB)
│   │
│   ├── db/                         # Database access layer
│   │   ├── database.py             # get_connection() — opens SQLite with row_factory
│   │   ├── schema.py               # CREATE TABLE statements — called once on startup
│   │   ├── ocr.py                  # get_pending_images(), save_ocr_result()
│   │   ├── categories.py           # save_category(), build_fts_index()
│   │   └── search.py               # keyword_search(), semantic_search(), hybrid_search()
│   │
│   ├── api/                        # FastAPI application
│   │   ├── main.py                 # App setup, CORS, lifespan (creates tables on startup)
│   │   ├── models.py               # Pydantic response models (ImageBase, ImageDetail, etc.)
│   │   └── routes/
│   │       ├── images.py           # /images endpoints + thumbnail generation
│   │       ├── search.py           # /search endpoint (keyword/semantic/hybrid)
│   │       ├── categories.py       # /categories endpoint
│   │       └── process.py          # /process endpoint (triggers pipeline from web)
│   │
│   └── data/
│       └── categories.json         # Category taxonomy used by rules.py
│
├── data/
│   ├── library.db                  # SQLite database (8,615 images)
│   ├── chroma/                     # ChromaDB HNSW index (8,615 vectors)
│   └── logs/
│       ├── pipeline.log
│       ├── ocr.log
│       ├── classifier.log
│       └── embeddings.log
│
├── frontend/                       # Next.js web application
│   ├── app/
│   │   ├── layout.tsx              # AppSidebar + theme script (wraps all pages)
│   │   ├── globals.css             # Design tokens (CSS vars) + Tailwind import
│   │   ├── page.tsx                # / (Home)
│   │   ├── search/page.tsx         # /search
│   │   ├── library/page.tsx        # /library
│   │   └── image/[id]/page.tsx     # /image/{id} (detail view)
│   ├── components/
│   │   ├── AppSidebar.tsx          # Navigation sidebar
│   │   ├── ImageCard.tsx           # Screenshot thumbnail card
│   │   ├── ImageGrid.tsx           # Grid layout for cards
│   │   └── SearchBar.tsx           # Search input with mode toggle
│   ├── lib/
│   │   └── api.ts                  # API client functions (wraps fetch calls)
│   ├── next.config.ts              # Next.js config
│   └── postcss.config.mjs          # Tailwind CSS v4 PostCSS config
│
├── scripts/                        # Utility/debug scripts
│   ├── check_db.py                 # Print DB stats
│   ├── db_summary.py               # Category distribution report
│   ├── inspect_ocr.py              # Print OCR text for specific images
│   └── test_semantic.py            # Test semantic search with 7 queries
│
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

### Dependency Graph (what calls what)

```
run_pipeline.py (CLI)
  ├── pipeline/ingestion.py
  │     ├── db/database.py     → opens library.db
  │     └── db/schema.py       → creates tables if missing
  │
  ├── pipeline/ocr.py
  │     ├── pipeline/preprocessor.py   (pure Pillow, no DB)
  │     └── db/ocr.py          → reads images, writes ocr_results
  │
  ├── pipeline/classifier.py
  │     ├── pipeline/rules.py  (pure Python keyword match, no DB)
  │     └── db/categories.py   → writes categories + fts_index
  │
  └── pipeline/embeddings.py
        └── data/chroma/       → ChromaDB HNSW index
              embeddings table → pointer only (no vectors in SQLite)

api/main.py (FastAPI)
  ├── api/routes/images.py     → reads images + ocr_results + categories
  │                                 Pillow for thumbnails
  ├── api/routes/search.py     → db/search.py (FTS5)
  │                               pipeline/embeddings.py (ChromaDB)
  ├── api/routes/categories.py → db/categories.py
  ├── api/routes/process.py    → pipeline/* (triggers pipeline from API)
  └── api/models.py            → Pydantic models for all responses

config.py ← imported by EVERYTHING
  DATABASE = data/library.db
  DEFAULT_SOURCE = C:\Users\Pratik\Pictures\MobScreenshots
  CHROMA_DIR = data/chroma/
  CLIP_MODEL = "clip-ViT-B-32"
  CHECKPOINT_INTERVAL = 100
```

---

## 7. How to Run

### Prerequisites

```powershell
# Check Python version (need 3.11+)
python --version

# Check Tesseract is installed
tesseract --version

# Install Python dependencies
pip install -r requirements.txt
```

### Running the Pipeline

```powershell
# From project root: C:\Users\Pratik\Documents\VSCode\Screenshot-Knowledge-Base

# Step 1: Scan and ingest all screenshots
python -m backend.run_pipeline ingest

# Step 2: Run OCR on all pending images
python -m backend.run_pipeline ocr

# Step 3: Classify all images (rule engine + CLIP)
python -m backend.run_pipeline classify

# Step 4: Generate CLIP embeddings for semantic search
python -m backend.run_pipeline embed

# --- OR run all 4 stages in one command ---
python -m backend.run_pipeline process-all

# Check database status
python -m backend.run_pipeline status
```

**Useful flags:**
```powershell
# Re-classify all images (even already classified)
python -m backend.run_pipeline classify --force

# Only process first 100 images (for testing)
python -m backend.run_pipeline ocr --limit 100

# Re-run OCR on previously failed images
python -m backend.run_pipeline ocr --retry-failed
```

### Starting the Backend API

```powershell
cd C:\Users\Pratik\Documents\VSCode\Screenshot-Knowledge-Base
uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

API is now at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

### Starting the Frontend

```powershell
cd C:\Users\Pratik\Documents\VSCode\Screenshot-Knowledge-Base\frontend
npm run dev
```

Frontend is now at `http://localhost:3000`.

### Both Together

Open two PowerShell windows:
- Window 1: `uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000`
- Window 2: `cd frontend ; npm run dev`

---

## 8. Current State

**As of November 2026 (last pipeline run):**

| Metric | Value |
|--------|-------|
| Total screenshots | 8,615 |
| OCR processed | 8,615 (100%) |
| Classified | 8,615 (100%) |
| Embedded (CLIP) | 8,615 (100%) |
| ChromaDB vectors | 8,615 |
| Uncategorized | 173 (2% — down from 2,768 before CLIP) |
| Rule-based classified | 5,847 (67.9%) |
| CLIP zero-shot classified | 2,768 (32.1%) |

**Category Distribution (top categories):**

| Category | Count |
|----------|-------|
| Instagram Posts | 1,503 |
| Budgets | 544 |
| Instagram Chats | 872 |
| Chats & Messages | 534 |
| Instagram | 563 |
| UPI Transactions | 489 |
| Receipts & Invoices | 480 |
| Navigation | 287 |
| Instagram Stories & Reels | 274 |
| Profile Pictures | 233 |
| Portraits | 229 |
| Payment Apps | 203 |
| Movies & Shows | 206 |

**Git:** `main` branch, last commit `443429a`, pushed to `https://github.com/pratikanpat/Screenshot-Pipeline`

---

## 9. Design System & Frontend

The UI uses a custom design system built with CSS custom properties. Default theme is **dark mode**.

### Color Tokens

| Token | Light Value | Dark Value | Usage |
|-------|------------|------------|-------|
| `--bg-canvas` | `#F3F0E9` | `#191917` | Page background (60%) |
| `--bg-surface` | `#FBFAF7` | `#22221F` | Card backgrounds (30%) |
| `--bg-elevated` | `#FFFFFF` | `#292824` | Modals, dropdowns |
| `--text-primary` | `#24231F` | `#EEEAE2` | Headings, body text |
| `--text-secondary` | `#77736B` | `#AAA397` | Captions, metadata |
| `--border` | `#E4DED3` | `#39362F` | Dividers, card borders |
| `--accent` | `#B65F43` | `#D58A6D` | Buttons, links, highlights (10%) |
| `--accent-soft` | `#F1E3DA` | `#3A2A24` | Accent backgrounds |
| `--success` | `#55765C` | `#8EAD88` | Success states |

### Design Principles
- **60-30-10 rule:** 60% canvas/surface, 30% secondary, 10% accent — not random
- **Typography-first:** OCR text and metadata support the image, never compete
- **No clutter:** Minimal chrome, screenshots are the content
- **Editorial feel:** Warm tones, structured whitespace

---

## 10. Errors & Fixes

| Error | Root Cause | Fix Applied |
|-------|-----------|-------------|
| Giant search icon filling entire screen | `next.config.ts` had broken `turbopack.rules["*.css"]` with `@tailwindcss/turbopack` loader — broke ALL CSS processing | Removed the turbopack block entirely; created `postcss.config.mjs` with `@tailwindcss/postcss` |
| `pip install sentence-transformers` warning about protobuf | `streamlit` (also installed globally) had a protobuf version conflict | Warning only — packages installed fine. Ignored. |
| `python -c "..."` with `{` characters in PowerShell | PowerShell interprets `{` as a block delimiter in `-c "..."` strings | Used separate `.py` script files instead of inline one-liners |
| `ModuleNotFoundError: No module named 'backend'` in scripts | Scripts run directly from `scripts/` folder, not as Python modules | Added `sys.path.insert(0, parent_dir)` at top of each script in `scripts/` |
| `git add -A` failed on `library.db-shm` | SQLite WAL mode holds a shared memory lock file while DB is open | Added `*.db-shm`, `*.db-wal`, `data/chroma/` to `.gitignore`; use `git add` selectively |
| `SyntaxError: unterminated string literal` in inline python | f-string with backslash in PowerShell one-liner | Use external `.py` script files |
| `ModuleNotFoundError: No module named 'PIL'` | Pillow not installed | `pip install Pillow` |
| Tesseract not found | Binary not in PATH | Install from `https://github.com/UB-Mannheim/tesseract/wiki`, add to PATH |

---

## 11. Roadmap

### V1.1 — Better OCR (PaddleOCR)
> Deferred — CLIP covers visual understanding adequately for now

PaddleOCR handles dense text, tables, mixed Hindi/English content far better than Tesseract. When ready:
```powershell
pip install paddlepaddle paddleocr
python -m backend.run_pipeline ocr --force   # re-process all with new engine
```

### V1.2 — UI Improvements
- Filter sidebar by category/subcategory
- Date range filter
- Infinite scroll / virtual list for performance
- Image detail panel (slide-in, not new page)
- Keyboard navigation

### V1.3 — Smart Re-classification
- Confidence threshold: re-classify images where `confidence < 0.6` with better prompts
- Multi-label: some screenshots belong in multiple categories
- User corrections: allow manual re-labeling from UI

### V1.4 — Connections & Relationships
- Link screenshots that share common tags/people
- Timeline view (screenshots organized by date)
- "Similar to this" button on detail view (uses existing ChromaDB)

### V1.5 — Natural Language Query
- Ask questions like "show me all my Swiggy orders from March"
- Use Gemini API (local model) or Ollama for query parsing
- Route to keyword/semantic/filter combination automatically

---

## Requirements

**Python packages** (`requirements.txt`):
```
fastapi
uvicorn[standard]
pillow
pytesseract
click
tqdm
pydantic
torch
sentence-transformers
chromadb
```

**System requirements:**
- Python 3.11+ (developed on 3.13)
- Tesseract OCR binary (`winget install UB-Mannheim.TesseractOCR`)
- Node.js 18+ (for frontend)
- ~2 GB disk for CLIP model cache (`~/.cache/torch/`)
- ~500 MB for ChromaDB index (8,615 images)

---

*ScreenshotKB — Built locally, runs privately, searches semantically.*
