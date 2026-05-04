"""
Sample CORS Configuration for Audio-to-Text Backend

Add this configuration to your FastAPI app if CORS errors occur.
Location: app/middleware/cors.py (or similar)
"""

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

def setup_cors(app: FastAPI, environment: str = "development"):
    """
    Setup CORS middleware for the FastAPI application.
    
    Args:
        app: FastAPI application instance
        environment: "development" or "production"
    """
    
    if environment == "development":
        origins = [
            "http://localhost:3000",      # EMS Frontend dev
            "http://localhost:5000",      # Audio-to-Text dev
            "http://localhost:5173",      # Test Gen dev
            "http://localhost:5174",      # Resume Checker dev
            "http://localhost:5175",      # Audio-to-Text dev
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:5175",
        ]
    else:  # production
        origins = [
            "https://ems.beqisoft.net",
            "https://www.ems.beqisoft.net",
        ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=3600,
    )


# Usage in main.py:
# 
# from fastapi import FastAPI
# from app.middleware.cors import setup_cors
# import os
#
# app = FastAPI()
# 
# # Setup CORS
# environment = os.getenv("ENVIRONMENT", "development")
# setup_cors(app, environment)
#
# # ... rest of app configuration
