import sqlite3
import os

db = os.path.join(os.path.dirname(__file__), 'tmp', 'icepot_dev.db')
print('db', db)
print('exists', os.path.exists(db))
if not os.path.exists(db):
    raise SystemExit('DB file not found')
conn = sqlite3.connect(db)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('tables', tables)
conn.close()
