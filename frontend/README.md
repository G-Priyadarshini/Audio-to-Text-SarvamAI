# Audio to Text Frontend

A Vite + React TypeScript web application for audio transcription.

## Features

- **Audio Upload**: Drag-and-drop or click to upload audio files
- **Live Recording**: Record audio directly from the browser
- **Multi-language Support**: Supports 13+ languages including Indian regional languages
- **Real-time Transcription**: Convert audio to text using the backend API
- **Text Editing**: Edit and refine transcription results
- **Download**: Save transcriptions as text files
- **Copy to Clipboard**: Quickly copy transcription text
- **Backend Health Monitoring**: Real-time status of the transcription service

## Setup

### Prerequisites

- Node.js 16+ and npm/yarn
- Audio-to-Text backend running on `http://localhost:8000`

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

The app will start on `http://localhost:5000`

### Building

```bash
npm run build
```

## Environment Variables

Create a `.env.local` file in the root directory:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_BASE_PATH=/
VITE_APP_PORT=5000
VITE_EMS_BASE_URL=https://ems.beqisoft.net
```

## Project Structure

```
src/
├── components/          # React components
│   ├── AudioUploader.tsx       # File upload component
│   ├── AudioRecorder.tsx       # Live recording component
│   ├── TranscriptionResult.tsx # Results display
│   └── LanguageSelector.tsx    # Language selection
├── pages/               # Page components
├── types/               # TypeScript interfaces
├── utils/               # Utility functions
├── App.tsx              # Main app component
├── api.ts               # API service
├── main.tsx             # Entry point
└── index.css            # Global styles
```

## Authentication

The app reads the auth token from cookies (`_auth`) and verifies it with the backend before allowing access.

## API Endpoints

- `GET /health` - Check backend health
- `GET /auth/verify` - Verify authentication token
- `POST /AudioToText` - Submit audio for transcription
- `GET /AudioToText/{jobId}` - Get transcription status/result

## License

MIT
