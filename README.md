# ICEPOT — Audio to Text (STT) Chrome Extension

A Chrome Extension (MV3) with FastAPI backend for audio-to-text transcription powered by **Sarvam AI**.

## Features

- **Microphone recording** — capture from mic with live waveform
- **Tab audio capture** — transcribe any browser tab audio (preserves user playback)
- **File upload** — drag-and-drop WAV/MP3/OGG/FLAC (up to 500 MB / 2 hrs)
- **Real-time streaming** — live partial transcripts via SSE
- **Batch processing** — diarized output with speaker labels
- **Chunked uploads** — resumable 5 MB chunks with retry
- **Export** — TXT, SRT, VTT formats
- **Editable transcripts** — edit and save corrections
- **Job history** — browse and reload past transcriptions

## Architecture

```
┌────────────────┐       HTTP / SSE       ┌─────────────┐
│ Chrome Ext MV3 │ ◄──────────────────► │  FastAPI     │
│  (Popup + UI)  │                        │  Backend     │
└────────────────┘                        └──────┬──────┘
                                                  │
                                    ┌─────────────┼─────────────┐
                                    │             │             │
                                ┌───▼───┐   ┌────▼────┐   ┌───▼───┐
                                │ MySQL │   │  Redis  │   │Sarvam │
                                │  8.0  │   │   7.0   │   │AI API │
                                └───────┘   └─────────┘   └───────┘
```

## Quick Start

### 1. Prerequisites

- Python 3.10+
- MySQL 8.0
- Redis 7
- Docker & Docker Compose (optional)

### 2. Backend Setup

```bash
cd backend

# Option A: Docker (MySQL + Redis)
docker compose up -d

# Option B: Native — install MySQL/Redis manually
```

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

# Install deps
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — set SARVAM_API_KEY and database credentials

# Run migrations
alembic upgrade head

# Start server
python run.py
```

```bash
# Start arq worker (separate terminal)
arq app.queue.settings.WorkerSettings
```

### 3. Chrome Extension

1. Open `chrome://extensions/`
2. Enable **Developer mode**
3. Click **Load unpacked** → select the `extension/` folder
4. Click the ICEPOT icon → **Open Transcription App**

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/jobs` | Create transcription job |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/jobs/{id}` | Get job detail |
| `GET` | `/api/jobs/{id}/status` | Get job status |
| `DELETE` | `/api/jobs/{id}` | Delete job |
| `POST` | `/api/uploads/init` | Init chunked upload |
| `POST` | `/api/uploads/{id}/chunk` | Upload a chunk |
| `GET` | `/api/uploads/{id}/status` | Upload Status |
| `POST` | `/api/uploads/{id}/complete` | Finalize upload |
| `GET` | `/api/transcripts/{id}` | Get transcript |
| `PUT` | `/api/transcripts/{id}` | Update transcript |
| `GET` | `/api/transcripts/{id}/download` | Download (txt/srt/vtt) |
| `POST` | `/api/stream/audio` | Send audio chunk (real-time) |
| `POST` | `/api/stream/end` | End stream |
| `GET` | `/api/stream` | SSE transcript events |

## Supported Languages

| Code | Language |
|------|----------|
| `hi-IN` | Hindi |
| `bn-IN` | Bengali |
| `kn-IN` | Kannada |
| `ml-IN` | Malayalam |
| `mr-IN` | Marathi |
| `od-IN` | Odia |
| `pa-IN` | Punjabi |
| `ta-IN` | Tamil |
| `te-IN` | Telugu |
| `en-IN` | English (Indian) |
| `gu-IN` | Gujarati |
| `auto` | Auto-detect |

## Limits

| Parameter | Value |
|-----------|-------|
| Max file size | 500 MB |
| Max duration | 2 hours (7200 s) |
| Chunk size | 5 MB |
| Rate: job creation | 10/min |
| Rate: chunk upload | 100/min |
| Max concurrent jobs | 5 |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory
│   │   ├── config.py            # Settings
│   │   ├── database.py          # Async SQLAlchemy
│   │   ├── models/              # ORM models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/            # Business logic
│   │   ├── routes/              # API endpoints
│   │   ├── queue/               # arq tasks & worker
│   │   ├── middleware/          # Rate limiting
│   │   └── utils/               # Helpers
│   ├── alembic/                 # DB migrations
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── run.py
├── extension/
│   ├── manifest.json
│   ├── popup.html / popup.js
│   ├── service-worker.js
│   ├── offscreen.html / offscreen.js
│   ├── extension-page.html / extension-page.js
│   ├── styles/main.css
│   ├── utils/                   # JS utilities
│   └── icons/
└── README.md
```

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy 2.0 (async), Alembic, arq, Redis, MySQL
- **Extension**: Chrome MV3, vanilla JS, SSE
- **STT**: Sarvam AI (REST + WebSocket)
- **Infra**: Docker Compose (optional)

## License

Private — Internal use only.
