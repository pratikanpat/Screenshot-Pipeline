import sqlite3
c = sqlite3.connect("data/library.db")
print("=== DATABASE SUMMARY ===")
print("Total images:    ", c.execute("SELECT COUNT(*) FROM images").fetchone()[0])
print("OCR done:        ", c.execute("SELECT COUNT(*) FROM images WHERE status='ocr_done'").fetchone()[0])
print("Classified:      ", c.execute("SELECT COUNT(*) FROM categories").fetchone()[0])
print("OCR results rows:", c.execute("SELECT COUNT(*) FROM ocr_results").fetchone()[0])
print("FTS index rows:  ", c.execute("SELECT COUNT(*) FROM fts_index").fetchone()[0])
print()
print("=== TOP CATEGORIES ===")
for row in c.execute("SELECT category, COUNT(*) as n FROM categories GROUP BY category ORDER BY n DESC LIMIT 10"):
    print(f"  {row[1]:5d}  {row[0]}")
print()
print("=== SAMPLE SEARCH: upi ===")
rows = c.execute(
    "SELECT i.filename, o.extracted_text FROM fts_index f "
    "JOIN images i ON i.id=f.image_id "
    "JOIN ocr_results o ON o.image_id=i.id "
    "WHERE fts_index MATCH 'upi' LIMIT 3"
).fetchall()
for row in rows:
    print(f"  {row[0]}: {row[1][:80]}")
c.close()

