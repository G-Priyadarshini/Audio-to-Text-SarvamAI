import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_session
from app.models.transcript import Transcript
from app.schemas.transcript import TranscriptResponse, TranscriptUpdate
from app.schemas.download import DownloadFormat
from app.services.formatter_service import FormatterService
from app.services.log_service import LogService

router = APIRouter(prefix="/jobs/{job_id}/transcript", tags=["transcripts"])


@router.get("", response_model=TranscriptResponse)
async def get_transcript(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get the transcript for a job."""
    result = await session.execute(
        select(Transcript).where(Transcript.job_id == job_id)
    )
    transcript = result.scalar_one_or_none()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript


@router.put("", response_model=TranscriptResponse)
async def update_transcript(
    job_id: str,
    body: TranscriptUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update (edit) the transcript."""
    result = await session.execute(
        select(Transcript).where(Transcript.job_id == job_id)
    )
    transcript = result.scalar_one_or_none()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    transcript.full_text = body.full_text
    transcript.edited = True
    await session.commit()
    await session.refresh(transcript)

    await LogService.info(
        session, job_id, "Transcript edited by user", "edit"
    )

    return transcript


@router.get("/download")
async def download_transcript(
    job_id: str,
    format: DownloadFormat = Query(default=DownloadFormat.TXT),
    session: AsyncSession = Depends(get_session),
):
    """Download transcript in specified format."""
    result = await session.execute(
        select(Transcript).where(Transcript.job_id == job_id)
    )
    transcript = result.scalar_one_or_none()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    formatter = FormatterService()

    if format == DownloadFormat.TXT:
        content = formatter.to_txt(
            transcript.full_text, transcript.diarized_json
        )
        media_type = "text/plain"
        ext = "txt"
    elif format == DownloadFormat.SRT:
        content = formatter.to_srt(
            transcript.segments_json,
            transcript.diarized_json,
            transcript.full_text,
        )
        media_type = "application/x-subrip"
        ext = "srt"
    elif format == DownloadFormat.VTT:
        content = formatter.to_vtt(
            transcript.segments_json,
            transcript.diarized_json,
            transcript.full_text,
        )
        media_type = "text/vtt"
        ext = "vtt"
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

    filename = f"transcript_{job_id[:8]}.{ext}"

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
