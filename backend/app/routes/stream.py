import asyncio
import json
import logging
import os
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
)
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.database import get_session
from app.models.transcription_job import TranscriptionJob, JobStatus, JobMode
from app.models.transcript import Transcript
from app.services.stream_service import StreamService
from app.services.sarvam_service import SarvamClient, SarvamStreamSession
from app.services.log_service import LogService
from app.utils.dependencies import get_redis, get_stream_service
from redis.asyncio import Redis

logger = logging.getLogger("icepot")
router = APIRouter(prefix="/jobs/{job_id}/stream", tags=["streaming"])

# In-memory store for active WebSocket sessions
_active_sessions: dict[str, SarvamStreamSession] = {}
# In-memory store for buffered audio chunks (for hybrid mode)
_audio_buffers: dict[str, list[bytes]] = {}


@router.post("/audio")
async def receive_stream_audio(
    job_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    stream_service: StreamService = Depends(get_stream_service),
    redis: Redis = Depends(get_redis),
):
    """
    Receive an audio chunk during real-time streaming.
    Forwards to Sarvam WebSocket, publishes partial result.
    Also buffers audio for the final job-based transcript.
    """
    # Verify job is in streaming mode
    result = await session.execute(
        select(TranscriptionJob).where(TranscriptionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.mode != JobMode.REALTIME:
        raise HTTPException(
            status_code=400, detail="Job is not in realtime mode"
        )

    # Update status to streaming if queued
    if job.status == JobStatus.QUEUED:
        job.status = JobStatus.STREAMING
        await session.commit()

    audio_data = await file.read()

    # Buffer audio for hybrid mode (final job-based transcript)
    if job_id not in _audio_buffers:
        _audio_buffers[job_id] = []
    _audio_buffers[job_id].append(audio_data)

    # Get or create Sarvam WebSocket session
    if job_id not in _active_sessions:
        client = SarvamClient()
        ws_session = await client.stream_transcribe(job.language)
        await ws_session.connect()
        _active_sessions[job_id] = ws_session

        # Start background task to receive partials
        asyncio.create_task(
            _receive_partials(job_id, ws_session, stream_service, session)
        )

    ws_session = _active_sessions[job_id]

    try:
        await ws_session.send_audio(audio_data)
    except Exception as e:
        logger.error(f"Failed to send audio to Sarvam WS for {job_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to forward audio"
        )

    return {"message": "Audio chunk received", "job_id": job_id}


@router.post("/end")
async def end_stream(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    stream_service: StreamService = Depends(get_stream_service),
    redis: Redis = Depends(get_redis),
):
    """
    Signal end of audio stream.
    Hybrid mode: closes WebSocket, saves buffered audio, enqueues
    job-based transcription for the final authoritative transcript.
    """
    # Close WebSocket session
    if job_id in _active_sessions:
        ws_session = _active_sessions.pop(job_id)
        await ws_session.close()

    # Compile interim transcript from stream history (for immediate display)
    history = await stream_service.get_history(job_id)
    full_text_parts = []
    for entry in history:
        if entry.get("type") == "partial":
            text = entry.get("transcript", "")
            if text:
                full_text_parts.append(text)

    interim_text = " ".join(full_text_parts)

    result = await session.execute(
        select(TranscriptionJob).where(TranscriptionJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        _audio_buffers.pop(job_id, None)
        raise HTTPException(status_code=404, detail="Job not found")

    # Save buffered audio to disk for job-based transcription
    audio_chunks = _audio_buffers.pop(job_id, [])
    combined_path = None

    if audio_chunks:
        combined_path = os.path.join(
            settings.TEMP_DIR, f"{job_id}_combined.wav"
        )
        os.makedirs(settings.TEMP_DIR, exist_ok=True)
        with open(combined_path, "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)

        logger.info(
            f"Saved {len(audio_chunks)} stream chunks to {combined_path}"
        )

    if combined_path and os.path.exists(combined_path):
        # Store interim transcript (will be replaced by job-based result)
        existing_transcript = await session.execute(
            select(Transcript).where(Transcript.job_id == job_id)
        )
        if not existing_transcript.scalar_one_or_none():
            transcript = Transcript(
                job_id=job_id,
                full_text=interim_text,
            )
            session.add(transcript)

        # Enqueue job-based transcription for authoritative result
        job.status = JobStatus.QUEUED
        await session.commit()

        from arq import ArqRedis
        arq_redis = ArqRedis(pool_or_conn=redis.connection_pool)
        await arq_redis.enqueue_job("transcribe_batch", job_id)

        await LogService.info(
            session, job_id,
            "Stream ended — job-based transcription enqueued for final result",
            "stream",
        )

        # Signal SSE listeners that job-based processing is starting
        await stream_service.publish_status(job_id, {
            "type": "sarvam_job_submitted",
            "job_id": job_id,
            "message": "Finalizing transcript via Sarvam...",
            "interim_text": interim_text,
        })
    else:
        # No audio buffered, just store what we have from WS
        existing_transcript = await session.execute(
            select(Transcript).where(Transcript.job_id == job_id)
        )
        if not existing_transcript.scalar_one_or_none():
            transcript = Transcript(
                job_id=job_id,
                full_text=interim_text,
            )
            session.add(transcript)
        job.status = JobStatus.COMPLETED
        await session.commit()

        await LogService.info(
            session, job_id, "Real-time streaming complete", "stream"
        )
        await stream_service.publish_complete(job_id)

    await stream_service.cleanup(job_id)

    return {
        "message": "Stream ended",
        "job_id": job_id,
        "status": job.status.value,
    }


@router.get("")
async def stream_sse(
    job_id: str,
    request: Request,
    stream_service: StreamService = Depends(get_stream_service),
):
    """SSE endpoint for real-time partial transcript updates."""

    async def event_generator():
        # First, send any history (for reconnection)
        history = await stream_service.get_history(job_id)
        for entry in history:
            yield {
                "event": entry.get("type", "partial"),
                "data": json.dumps(entry),
            }

        # Subscribe to live updates
        async for data in stream_service.subscribe(job_id):
            if await request.is_disconnected():
                break
            yield {
                "event": data.get("type", "partial"),
                "data": json.dumps(data),
            }

    return EventSourceResponse(event_generator())


async def _receive_partials(
    job_id: str,
    ws_session: SarvamStreamSession,
    stream_service: StreamService,
    session: AsyncSession,
):
    """Background task to receive partial transcripts from Sarvam WS."""
    try:
        while ws_session.is_connected:
            result = await ws_session.receive_partial()
            if result is None:
                break

            partial_data = {
                "type": "partial",
                "transcript": result.get("transcript", ""),
                "is_final": result.get("is_final", False),
            }
            await stream_service.publish_partial(job_id, partial_data)
    except Exception as e:
        logger.error(f"Error receiving partials for {job_id}: {e}")
        await stream_service.publish_error(job_id, str(e))
    finally:
        _active_sessions.pop(job_id, None)
