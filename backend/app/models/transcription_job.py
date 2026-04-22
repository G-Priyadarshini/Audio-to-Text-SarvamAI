import uuid
import enum
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Enum,
    Integer,
    BigInteger,
    Text,
    DateTime,
)
from sqlalchemy.orm import relationship
from app.models.base import Base


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    STREAMING = "streaming"
    UPLOADING_TO_SARVAM = "uploading_to_sarvam"
    SARVAM_PROCESSING = "sarvam_processing"
    DOWNLOADING_RESULT = "downloading_result"
    COMPLETED = "completed"
    FAILED = "failed"


class JobMode(str, enum.Enum):
    REALTIME = "realtime"
    BATCH = "batch"


class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    language = Column(String(10), nullable=False, default="en-IN")
    status = Column(
        Enum(JobStatus),
        nullable=False,
        default=JobStatus.QUEUED,
    )
    mode = Column(
        Enum(JobMode),
        nullable=False,
        default=JobMode.BATCH,
    )
    duration_seconds = Column(Integer, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)
    source_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Sarvam Job API fields
    sarvam_job_id = Column(String(255), nullable=True, index=True)
    sarvam_upload_url = Column(Text, nullable=True)
    sarvam_state = Column(String(20), nullable=True)
    sarvam_poll_count = Column(Integer, nullable=True, default=0)
    sarvam_last_polled_at = Column(DateTime, nullable=True)

    # Relationships
    transcript = relationship(
        "Transcript",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )
    logs = relationship(
        "JobLog",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobLog.timestamp",
    )
