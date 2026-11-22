"""
backend/db/schema.py
────────────────────
Defines and creates all SQLite tables and indexes for the Screenshot
Knowledge Base.  The single entry-point is ``create_all_tables(conn)``,
which is idempotent — safe to call on every connection open.

Schema overview
───────────────
  images        — master record for each unique screenshot
  ocr_results   — text extracted from each image (one row per image)
  categories    — CLIP / rule-engine classification results
  embeddings    — reference row for vectors stored in ChromaDB
  fts_index     — FTS5 virtual table for full-text keyword search
"""

from __future__ import annotations

import sqlite3


# ─────────────────────────────────────────────────────────────────────────────
# DDL statements
# ─────────────────────────────────────────────────────────────────────────────

_CREATE_IMAGES = """
CREATE TABLE IF NOT EXISTS images (
    -- Surrogate primary key
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- File identity
    filename        TEXT    NOT NULL,
    original_path   TEXT    NOT NULL UNIQUE,   -- absolute path to source file (never moved)
    sha256          TEXT    NOT NULL,           -- hex SHA-256 of file bytes (deduplication key)
    file_size       INTEGER NOT NULL,           -- bytes

    -- Image metadata (populated after Pillow open)
    width           INTEGER,
    height          INTEGER,
    image_format    TEXT,                       -- e.g. "PNG", "JPEG"

    -- Timestamps
    captured_at     TEXT,                       -- EXIF / file-creation time (ISO-8601)
    modified_at     TEXT    NOT NULL,           -- file mtime (ISO-8601)
    modified_at_ns  INTEGER NOT NULL,           -- file mtime in nanoseconds (precise dedup)

    -- Pipeline state
    status          TEXT    NOT NULL DEFAULT 'pending',
                                                -- pending | processing | indexed | error
    indexed_at      TEXT                        -- ISO-8601, set when status → 'indexed'
);
"""

_CREATE_OCR_RESULTS = """
CREATE TABLE IF NOT EXISTS ocr_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- One OCR result per image
    image_id        INTEGER NOT NULL UNIQUE
                        REFERENCES images(id) ON DELETE CASCADE,

    -- Extracted content
    extracted_text  TEXT    NOT NULL DEFAULT '',
    language        TEXT,                       -- detected / requested language code
    confidence      REAL,                       -- 0.0–100.0 mean confidence across words
    engine          TEXT    NOT NULL,           -- "paddleocr" | "tesseract"
    word_count      INTEGER NOT NULL DEFAULT 0,

    processed_at    TEXT    NOT NULL            -- ISO-8601
);
"""

_CREATE_CATEGORIES = """
CREATE TABLE IF NOT EXISTS categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    image_id        INTEGER NOT NULL UNIQUE
                        REFERENCES images(id) ON DELETE CASCADE,

    -- Classification output
    category        TEXT    NOT NULL,           -- top-level key from categories.json
    subcategory     TEXT,                       -- second-level value
    content_type    TEXT,                       -- fine-grained label (optional)
    tags            TEXT    NOT NULL DEFAULT '[]',
                                                -- JSON array, e.g. '["python","tutorial"]'
    confidence      REAL,                       -- 0.0–1.0
    method          TEXT    NOT NULL,           -- "clip_zeroshot" | "rule_based" | "fallback"

    created_at      TEXT    NOT NULL            -- ISO-8601
);
"""

_CREATE_EMBEDDINGS = """
CREATE TABLE IF NOT EXISTS embeddings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- One embedding record per image (vectors live in ChromaDB, keyed by image_id)
    image_id        INTEGER NOT NULL UNIQUE
                        REFERENCES images(id) ON DELETE CASCADE,

    model           TEXT    NOT NULL,           -- e.g. "clip-ViT-B-32"
    created_at      TEXT    NOT NULL            -- ISO-8601
);
"""

# FTS5 virtual table — mirrors ocr_results.extracted_text + category tags.
# image_id is UNINDEXED so we can JOIN back to images without it being tokenised.
# Porter stemmer + unicode61 tokeniser gives good English recall.
_CREATE_FTS_INDEX = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts_index USING fts5 (
    image_id    UNINDEXED,
    text_content,                               -- mirrors ocr_results.extracted_text
    tags,                                       -- space-separated tag keywords
    tokenize    = 'porter unicode61'
);
"""

# ── Indexes ───────────────────────────────────────────────────────────────────
_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_images_sha256        ON images(sha256);",
    "CREATE INDEX IF NOT EXISTS idx_images_status        ON images(status);",
    "CREATE INDEX IF NOT EXISTS idx_ocr_image            ON ocr_results(image_id);",
    "CREATE INDEX IF NOT EXISTS idx_categories_image     ON categories(image_id);",
    "CREATE INDEX IF NOT EXISTS idx_categories_category  ON categories(category);",
]

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def create_all_tables(conn: sqlite3.Connection) -> None:
    """Create every table, virtual table, and index if they do not already exist.

    This function is intentionally idempotent: calling it multiple times on the
    same database is safe and has no side-effects.

    Args:
        conn: An open :class:`sqlite3.Connection` with *foreign_keys* already
              enabled by the caller (the connection factory does this).
    """
    with conn:  # single transaction — all-or-nothing
        conn.execute(_CREATE_IMAGES)
        conn.execute(_CREATE_OCR_RESULTS)
        conn.execute(_CREATE_CATEGORIES)
        conn.execute(_CREATE_EMBEDDINGS)
        conn.execute(_CREATE_FTS_INDEX)
        for idx_sql in _CREATE_INDEXES:
            conn.execute(idx_sql)
