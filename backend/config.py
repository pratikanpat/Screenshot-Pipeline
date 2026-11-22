"""
backend/config.py
─────────────────
Central configuration for the Screenshot Knowledge Base.

All filesystem paths are derived from PROJECT_ROOT, which is auto-detected
as the directory *containing* the backend/ package (i.e., the repo root).
Override any value by setting the matching environment variable before
importing this module; python-dotenv will load a .env file from the repo
root automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Repo-root detection ───────────────────────────────────────────────────────
# This file lives at <repo_root>/backend/config.py
# → __file__.parent  = <repo_root>/backend
# → __file__.parent.parent = <repo_root>
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# Load .env from the repo root (silently skipped if the file doesn't exist)
load_dotenv(PROJECT_ROOT / ".env")

# ── Directory layout ─────────────────────────────────────────────────────────
DATA_DIR: Path = PROJECT_ROOT / "data"
DATABASE: Path = DATA_DIR / "library.db"
CHROMA_DIR: Path = DATA_DIR / "chroma"
LOGS_DIR: Path = DATA_DIR / "logs"

# ── Default screenshot source ─────────────────────────────────────────────────
# Override with the SOURCE_DIR environment variable if needed.
DEFAULT_SOURCE: Path = Path(
    os.getenv("SOURCE_DIR", str(Path.home() / "Pictures" / "MobScreenshots"))
)

# ── Supported image extensions (lower-case, with leading dot) ─────────────────
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}
)

# ── File hashing ──────────────────────────────────────────────────────────────
HASH_CHUNK_SIZE: int = 1 * 1024 * 1024  # 1 MB

# ── OCR settings ─────────────────────────────────────────────────────────────
# Language code for PaddleOCR (e.g. "en", "ch").
PADDLE_LANG: str = os.getenv("PADDLE_LANG", "en")

# Tesseract config string passed verbatim via pytesseract.
#   --oem 3  → LSTM + legacy engine (best accuracy)
#   --psm 6  → assume a uniform block of text
TESSERACT_CONFIG: str = "--oem 3 --psm 6"

# Minimum OCR confidence (0–100) to accept a result; below this the
# fallback engine is tried or the text is discarded.
OCR_CONFIDENCE_THRESHOLD: int = 50

# If fewer than this many words are extracted, the result is treated as
# "no meaningful text" (useful for icon-only screenshots).
OCR_MIN_WORDS: int = 3

# ── Semantic / CLIP model ─────────────────────────────────────────────────────
CLIP_MODEL: str = os.getenv("CLIP_MODEL", "clip-ViT-B-32")

# ── Category taxonomy ─────────────────────────────────────────────────────────
CATEGORIES_FILE: Path = PROJECT_ROOT / "backend" / "data" / "categories.json"

# ── API server ────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

# ── Thumbnail generation ──────────────────────────────────────────────────────
# (width, height) — images are resized to fit within this box, aspect-ratio
# preserved; no upscaling.
THUMBNAIL_SIZE: tuple[int, int] = (400, 400)

# ── Processing checkpoints ────────────────────────────────────────────────────
# After every CHECKPOINT_INTERVAL images the pipeline flushes its DB batch
# and logs progress so a crash loses at most this many results.
CHECKPOINT_INTERVAL: int = 50
