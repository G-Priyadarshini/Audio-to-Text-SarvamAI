from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_session
from app.models.transcription_job import TranscriptionJob, JobStatus, JobMode
from app.schemas.job import (
    JobCreate,
    JobResponse,
    JobListResponse,
    JobStatusResponse,
)
from app.middleware.rate_limit import limiter, JOBS_RATE_LIMIT
from app.services.log_service import LogService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse)
@limiter.limit(JOBS_RATE_LIMIT)
async def create_job(
    request: Request,
    body: JobCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new transcription job."""
    job = TranscriptionJob(
        language=body.language,
        mode=JobMode(body.mode.value),
        status=JobStatus.QUEUED,
        source_ip=request.client.host if request.client else None,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    await LogService.info(
        session,
        job.id,
        f"Job created: language={body.language}, mode={body.mode}",
        "create",
    )

    return job


@router.get("", response_model=JobListResponse)
async def list_jobs(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List all transcription jobs, paginated."""
    offset = (page - 1) * limit

    # Count total
    count_query = select(func.count()).select_from(TranscriptionJob)
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Fetch page
    query = (
        select(TranscriptionJob)
        .order_by(desc(TranscriptionJob.created_at))
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(
        jobs=[JobResponse.model_validate(j) for j in jobs],
        total=total,
        page=page,
        limit=limit,
        has_next=(offset + limit) < total,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get job details by ID."""
    result = await session.execute(
        select(TranscriptionJob).where(TranscriptionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get job status (lightweight)."""
    result = await session.execute(
        select(TranscriptionJob).where(TranscriptionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        error_message=job.error_message,
    )


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Delete a job and associated data."""
    result = await session.execute(
        select(TranscriptionJob).where(TranscriptionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await session.delete(job)
    await session.commit()

    return {"message": "Job deleted", "job_id": job_id}
