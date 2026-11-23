import sqlite3

conn = sqlite3.connect("data/library.db")
cols = [r[1] for r in conn.execute("PRAGMA table_info(images)")]
print("images columns:", cols)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables:", tables)
count = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
print("image count:", count)
conn.close()

