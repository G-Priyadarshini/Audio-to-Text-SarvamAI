import requests
import os

BASE = "http://127.0.0.1:8000"

print('Creating job...')
r = requests.post(f"{BASE}/api/jobs", json={"language": "en-IN", "mode": "batch"})
print('create:', r.status_code, r.text)
job = r.json()
job_id = job['id']
print('JOB_ID:', job_id)

path = 'tmp/test.wav'
size = os.path.getsize(path)
print('File size:', size)

print('Initializing upload...')
r = requests.post(f"{BASE}/api/jobs/{job_id}/upload/init", json={"total_chunks": 1, "file_size": size})
print('init:', r.status_code, r.text)

print('Uploading chunk...')
with open(path, 'rb') as f:
    files = {'file': ('test.wav', f, 'audio/wav')}
    r = requests.post(f"{BASE}/api/jobs/{job_id}/upload/chunks/0", files=files)
print('upload chunk:', r.status_code, r.text)

print('Completing...')
r = requests.post(f"{BASE}/api/jobs/{job_id}/upload/complete")
print('complete:', r.status_code, r.text)
