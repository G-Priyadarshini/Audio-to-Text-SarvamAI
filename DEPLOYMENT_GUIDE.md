# Audio-to-Text Integration Setup Guide

## Overview

This document provides step-by-step instructions for deploying and integrating the Audio-to-Text web application with the EMS (Attendance Frontend) system.

## Phase 1: Frontend Setup (Audio-to-Text-SarvamAI/frontend)

### 1.1 Install Dependencies

```bash
cd Audio-to-Text-SarvamAI/frontend
npm install
```

### 1.2 Development Server

Start the development server:

```bash
npm run dev
```

The app will be available at `http://localhost:5175`

### 1.3 Build for Production

```bash
npm run build
```

The build output will be in the `dist/` directory.

## Phase 2: Backend Setup (Audio-to-Text-SarvamAI/backend)

### 2.1 Install Dependencies

```bash
cd Audio-to-Text-SarvamAI/backend
pip install -r requirements.txt
```

### 2.2 Database Setup

```bash
python create_tables.py
```

### 2.3 Start the Server

```bash
python run.py
```

The backend will run on `http://localhost:8000` by default.

### 2.4 CORS Configuration

Ensure your backend allows CORS requests from the frontend domains. Update `app/middleware/` to include:

```python
origins = [
    "http://localhost:5173",  # AttendanceFrontend dev
    "http://localhost:5174",  # Resume Checker dev
    "http://localhost:5175",  # Audio-to-Text dev
    "https://ems.beqisoft.net",  # Production domain
]
```

## Phase 3: EMS Frontend Integration

The following changes have already been made:

### 3.1 Route Addition (App.js)
- ✅ Added `/audio-to-text` route
- ✅ Added `AudioToTextPage` component import

### 3.2 Sidebar Navigation (Sidebar.js)
- ✅ Added "ATS" icon for Audio-to-Text
- ✅ Configured module-based visibility (`AUDIO_TO_TEXT_MODULE`)

### 3.3 Environment Variables (.env files)
- ✅ `.env.development`: `REACT_APP_AUDIO_TO_TEXT_BASE_URL=http://localhost:5000`
- ✅ `.env.production`: `REACT_APP_AUDIO_TO_TEXT_BASE_URL=https://ems.beqisoft.net/audio-to-text`

## Phase 4: Deployment

### 4.1 Local Development

```bash
# Terminal 1: Start EMS Frontend
cd AttendanceFrontEnd
npm start

# Terminal 2: Start Audio-to-Text Frontend
cd Audio-to-Text-SarvamAI/frontend
npm run dev

# Terminal 3: Start Audio-to-Text Backend
cd Audio-to-Text-SarvamAI/backend
python run.py
```

Access EMS at `http://localhost:3000` (or configured port)

### 4.2 Production Deployment

#### Option A: Single Domain Deployment (Recommended)

1. Build Audio-to-Text frontend:
   ```bash
   cd Audio-to-Text-SarvamAI/frontend
   npm run build
   ```

2. Deploy `dist/` folder to your web server at `/audio-to-text/` path

3. Update environment variables:
   ```
   REACT_APP_AUDIO_TO_TEXT_BASE_URL=https://ems.beqisoft.net/audio-to-text
   ```

4. Configure Nginx/Apache to proxy `/audio-to-text/` to the built app

#### Option B: Separate Deployment

1. Deploy Audio-to-Text frontend to a separate domain (e.g., `https://audio.yourdomain.com`)

2. Update EMS environment:
   ```
   REACT_APP_AUDIO_TO_TEXT_BASE_URL=https://audio.yourdomain.com
   ```

3. Ensure backend CORS allows the frontend domain

### 4.3 Backend Deployment

1. Set environment variables:
   ```
   DATABASE_URL=mysql://user:password@host:port/dbname
   API_PORT=8000
   ```

2. Run migrations:
   ```bash
   python -m alembic upgrade head
   ```

3. Start the backend (with gunicorn or uvicorn):
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

4. Use a reverse proxy (Nginx/Apache) with SSL

## Phase 5: User Permissions

### 5.1 Enable Module for Users

Add `AUDIO_TO_TEXT_MODULE` to user's modules array in the backend:

```sql
INSERT INTO user_modules (user_id, module_name) 
VALUES (user_id, 'AUDIO_TO_TEXT_MODULE');
```

Or add to user profile during user creation.

### 5.2 Verify Sidebar Visibility

The "ATS" icon in the sidebar will only appear for users with `AUDIO_TO_TEXT_MODULE` permission.

## Phase 6: Testing

### 6.1 Integration Testing

1. ✅ Navigate to EMS home page
2. ✅ Verify "ATS" icon appears in sidebar (for authorized users)
3. ✅ Click "ATS" to navigate to Audio-to-Text page
4. ✅ Verify authentication redirects to login if not logged in
5. ✅ Upload/record audio file
6. ✅ Verify transcription results appear
7. ✅ Test edit, copy, and download features

### 6.2 Error Handling

- ✅ Backend offline: Shows "Offline" status with error message
- ✅ Invalid audio format: Shows validation error
- ✅ Upload failure: Displays error with retry option
- ✅ Session timeout: Redirects to login page

### 6.3 Performance Testing

- Test with various audio file sizes
- Verify response times for transcription
- Monitor network usage

## Phase 7: Troubleshooting

### Issue: "Backend is offline"

**Solution**: 
1. Verify backend is running: `http://localhost:8000/health`
2. Check CORS configuration
3. Verify firewall allows requests

### Issue: "Unauthorized: Invalid or expired token"

**Solution**:
1. Clear browser cookies
2. Re-login to EMS
3. Verify token expiration time

### Issue: Audio upload fails

**Solution**:
1. Check audio file format (MP3, WAV, OGG, WebM)
2. Verify file size is reasonable (<100MB recommended)
3. Check backend logs for detailed error

### Issue: "Module not found" in sidebar

**Solution**:
1. Verify user has `AUDIO_TO_TEXT_MODULE` permission
2. Check that user.modules array includes the module
3. Clear browser cache and reload

## Phase 8: Monitoring & Maintenance

### 8.1 Log Files

Backend logs: `Audio-to-Text-SarvamAI/backend/logs/`

Check for:
- Failed transcriptions
- API errors
- Performance issues

### 8.2 Health Checks

Frontend performs health checks every 15 seconds:
- Watch browser console for health status
- Monitor `GET /health` endpoint

### 8.3 Database Maintenance

```bash
# List jobs and status
python list_jobs.py

# Requeue failed jobs
python requeue_failed.py
```

## Additional Resources

- [Audio-to-Text Backend README](../backend/README.md)
- [EMS Frontend Repository](https://github.com/yourusername/ems-frontend)
- [Sarvam AI API Documentation](https://sarvam.ai/docs)

## Support

For issues or questions:
1. Check logs in both frontend console and backend
2. Verify all services are running
3. Check network requests in browser DevTools
4. Consult troubleshooting section above
