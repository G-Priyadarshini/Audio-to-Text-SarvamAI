from arq.connections import RedisSettings
from app.config import settings
from app.queue.tasks import transcribe_batch
from app.queue.cron import cleanup_abandoned, poll_sarvam_jobs


class WorkerSettings:
    """arq worker settings."""

    functions = [transcribe_batch]
    cron_jobs = [cleanup_abandoned, poll_sarvam_jobs]

    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
    )

    max_jobs = 5
    job_timeout = 7200  # 2 hours max
    max_tries = 3
    retry_jobs = True
    health_check_interval = 30
