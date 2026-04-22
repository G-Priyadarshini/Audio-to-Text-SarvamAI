import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from app.config import settings
from app.database import async_session
from app.models.transcription_job import TranscriptionJob, JobStatus
from app.models.transcript import Transcript
from app.services.sarvam_service import SarvamClient
from app.services.log_service import LogService
from app.services.formatter_service import FormatterService
from app.utils.audio_utils import get_audio_duration, split_audio
from sqlalchemy import select

logger = logging.getLogger("icepot")


async def complete_sarvam_download(session, sarvam, job, final_status):
    """
    Shared helper: download Sarvam result and store transcript.
    Used by both the in-task flow and the cron fallback.
    """
    job.status = JobStatus.DOWNLOADING_RESULT
    await session.commit()

    output_files = sarvam.extract_output_filenames(final_status)
    if not output_files:
        raise RuntimeError("No output files in completed Sarvam job")

    download_response = await sarvam.request_download_urls(
        job.sarvam_job_id, output_files
    )

    full_text_parts = []
    all_segments = []
    all_diarization = []

    for fname in output_files:
        file_info = download_response.get("download_urls", {}).get(fname)
        if not file_info:
            logger.warning(f"No download URL for output file {fname}")
            continue

        file_url = file_info["file_url"]
        result_json = await sarvam.download_sarvam_result(file_url)

        text = result_json.get("text", "")
        segments = result_json.get("timestamps", [])
        diarization = result_json.get("diarization", [])
        full_text_parts.append(text)
        all_segments.extend(segments)
        all_diarization.extend(diarization)

    full_text = " ".join(full_text_parts).strip()

    # Store transcript
    transcript = Transcript(
        job_id=job.id,
        full_text=full_text,
        segments_json=all_segments if all_segments else None,
        diarized_json=all_diarization if all_diarization else None,
    )
    session.add(transcript)

    # Update job
    job.sarvam_state = "Completed"
    job.status = JobStatus.COMPLETED
    job.updated_at = datetime.utcnow()
    await session.commit()

    return full_text


