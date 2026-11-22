"""
scripts/migrate_db.py
─────────────────────
One-time migration: bring the old M1 schema up to the new pipeline schema.

Changes made:
  images table:
    - rename  inventory_status → status
    - add     status values mapped from inventory_status values
    - old 'ok' → new 'pending'  (ready to be OCR'd)
    - old 'error' → new 'error'

  Leaves all existing data intact.
"""

import sqlite3
from pathlib import Path

DB = Path("data/library.db")

if not DB.exists():
    print("ERROR: data/library.db not found. Run from the project root.")
    raise SystemExit(1)

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=OFF")  # needed for schema changes

# ── Check current columns ─────────────────────────────────────────────────────
cols = [r[1] for r in conn.execute("PRAGMA table_info(images)")]
print("Current images columns:", cols)

# ── Step 1: rename inventory_status → status (SQLite 3.25+) ──────────────────
if "inventory_status" in cols and "status" not in cols:
    print("Renaming inventory_status → status ...")
    conn.execute("ALTER TABLE images RENAME COLUMN inventory_status TO status")
    print("  Done.")
elif "status" in cols:
    print("Column 'status' already exists — skipping rename.")
else:
    print("WARNING: neither 'inventory_status' nor 'status' found — check schema manually.")

# ── Step 2: re-map old status values to new ones ──────────────────────────────
# Old: 'ok' | 'error'
# New: 'pending' (ready for OCR) | 'error'
print("Re-mapping status values: 'ok' → 'pending' ...")
conn.execute("UPDATE images SET status = 'pending' WHERE status = 'ok'")
updated = conn.execute("SELECT changes()").fetchone()[0]
print(f"  {updated} rows updated to 'pending'.")

# ── Step 3: add missing index if not present ──────────────────────────────────
existing_indexes = [r[1] for r in conn.execute("SELECT type, name FROM sqlite_master WHERE type='index'")]
if "idx_images_status" not in existing_indexes:
    print("Creating idx_images_status index ...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_images_status ON images(status)")
    print("  Done.")

conn.commit()

# ── Verify ────────────────────────────────────────────────────────────────────
cols_after = [r[1] for r in conn.execute("PRAGMA table_info(images)")]
print("\nFinal images columns:", cols_after)

counts = conn.execute(
    "SELECT status, COUNT(*) FROM images GROUP BY status ORDER BY COUNT(*) DESC"
).fetchall()
print("\nStatus breakdown:")
for status, count in counts:
    print(f"  {status:20s}: {count:,}")

conn.close()
print("\nMigration complete. Run the pipeline again.")
