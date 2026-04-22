import sqlite3, os, sys

DB = os.path.join(os.path.dirname(__file__), "tmp", "icepot_dev.db")
if not os.path.exists(DB):
    print("DB not found:", DB)
    sys.exit(1)

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT id, status, error_message, created_at FROM transcription_jobs ORDER BY created_at DESC LIMIT 20")
rows = cur.fetchall()
if not rows:
    print("No jobs found")
else:
    print(f"Found {len(rows)} recent jobs:\n")
    for r in rows:
        print(r)
conn.close()
