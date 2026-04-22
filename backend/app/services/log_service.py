import logging
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job_log import JobLog

logger = logging.getLogger("icepot")


class LogService:
    """Structured logging to both database and console."""

    @staticmethod
    async def log(
        session: AsyncSession,
        job_id: str,
        level: str,
        message: str,
        stage: Optional[str] = None,
    ):
        """Write log entry to DB and console."""
        # Database log
        log_entry = JobLog(
            job_id=job_id,
            level=level.upper(),
            stage=stage,
            message=message,
        )
        session.add(log_entry)
        await session.commit()

        # Console log (structured JSON)
        log_data = {
            "job_id": job_id,
            "stage": stage,
            "level": level.upper(),
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        log_func = getattr(logger, level.lower(), logger.info)
        log_func(json.dumps(log_data))

    @staticmethod
    async def info(
        session: AsyncSession,
        job_id: str,
        message: str,
        stage: Optional[str] = None,
    ):
        await LogService.log(session, job_id, "INFO", message, stage)

    @staticmethod
    async def error(
        session: AsyncSession,
        job_id: str,
        message: str,
        stage: Optional[str] = None,
    ):
        await LogService.log(session, job_id, "ERROR", message, stage)

    @staticmethod
    async def warning(
        session: AsyncSession,
        job_id: str,
        message: str,
        stage: Optional[str] = None,
    ):
        await LogService.log(session, job_id, "WARNING", message, stage)
