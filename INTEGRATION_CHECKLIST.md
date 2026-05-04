# Audio-to-Text Frontend Integration Checklist

## ✅ Completed Setup

- [x] Audio-to-Text Frontend Project Created
  - [x] Vite + React + TypeScript setup
  - [x] Package.json with dependencies
  - [x] tsconfig.json configuration
  - [x] Vite config with environment variable support
  - [x] index.html entry point

- [x] React Components Implemented
  - [x] AudioUploader - Drag-and-drop file upload
  - [x] AudioRecorder - Live audio recording from microphone
  - [x] TranscriptionResult - Display and edit transcriptions
  - [x] LanguageSelector - Multi-language support
  - [x] App.tsx - Main application logic with auth and health checks

- [x] API Integration Layer
  - [x] api.ts - Service layer for backend communication
  - [x] types.ts - TypeScript interfaces for type safety
  - [x] Authentication handling via cookies
  - [x] Health monitoring (every 15 seconds)
  - [x] Error handling with user feedback

- [x] EMS Frontend Integration
  - [x] AudioToTextPage.js component created
  - [x] Route added to App.js
  - [x] Sidebar navigation with ATS icon
  - [x] Environment variables configured (.env.development & .env.production)

- [x] Documentation
  - [x] README.md for frontend project
  - [x] DEPLOYMENT_GUIDE.md with step-by-step instructions
  - [x] Project structure documentation

## 📋 Next Steps - Deployment

### 1. Install Frontend Dependencies

```bash
cd Audio-to-Text-SarvamAI/frontend
npm install
```

### 2. Configure Backend URLs

Update environment variables as needed:

**Development:**
- Backend: `http://localhost:8000`
- Frontend Audio-to-Text: `http://localhost:5175`

**Production:**
- Backend: `https://ems.beqisoft.net/api/audio-to-text` (configure as needed)
- Frontend Audio-to-Text: `https://ems.beqisoft.net/audio-to-text` (configure as needed)

### 3. Start Development Servers

```bash
# Terminal 1: EMS Frontend
cd AttendanceFrontEnd
npm start

# Terminal 2: Audio-to-Text Frontend
cd Audio-to-Text-SarvamAI/frontend
npm run dev

# Terminal 3: Audio-to-Text Backend
cd Audio-to-Text-SarvamAI/backend
python run.py
```

### 4. Test Integration

1. Navigate to EMS at `http://localhost:3000`
2. Login with your credentials
3. Look for "ATS" icon in the sidebar (if AUDIO_TO_TEXT_MODULE is enabled)
4. Click to navigate to Audio-to-Text page
5. Try uploading/recording audio
6. Verify transcription works

### 5. Configure User Permissions

Add `AUDIO_TO_TEXT_MODULE` to users who should have access:

```sql
-- Example: Add module to a specific user
UPDATE user_profiles 
SET modules = JSON_ARRAY_APPEND(modules, '$', 'AUDIO_TO_TEXT_MODULE')
WHERE user_id = 'your_user_id';
```

### 6. Build for Production

```bash
cd Audio-to-Text-SarvamAI/frontend
npm run build
```

Output will be in `dist/` directory - deploy this to your web server.

### 7. Backend Deployment

```bash
# Install production dependencies
pip install -r Audio-to-Text-SarvamAI/backend/requirements.txt

# Setup database
python Audio-to-Text-SarvamAI/backend/create_tables.py

# Start backend with production settings
# Use uvicorn or gunicorn with SSL
uvicorn app.main:app --host 0.0.0.0 --port 8000 --ssl-keyfile=/path/to/key.pem --ssl-certfile=/path/to/cert.pem
```

## 🔧 Configuration Details

### Backend CORS Configuration

Ensure your backend's CORS middleware includes:
```python
origins = [
    "http://localhost:5173",
    "http://localhost:5175",
    "https://ems.beqisoft.net",
]
```

### Environment Variables

**AttendanceFrontEnd/.env.development:**
```
REACT_APP_AUDIO_TO_TEXT_BASE_URL=http://localhost:5000
```

