"""
Sarvam Job-based STT API — Direct endpoint wrappers.

Exposes the full Sarvam Job API lifecycle as backend HTTP endpoints:
  POST   /api/sarvam/jobs              → Create job
  PUT    /api/sarvam/jobs/{id}/upload   → Upload audio file
  POST   /api/sarvam/jobs/{id}/start    → Start job
  GET    /api/sarvam/jobs/{id}/status   → Poll status
  POST   /api/sarvam/jobs/download      → Get download URLs
  GET    /api/sarvam/jobs/{id}/transcript → Convenience: status + download + parse
"""

import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.services.sarvam_service import SarvamClient, SarvamAPIError

router = APIRouter(prefix="/sarvam", tags=["Sarvam Job API"])


# ──────────────────────────────────────────
# Request / Response Schemas
# ──────────────────────────────────────────

class CreateJobRequest(BaseModel):
    language_code: str = "en-IN"


class CreateJobResponse(BaseModel):
    job_id: str
    job_state: str
    upload_url: Optional[str] = None
    job_parameters: Optional[dict] = None


class StartJobResponse(BaseModel):
    message: str
    job_id: str


class JobStatusResponse(BaseModel):
    job_state: str
    total_files: Optional[int] = None
    successful_files_count: Optional[int] = None
    failed_files_count: Optional[int] = None
    job_details: Optional[list] = None


class DownloadRequest(BaseModel):
    job_id: str
    files: List[str]


class DownloadResponse(BaseModel):
    download_urls: dict


# ──────────────────────────────────────────
# Step 1: Create Job
# ──────────────────────────────────────────

@router.post("/jobs", response_model=CreateJobResponse)
async def create_sarvam_job(req: CreateJobRequest):
    """
    Create a new Sarvam transcription job.

    Returns the job_id, initial state, and a pre-built upload URL.
    """
    sarvam = SarvamClient()
    try:
        result = await sarvam.create_sarvam_job(req.language_code)
        job_id = result["job_id"]

        # Pre-build the upload URL for convenience
        upload_url = sarvam.build_upload_url(job_id, "audio.mp3")

        return CreateJobResponse(
            job_id=job_id,
            job_state=result.get("job_state", "Accepted"),
            upload_url=upload_url,
            job_parameters=result.get("job_parameters"),
        )
    except SarvamAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────
# Step 2: Upload Audio File
# ──────────────────────────────────────────

@router.put("/jobs/{job_id}/upload")
async def upload_audio(job_id: str, file: UploadFile = File(...)):
    """
    Upload an audio file to Sarvam's Azure Blob storage for the given job.

    The backend proxies the upload: client sends the file here, and this
    endpoint forwards it to Sarvam's pre-signed Azure Blob URL.
    """
    sarvam = SarvamClient()
    try:
        # Save uploaded file to a temp location
        suffix = Path(file.filename).suffix if file.filename else ".mp3"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        # Build upload URL and send to Azure Blob
        filename = file.filename or f"audio{suffix}"
        upload_url = sarvam.build_upload_url(job_id, filename)
        await sarvam.upload_to_sarvam(upload_url, tmp_path)

        # Cleanup temp file
        tmp_path.unlink(missing_ok=True)

        return {
            "message": "File uploaded successfully",
            "job_id": job_id,
            "filename": filename,
            "size_bytes": len(content),
            "upload_url": upload_url,
        }
    except SarvamAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────
# Step 3: Start Job
# ──────────────────────────────────────────

@router.post("/jobs/{job_id}/start", response_model=StartJobResponse)
async def start_sarvam_job(job_id: str):
    """
    Start a Sarvam transcription job.

    The job must be in 'Accepted' state (i.e., files uploaded but not yet started).
    """
    sarvam = SarvamClient()
    try:
        await sarvam.start_sarvam_job(job_id)
        return StartJobResponse(
            message="Job started successfully",
            job_id=job_id,
        )
    except SarvamAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ──────────────────────────────────────────
# Step 4: Check Job Status
# ──────────────────────────────────────────

@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_sarvam_job_status(job_id: str):
    """
    Poll the status of a Sarvam transcription job.

    States: Accepted → Running → Completed / Failed
    """
    sarvam = SarvamClient()
    try:
        result = await sarvam.poll_sarvam_status(job_id)
        return JobStatusResponse(
            job_state=result.get("job_state", "Unknown"),
            total_files=result.get("total_files"),
            successful_files_count=result.get("successful_files_count"),
            failed_files_count=result.get("failed_files_count"),
            job_details=result.get("job_details"),
        )
    except SarvamAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────
# Step 5: Request Download URLs
# ──────────────────────────────────────────

@router.post("/jobs/download", response_model=DownloadResponse)
async def request_download_urls(req: DownloadRequest):
    """
    Get signed download URLs for completed job output files.

    The URLs are time-limited. Call again if expired.
    """
    sarvam = SarvamClient()
    try:
        result = await sarvam.request_download_urls(req.job_id, req.files)
        return DownloadResponse(
            download_urls=result.get("download_urls", {}),
        )
    except SarvamAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────
# Step 6: Convenience — Get Final Transcript
# ──────────────────────────────────────────

@router.get("/jobs/{job_id}/transcript")
async def get_sarvam_transcript(job_id: str):
    """
    Convenience endpoint that combines Steps 4 + 5 + 6.

    Checks status → if Completed, requests download URLs →
    downloads output JSON → returns merged transcript.
    """
    sarvam = SarvamClient()
    try:
        # Check status first
        status = await sarvam.poll_sarvam_status(job_id)
        state = status.get("job_state", "Unknown")

        if state != "Completed":
            return {
                "job_id": job_id,
                "job_state": state,
                "transcript": None,
                "message": f"Job is not completed yet. Current state: {state}",
            }

        # Extract output filenames
        output_files = sarvam.extract_output_filenames(status)
        if not output_files:
            raise HTTPException(
                status_code=404, detail="No output files found in completed job"
            )

        # Get download URLs
        download_resp = await sarvam.request_download_urls(job_id, output_files)

        # Download and merge all transcripts
        full_text_parts = []
        all_segments = []

        for fname in output_files:
            file_info = download_resp.get("download_urls", {}).get(fname, {})
            file_url = file_info.get("file_url")
            if not file_url:
                continue

            result_json = await sarvam.download_sarvam_result(file_url)
            full_text_parts.append(result_json.get("text", ""))
            all_segments.extend(result_json.get("segments", []))

        return {
            "job_id": job_id,
            "job_state": "Completed",
            "transcript": " ".join(full_text_parts).strip(),
            "segments": all_segments,
            "output_files": output_files,
        }
    except HTTPException:
        raise
    except SarvamAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
