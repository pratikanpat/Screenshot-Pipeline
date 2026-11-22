import sqlite3

DB_PATH = "data/library.db"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print("\n========== DATABASE TABLES ==========")

tables = conn.execute("""
    SELECT name FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
""").fetchall()

for table in tables:
    print("-", table["name"])

print("\n========== OCR CANDIDATE SCHEMA ==========")

columns = conn.execute(
    "PRAGMA table_info(ocr_candidates)"
).fetchall()

for col in columns:
    print(dict(col))

print("\n========== CANDIDATE COUNTS ==========")

try:
    rows = conn.execute("""
        SELECT language, COUNT(*) AS total
        FROM ocr_candidates
        GROUP BY language
        ORDER BY total DESC
    """).fetchall()

    for row in rows:
        print(f"{row['language']}: {row['total']}")

except sqlite3.Error as e:
    print("Could not inspect candidates:", e)

print("\n========== OCR QUALITY SUMMARY ==========")

rows = conn.execute("""
    SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN extracted_text IS NULL
            OR TRIM(extracted_text) = '' THEN 1 ELSE 0 END) AS empty,
        ROUND(AVG(confidence), 2) AS avg_confidence,
        SUM(CASE WHEN confidence < 30 THEN 1 ELSE 0 END) AS low_confidence
    FROM ocr_results
""").fetchone()

print(dict(rows))

conn.close()