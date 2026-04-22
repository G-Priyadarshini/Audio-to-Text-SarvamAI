from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class JobModeEnum(str, Enum):
    REALTIME = "realtime"
    BATCH = "batch"


class JobStatusEnum(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    STREAMING = "streaming"
    UPLOADING_TO_SARVAM = "uploading_to_sarvam"
    SARVAM_PROCESSING = "sarvam_processing"
    DOWNLOADING_RESULT = "downloading_result"
    COMPLETED = "completed"
    FAILED = "failed"


class JobCreate(BaseModel):
    language: str = Field(default="en-IN", max_length=10)
    mode: JobModeEnum = Field(default=JobModeEnum.BATCH)


class JobResponse(BaseModel):
    id: str
    language: str
    status: JobStatusEnum
    mode: JobModeEnum
    duration_seconds: Optional[int] = None
    file_size: Optional[int] = None
    retry_count: int = 0
    error_message: Optional[str] = None
    sarvam_job_id: Optional[str] = None
    sarvam_state: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobStatusResponse(BaseModel):
    id: str
    status: JobStatusEnum
    error_message: Optional[str] = None
    sarvam_job_id: Optional[str] = None
    sarvam_state: Optional[str] = None
    sarvam_poll_count: Optional[int] = None


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    limit: int
    has_next: bool
