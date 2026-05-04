"""
Authentication routes - Verify JWT tokens from EMS/Auth system
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.schemas.auth import AuthResponse
import logging

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("icepot")


@router.get("/verify", response_model=AuthResponse)
async def verify_token(
    request: Request,
    authorization: str = Header(None),
    session: AsyncSession = Depends(get_session),
):
    """
    Verify authentication token from EMS/Auth system.
    
    Expects Authorization header with Bearer token.
    Returns success if token is valid (format check only).
    
    In production, validate token with EMS backend.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    # Extract bearer token
    auth_parts = authorization.split()
    if len(auth_parts) != 2 or auth_parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = auth_parts[1]
    
    # In development, accept any token format (non-empty)
    # In production, validate with EMS backend
    if not token or len(token) < 10:
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    logger.info(f"Token verified for request from {request.client.host if request.client else 'unknown'}")
    
    return AuthResponse(success=True, message="Token verified successfully")
