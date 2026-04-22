from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class TranscriptResponse(BaseModel):
    id: str
    job_id: str
    full_text: str
    diarized_json: Optional[Any] = None
    segments_json: Optional[Any] = None
    format_version: str
    edited: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TranscriptUpdate(BaseModel):
    full_text: str
