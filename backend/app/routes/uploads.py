from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_session
from app.models.transcription_job import TranscriptionJob, JobStatus
from app.schemas.upload import (
    UploadInitRequest,
    UploadInitResponse,
    UploadStatusResponse,
    UploadCompleteResponse,
)
from app.middleware.rate_limit import limiter, CHUNKS_RATE_LIMIT
from app.services.upload_service import UploadService
from app.services.log_service import LogService
from app.utils.dependencies import get_redis, get_upload_service
from app.config import settings
import asyncio
import logging

logger = logging.getLogger("icepot")

router = APIRouter(prefix="/jobs/{job_id}/upload", tags=["uploads"])


@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    job_id: str,
    body: UploadInitRequest,
    session: AsyncSession = Depends(get_session),
    upload_service: UploadService = Depends(get_upload_service),
):
    """Initialize chunked upload for a job."""
    # Verify job exists and is in correct state
    result = await session.execute(
        select(TranscriptionJob).where(TranscriptionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.QUEUED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is in '{job.status.value}' state, expected 'queued'",
        )

    try:
        await upload_service.init_upload(
            job_id, body.total_chunks, body.file_size
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Update job file_size
    job.file_size = body.file_size
    await session.commit()

    await LogService.info(
        session,
        job_id,
        f"Upload initialized: {body.total_chunks} chunks, "
        f"{body.file_size} bytes",
        "upload",
    )

    return UploadInitResponse(
        job_id=job_id,
        total_chunks=body.total_chunks,
        file_size=body.file_size,
        message="Upload initialized",
    )


@router.post("/chunks/{chunk_index}")
@limiter.limit(CHUNKS_RATE_LIMIT)
async def upload_chunk(
    request: Request,
    job_id: str,
    chunk_index: int,
    file: UploadFile = File(...),
    upload_service: UploadService = Depends(get_upload_service),
):
    """Upload a single chunk."""
    try:
        await upload_service.save_chunk(job_id, chunk_index, file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save chunk: {e}"
        )

    return {"message": f"Chunk {chunk_index} received", "job_id": job_id}


@router.get("/status", response_model=UploadStatusResponse)
async def upload_status(
    job_id: str,
    upload_service: UploadService = Depends(get_upload_service),
):
    """Get upload progress (for resumable uploads)."""
    status = await upload_service.get_upload_status(job_id)
    return UploadStatusResponse(**status)


@router.post("/complete", response_model=UploadCompleteResponse)
async def complete_upload(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    upload_service: UploadService = Depends(get_upload_service),
    redis=Depends(get_redis),
):
    """
    Finalize upload: combine chunks and enqueue transcription job.
    Falls back to inline background processing when arq/Redis is unavailable.
    """
    # Verify job
    result = await session.execute(
        select(TranscriptionJob).where(TranscriptionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Combine chunks
    try:
        combined_path = await upload_service.combine_chunks(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate duration
    try:
        from app.utils.audio_utils import get_audio_duration
        from app.config import settings

        duration = await get_audio_duration(combined_path)
        if duration > settings.MAX_DURATION_SECONDS:
            await upload_service.cleanup_job(job_id)
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Audio duration {duration:.0f}s exceeds "
                    f"maximum {settings.MAX_DURATION_SECONDS}s"
                ),
            )
        job.duration_seconds = int(duration)
    except HTTPException:
        raise
    except Exception:
        # If duration check fails, proceed anyway
        pass

    await session.commit()

    # Enqueue transcription — try arq if explicitly enabled, else run inline
    enqueued = False
    use_arq = getattr(settings, "USE_ARQ_WORKER", False)

    if use_arq and redis is not None:
        try:
            from arq import ArqRedis
            arq_redis = ArqRedis(pool_or_conn=redis.connection_pool)
            await arq_redis.enqueue_job("transcribe_batch", job_id)
            enqueued = True
            logger.info(f"Job {job_id} enqueued to arq worker")
        except Exception as exc:
            logger.warning(f"arq enqueue failed for {job_id}: {exc}")

    if not enqueued:
        # Run transcription directly as an async task on the event loop
        from app.queue.tasks import run_transcription_inline

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(
                run_transcription_inline(job_id),
                name=f"transcribe-{job_id}",
            )

            # Log any unhandled exception from the background task
            def _task_done_cb(t):
                if t.cancelled():
                    logger.warning("Transcription task for %s was cancelled", job_id)
                elif t.exception():
                    logger.error(
                        "Transcription task for %s failed: %s",
                        job_id,
                        t.exception(),
                        exc_info=t.exception(),
                    )

            task.add_done_callback(_task_done_cb)
            logger.info(f"Job {job_id} scheduled for inline background transcription")
        except Exception as exc:
            logger.error(f"Failed to schedule background task for {job_id}: {exc}")

    await LogService.info(
        session, job_id, "Upload complete, job enqueued", "upload"
    )

    return UploadCompleteResponse(
        job_id=job_id,
        status="queued",
        message="Upload complete, transcription queued",
    )
