"""Requeue FAILED jobs so the worker can process them again.

Usage: python requeue_failed.py
"""
import sqlite3
import os
from datetime import datetime

DB = os.path.join(os.path.dirname(__file__), "tmp", "icepot_dev.db")

if not os.path.exists(DB):
    print("DB not found:", DB)
    raise SystemExit(1)

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Requeue jobs that failed or are stuck in processing
cur.execute("SELECT id, status, error_message FROM transcription_jobs WHERE status IN ('FAILED','PROCESSING','QUEUED') ORDER BY created_at DESC")
rows = cur.fetchall()
if not rows:
    print("No failed/processing/queued jobs found")
    conn.close()
    raise SystemExit(0)

print(f"Found {len(rows)} jobs to requeue (setting to QUEUED)")
for r in rows:
    job_id, status, error = r
    print("requeueing", job_id, status, error)
    cur.execute("UPDATE transcription_jobs SET status='QUEUED', error_message=NULL, retry_count=0, updated_at=? WHERE id=?", (datetime.utcnow(), job_id))

conn.commit()
conn.close()
print("Done requeuing jobs")
