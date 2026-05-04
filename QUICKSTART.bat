@echo off
REM Quick Start Script for Audio-to-Text Integration (Windows)
REM This script sets up all necessary components for development

setlocal enabledelayedexpansion

echo ==================================
echo Audio-to-Text Integration Setup
echo ==================================
echo.

REM Check if Node.js is installed
echo Checking prerequisites...
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Node.js is not installed. Please install Node.js 16+ from https://nodejs.org/
    exit /b 1
)
for /f "tokens=*" %%i in ('node -v') do set NODE_VERSION=%%i
echo [OK] Node.js %NODE_VERSION%

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed. Please install Python 3.8+ from https://www.python.org/
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] %PYTHON_VERSION%

echo.
echo Installing Audio-to-Text Frontend...
cd /d "%~dp0frontend"
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo Error: Frontend installation failed
    exit /b 1
)
echo [OK] Frontend dependencies installed

echo.
echo Installing Audio-to-Text Backend...
cd /d "%~dp0backend"
call pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Error: Backend installation failed
    exit /b 1
)
echo [OK] Backend dependencies installed

echo.
echo ==================================
echo Setup Complete!
echo ==================================
echo.
echo To start development servers, run in separate terminals:
echo.
echo   Terminal 1 - EMS Frontend:
echo     cd AttendanceFrontEnd ^&^& npm start
echo.
echo   Terminal 2 - Audio-to-Text Frontend:
echo     cd Audio-to-Text-SarvamAI\frontend ^&^& npm run dev
echo.
echo   Terminal 3 - Audio-to-Text Backend:
echo     cd Audio-to-Text-SarvamAI\backend ^&^& python run.py
echo.
echo Then navigate to http://localhost:3000 in your browser
echo.
echo For detailed setup instructions, see: DEPLOYMENT_GUIDE.md
echo.
pause
