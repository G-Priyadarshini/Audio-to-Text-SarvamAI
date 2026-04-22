import os
import re
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])

# Absolute path to backend/.env (same file pydantic reads at startup)
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


class SettingsUpdate(BaseModel):
    sarvam_api_key: Optional[str] = None


def _update_env_file(key: str, value: str):
    """Write or update a key=value line in the .env file."""
    env_path = _ENV_PATH
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        if pattern.search(content):
            content = pattern.sub(f"{key}={value}", content)
        else:
            content = content.rstrip("\n") + f"\n{key}={value}\n"
    else:
        content = f"{key}={value}\n"
    env_path.write_text(content, encoding="utf-8")


def _set_runtime(key: str, value: str):
    """Update a settings field at runtime."""
    try:
        setattr(settings, key, value)
    except Exception:
        settings.__dict__[key] = value


@router.post("")
async def update_settings(body: SettingsUpdate):
    """Update API key: writes to .env and updates runtime immediately."""
    if body.sarvam_api_key is not None:
        _set_runtime("SARVAM_API_KEY", body.sarvam_api_key)
        _update_env_file("SARVAM_API_KEY", body.sarvam_api_key)
    return {
        "message": "Settings updated",
        "sarvam_api_key_set": bool(settings.SARVAM_API_KEY),
    }


@router.get("")
async def get_settings():
    """Return current API key value so the frontend can pre-fill on load."""
    return {
        "sarvam_api_key": settings.SARVAM_API_KEY or "",
    }
