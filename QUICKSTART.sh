#!/usr/bin/env bash

# Quick Start Script for Audio-to-Text Integration
# This script sets up all necessary components for development

set -e  # Exit on error

echo "=================================="
echo "Audio-to-Text Integration Setup"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Node.js is installed
echo -e "${YELLOW}Checking prerequisites...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}Node.js is not installed. Please install Node.js 16+ from https://nodejs.org/${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js $(node -v)${NC}"

if ! command -v python &> /dev/null; then
    echo -e "${RED}Python is not installed. Please install Python 3.8+ from https://www.python.org/${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $(python --version)${NC}"

echo ""
echo -e "${YELLOW}Installing Audio-to-Text Frontend...${NC}"
cd "$(dirname "$0")/frontend"
npm install
echo -e "${GREEN}✓ Frontend dependencies installed${NC}"

echo ""
echo -e "${YELLOW}Installing Audio-to-Text Backend...${NC}"
cd "$(dirname "$0")/backend"
pip install -r requirements.txt
echo -e "${GREEN}✓ Backend dependencies installed${NC}"

echo ""
echo -e "${GREEN}=================================="
echo "Setup Complete!"
echo "==================================${NC}"
echo ""
echo "To start development servers, run:"
echo ""
echo "  Terminal 1 - EMS Frontend:"
echo "    cd AttendanceFrontEnd && npm start"
echo ""
echo "  Terminal 2 - Audio-to-Text Frontend:"
echo "    cd Audio-to-Text-SarvamAI/frontend && npm run dev"
echo ""
echo "  Terminal 3 - Audio-to-Text Backend:"
echo "    cd Audio-to-Text-SarvamAI/backend && python run.py"
echo ""
echo "Then navigate to http://localhost:3000 in your browser"
echo ""
echo -e "${YELLOW}For detailed setup instructions, see: DEPLOYMENT_GUIDE.md${NC}"
echo ""
