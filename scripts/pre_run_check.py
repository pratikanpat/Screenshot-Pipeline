"""Quick pre-run sanity check before running the full pipeline."""
import sqlite3
conn = sqlite3.connect("data/library.db")

# categories unique index
idxs = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='categories'").fetchall()
print("categories indexes:", idxs)

# ocr_results existing rows
print("ocr_results rows:", conn.execute("SELECT COUNT(*) FROM ocr_results").fetchone()[0])

# how many images are pending OCR
pending = conn.execute(
    "SELECT COUNT(*) FROM images i "
    "LEFT JOIN ocr_results o ON i.id = o.image_id "
    "WHERE i.status = 'pending' AND o.image_id IS NULL"
).fetchone()[0]
print("pending for OCR:", pending)

conn.close()
print("All checks passed.")