async def _do_sarvam_transcription(job_id: str):
    """
    Core transcription logic — called by both the arq task and the inline fallback.

    Uses the **direct** Sarvam Speech-to-Text API (POST /speech-to-text-translate).
    The API accepts at most ~30 s of audio per request, so longer files are split
    into 25-second WAV chunks via ffmpeg and each chunk is transcribed separately.

    Flow:
      1. Locate the combined audio file
      2. Split into ≤25 s WAV chunks (ffmpeg)
      3. POST each chunk to Sarvam direct API
      4. Concatenate transcripts and store in DB
    """
    chunks_dir: str | None = None          # for cleanup

    async with async_session() as session:
        # Fetch job
        result = await session.execute(
            select(TranscriptionJob).where(TranscriptionJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # ── Locate the audio file ──
        # The uploader writes  <TEMP_DIR>/<job_id>_combined.wav  but the
        # original may have any extension (mp3, webm, …).  Also check the
        # job-specific sub-directory for any audio files.
        combined_path: str | None = None

        # Check the standard combined path
        for ext in (".wav", ".mp3", ".webm", ".ogg", ".m4a", ".flac", ""):
            candidate = os.path.join(settings.TEMP_DIR, f"{job_id}_combined{ext}")
            if os.path.isfile(candidate) and os.path.getsize(candidate) > 0:
                combined_path = candidate
                break

        # Fall back to first audio file in the job sub-directory
        if not combined_path:
            job_dir = os.path.join(settings.TEMP_DIR, job_id)
            if os.path.isdir(job_dir):
                for fname in sorted(os.listdir(job_dir)):
                    if fname.startswith("_"):
                        continue
                    fpath = os.path.join(job_dir, fname)
                    if os.path.isfile(fpath) and os.path.getsize(fpath) > 0:
                        combined_path = fpath
                        break

        if not combined_path:
            job.status = JobStatus.FAILED
            job.error_message = "Combined audio file not found"
            await session.commit()
            await LogService.error(
                session, job_id, "Audio file not found", "transcribe"
            )
            return

        file_path = Path(combined_path)
        file_size = file_path.stat().st_size

        try:
            sarvam = SarvamClient()

            # ── Mark as processing ──
            job.status = JobStatus.UPLOADING_TO_SARVAM
            await session.commit()

            duration = await get_audio_duration(combined_path)
            logger.info(
                f"Job {job_id}: {file_path.name}, "
                f"{file_size} bytes, ~{duration:.0f}s"
            )
            await LogService.info(
                session, job_id,
                f"Audio: {file_path.name} ({file_size} bytes, ~{duration:.0f}s)",
                "transcribe",
            )

            chunk_secs = settings.SARVAM_MAX_CHUNK_SECONDS  # 25 s default
            language = job.language or "en-IN"

            if duration <= chunk_secs:
                # ── Small file → single direct call ──
                await LogService.info(
                    session, job_id,
                    "Sending to Sarvam direct API (single request)...",
                    "transcribe",
                )
                stt_result = await sarvam.transcribe_direct(
                    file_path, language_code=language,
                )
            else:
                # ── Large file → split + transcribe each chunk ──
                chunks_dir = os.path.join(
                    settings.TEMP_DIR, f"{job_id}_sarvam_chunks"
                )
                await LogService.info(
                    session, job_id,
                    f"Splitting audio into ~{chunk_secs}s chunks...",
                    "transcribe",
                )
                chunk_paths = await split_audio(
                    combined_path, chunks_dir, chunk_secs
                )
                await LogService.info(
                    session, job_id,
                    f"Created {len(chunk_paths)} chunks — transcribing...",
                    "transcribe",
                )

                job.sarvam_state = "Processing"
                await session.commit()

                stt_result = await sarvam.transcribe_chunks(
                    chunk_paths, language_code=language,
                )

            # ── Extract result ──
            transcript_text = (stt_result.get("transcript") or "").strip()
            diarized = stt_result.get("diarized_transcript")
            detected_lang = stt_result.get("language_code")

            await LogService.info(
                session, job_id,
                f"Sarvam returned {len(transcript_text)} chars "
                f"(lang={detected_lang})",
                "transcribe",
            )

            # ── Format with ICEPOT analysis ──
            formatted_text = FormatterService.to_txt(
                transcript_text if transcript_text else "[No speech detected]",
                diarized,
                filename=file_path.name,
                duration_seconds=duration,
                language=language,
                file_format=file_path.suffix.lstrip("."),
                file_size=str(file_size),
            )

            # ── Store transcript ──
            job.status = JobStatus.DOWNLOADING_RESULT
            await session.commit()

            transcript = Transcript(
                job_id=job.id,
                full_text=formatted_text,
                segments_json=None,
                diarized_json=diarized,
            )
            session.add(transcript)

            job.sarvam_state = "Completed"
            job.status = JobStatus.COMPLETED
            job.duration_seconds = int(duration) if duration else None
            job.updated_at = datetime.utcnow()
            await session.commit()

            await LogService.info(
                session, job_id,
                f"Transcription complete: {len(transcript_text)} chars",
                "transcribe",
            )

        except Exception as e:
            logger.exception(f"Job {job_id} transcription error: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)[:500]
            job.retry_count = (job.retry_count or 0) + 1
            await session.commit()
            await LogService.error(
                session, job_id, f"Transcription error: {e}", "transcribe"
            )

        finally:
            # Clean up audio files
            if combined_path and os.path.exists(combined_path):
                os.remove(combined_path)
                logger.info(f"Cleaned up {combined_path}")
            if chunks_dir and os.path.isdir(chunks_dir):
                shutil.rmtree(chunks_dir, ignore_errors=True)
                logger.info(f"Cleaned up chunks dir {chunks_dir}")


async def transcribe_batch(ctx: dict, job_id: str):
    """arq task: Transcribe audio via Sarvam Job-based API."""
    await _do_sarvam_transcription(job_id)


async def run_transcription_inline(job_id: str):
    """
    Inline fallback — same logic as the arq task but callable directly
    from a FastAPI BackgroundTask when arq/Redis is not available.
    """
    logger.info(f"Running inline transcription for job {job_id}")
    try:
        await _do_sarvam_transcription(job_id)
    except Exception as e:
        logger.exception(f"Inline transcription failed for {job_id}: {e}")
