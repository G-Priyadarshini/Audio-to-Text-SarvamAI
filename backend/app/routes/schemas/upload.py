from pydantic import BaseModel, Field
from typing import List


class UploadInitRequest(BaseModel):
    total_chunks: int = Field(gt=0)
    file_size: int = Field(gt=0)


class UploadInitResponse(BaseModel):
    job_id: str
    total_chunks: int
    file_size: int
    message: str


class UploadStatusResponse(BaseModel):
    job_id: str
    total_chunks: int
    received_chunks: List[int]
    is_complete: bool


class UploadCompleteResponse(BaseModel):
    job_id: str
    status: str
    message: str
