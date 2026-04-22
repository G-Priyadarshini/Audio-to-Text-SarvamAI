import logging
from datetime import datetime
from arq.cron import cron
from redis.asyncio import Redis
from sqlalchemy import select
from app.database import async_session
from app.models.transcription_job import TranscriptionJob, JobStatus
from app.services.sarvam_service import SarvamClient
from app.services.upload_service import UploadService
from app.services.log_service import LogService
from app.queue.tasks import complete_sarvam_download

logger = logging.getLogger("icepot")


async def _cleanup_task(ctx: dict):
    """Periodic cleanup of abandoned uploads."""
    redis: Redis = ctx.get("redis")
    if redis:
        cleaned = await UploadService.cleanup_abandoned_uploads(redis)
        if cleaned > 0:
            logger.info(f"Cleaned {cleaned} abandoned uploads")


async def _poll_sarvam_jobs(ctx: dict):
    """
    Cron fallback: pick up orphaned SARVAM_PROCESSING jobs and drive
    them to completion. Catches jobs where the in-task poll loop was
    interrupted (worker crash, restart, etc.).
    """
    async with async_session() as session:
        stmt = select(TranscriptionJob).where(
            TranscriptionJob.status == JobStatus.SARVAM_PROCESSING,
            TranscriptionJob.sarvam_job_id.isnot(None),
        )
        result = await session.execute(stmt)
        jobs = result.scalars().all()

        if not jobs:
            return

        sarvam = SarvamClient()
        logger.info(f"Cron: checking {len(jobs)} orphaned Sarvam jobs")

        for job in jobs:
            try:
                status = await sarvam.poll_sarvam_status(job.sarvam_job_id)
                state = status.get("job_state", "Unknown")

                job.sarvam_state = state
                job.sarvam_poll_count = (job.sarvam_poll_count or 0) + 1
                job.sarvam_last_polled_at = datetime.utcnow()

                if state == "Completed":
                    logger.info(
                        f"Cron: Sarvam job {job.sarvam_job_id} completed. "
                        f"Triggering download for job {job.id}"
                    )
                    full_text = await complete_sarvam_download(
                        session, sarvam, job, status
                    )
                    await LogService.info(
                        session, job.id,
                        f"Cron recovery: transcription complete ({len(full_text)} chars)",
                        "cron",
                    )

                elif state == "Failed":
                    logger.warning(
                        f"Cron: Sarvam job {job.sarvam_job_id} failed "
                        f"for job {job.id}"
                    )
                    job.status = JobStatus.FAILED
                    job.error_message = f"Sarvam job failed: {status}"
                    await session.commit()
                    await LogService.error(
                        session, job.id,
                        f"Cron: Sarvam job failed",
                        "cron",
                    )

                else:
                    # Still running — just update poll count
                    await session.commit()

            except Exception as e:
                logger.exception(
                    f"Cron: error polling Sarvam job for {job.id}: {e}"
                )


cleanup_abandoned = cron(
    _cleanup_task,
    minute={0, 15, 30, 45},  # Every 15 minutes
)

poll_sarvam_jobs = cron(
    _poll_sarvam_jobs,
    second={0, 30},  # Every 30 seconds
)