**AttendanceFrontEnd/.env.production:**
```
REACT_APP_AUDIO_TO_TEXT_BASE_URL=https://ems.beqisoft.net/audio-to-text
```

**Audio-to-Text-SarvamAI/frontend/.env.development:**
```
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_PORT=5175
```

**Audio-to-Text-SarvamAI/frontend/.env.production:**
```
VITE_API_BASE_URL=https://ems.beqisoft.net/api/audio-to-text
VITE_BASE_PATH=/audio-to-text/
```

## 🧪 Testing Checklist

### Functional Testing
- [ ] Audio file upload works
- [ ] Live recording works
- [ ] Language selection changes
- [ ] Transcription results display
- [ ] Edit transcription works
- [ ] Copy to clipboard works
- [ ] Download as .txt file works
- [ ] Backend health status updates

### Integration Testing
- [ ] Sidebar icon appears for authorized users
- [ ] Navigation to Audio-to-Text works
- [ ] Authentication redirects to login if not logged in
- [ ] Auth token is properly sent to backend

### Error Handling
- [ ] Backend offline message displays
- [ ] Invalid file format shows error
- [ ] Upload failure shows retry option
- [ ] Transcription errors display with details
- [ ] Session timeout redirects to login

### Performance
- [ ] Frontend loads quickly
- [ ] Large audio files upload without timeout
- [ ] No memory leaks with repeated use

## 📦 Project Structure

```
Audio-to-Text-SarvamAI/
├── frontend/                 # NEW - Vite/React application
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── types/            # TypeScript interfaces
│   │   ├── App.tsx           # Main app
│   │   ├── api.ts            # API service
│   │   ├── main.tsx          # Entry point
│   │   └── index.css         # Styles
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── README.md
│   └── .env.* files
├── backend/                  # Existing backend
│   ├── app/
│   ├── requirements.txt
│   └── run.py
└── DEPLOYMENT_GUIDE.md       # Deployment instructions

AttendanceFrontEnd/
├── src/
│   ├── pages/
│   │   └── audiototextpage.js # NEW - Navigation page
│   └── App.js                 # UPDATED - Added route
├── .env.development           # UPDATED - Added REACT_APP_AUDIO_TO_TEXT_BASE_URL
└── .env.production            # UPDATED - Added REACT_APP_AUDIO_TO_TEXT_BASE_URL
```

## 🚀 Deployment Options

### Option 1: Local Development
Best for testing and development:
- Run all services locally on different ports
- Use .env.development configurations
- Direct port access (5173, 5175, 8000)

### Option 2: Docker Containers
Best for consistent environments:
- Create Dockerfile for frontend and backend
- Use Docker Compose to orchestrate services
- Configure container networking

### Option 3: Single Domain Deployment
Best for production:
- Build frontend and serve from same domain
- Use reverse proxy (Nginx/Apache) for routing
- SSL/HTTPS for secure communication

### Option 4: Microservices Deployment
Best for scalability:
- Deploy frontend to CDN or static hosting
- Deploy backend to app server (AWS EC2, Heroku, etc.)
- Configure CORS for cross-domain communication

## ⚠️ Important Notes

1. **Authentication**: Audio-to-Text app reads `_auth` cookie from EMS. Ensure cookies are shared across subdomains.

2. **CORS**: Backend must explicitly allow requests from frontend domains.

3. **Token Refresh**: If tokens expire, user is automatically redirected to login.

4. **Backend Health**: Frontend checks backend health every 15 seconds. UI shows offline status.

5. **File Size**: Recommend limiting audio uploads to <100MB.

6. **Browser Support**: Works on all modern browsers with Web Audio API support.

## 📞 Support & Troubleshooting

See DEPLOYMENT_GUIDE.md for detailed troubleshooting section.

Common issues:
- CORS errors → Check backend CORS configuration
- Authentication failures → Clear cookies, re-login
- Backend offline → Verify backend is running and accessible
- Module not visible → Check user has AUDIO_TO_TEXT_MODULE permission
