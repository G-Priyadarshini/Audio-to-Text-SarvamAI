"""
Authentication schemas
"""

from pydantic import BaseModel


class AuthResponse(BaseModel):
    success: bool
    message: str
