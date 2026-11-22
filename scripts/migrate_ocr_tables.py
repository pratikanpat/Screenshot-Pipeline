"""
scripts/migrate_ocr_tables.py
──────────────────────────────
Drops the old-schema ocr_results and ocr_candidates tables (created by the
legacy M2 inventory script) and recreates them with the new pipeline schema.

Safe to run because:
  - The old tables have only ~50 rows from a prototype script.
  - All 8,615 images are still marked 'pending' in the images table,
    so the OCR pipeline will simply re-process them fresh.
  - ocr_candidates was a temporary staging table; it is not referenced
    by any new code and will just be dropped.
"""

import sqlite3
from pathlib import Path

DB = Path("data/library.db")

if not DB.exists():
    print("ERROR: data/library.db not found. Run from the project root.")
    raise SystemExit(1)

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=OFF")

# ── Show current state ────────────────────────────────────────────────────────
ocr_cols = [r[1] for r in conn.execute("PRAGMA table_info(ocr_results)")]
print("Current ocr_results columns:", ocr_cols)
old_rows = conn.execute("SELECT COUNT(*) FROM ocr_results").fetchone()[0]
print(f"Rows to discard: {old_rows}")

# ── Drop old tables ───────────────────────────────────────────────────────────
print("Dropping old ocr_results ...")
conn.execute("DROP TABLE IF EXISTS ocr_results")

print("Dropping old ocr_candidates ...")
conn.execute("DROP TABLE IF EXISTS ocr_candidates")

# ── Recreate with new schema ──────────────────────────────────────────────────
print("Creating new ocr_results table ...")
conn.execute("""
CREATE TABLE ocr_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    image_id        INTEGER NOT NULL UNIQUE
                        REFERENCES images(id) ON DELETE CASCADE,

    -- Extracted content
    extracted_text  TEXT    NOT NULL DEFAULT '',
    language        TEXT,                       -- detected / requested language code
    confidence      REAL,                       -- 0.0-100.0 mean confidence across words
    engine          TEXT    NOT NULL,           -- "paddleocr" | "tesseract"
    word_count      INTEGER NOT NULL DEFAULT 0,

    processed_at    TEXT    NOT NULL            -- ISO-8601
)
""")

# ── Recreate standard indexes ─────────────────────────────────────────────────
print("Creating indexes ...")
conn.execute("CREATE INDEX IF NOT EXISTS idx_ocr_image ON ocr_results(image_id)")

# ── Verify ────────────────────────────────────────────────────────────────────
conn.commit()
new_cols = [r[1] for r in conn.execute("PRAGMA table_info(ocr_results)")]
print("New ocr_results columns:", new_cols)

# Confirm all images are still pending
pending = conn.execute(
    "SELECT COUNT(*) FROM images WHERE status = 'pending'"
).fetchone()[0]
print(f"Images pending OCR: {pending:,}")

conn.close()
print("\nocr_results migration complete. Run the pipeline again.")
