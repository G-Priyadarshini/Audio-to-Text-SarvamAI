import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship
from app.models.base import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(
        String(36),
        ForeignKey("transcription_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    full_text = Column(Text(length=4294967295), nullable=False, default="")
    diarized_json = Column(JSON, nullable=True)
    segments_json = Column(JSON, nullable=True)  # timestamps for SRT/VTT
    format_version = Column(String(10), nullable=False, default="1.0")
    edited = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    job = relationship("TranscriptionJob", back_populates="transcript")
