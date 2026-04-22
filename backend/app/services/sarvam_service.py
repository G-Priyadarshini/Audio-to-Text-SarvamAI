import httpx
import json
import asyncio
import logging
import re
from pathlib import Path
from typing import AsyncIterator, Optional, Dict, Any, Callable, Awaitable
from app.config import settings

logger = logging.getLogger("icepot")

SARVAM_BASE_URL = "https://api.sarvam.ai"
SARVAM_WS_ENDPOINT = "wss://api.sarvam.ai/speech-to-text/ws"


class SarvamAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Sarvam API Error {status_code}: {detail}")


class SarvamRateLimitError(SarvamAPIError):
    pass


class SarvamClient:
    """Client for Sarvam AI Speech-to-Text — Job-based API + WebSocket streaming."""

    def __init__(self):
        self.api_key = settings.SARVAM_API_KEY
        self.job_api_base = settings.SARVAM_JOB_API_BASE
        self.blob_base_url = settings.SARVAM_BLOB_BASE_URL
        self.headers = {
            "api-subscription-key": self.api_key,
        }
        self.json_headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }

    # ──────────────────────────────────────────────
    # Direct API: Single-request transcription
    # ──────────────────────────────────────────────
    async def transcribe_direct(
        self,
        file_path: Path,
        language_code: str = "en-IN",
        model: str | None = None,
    ) -> dict:
        """
        POST /speech-to-text  or  /speech-to-text-translate  (multipart form)

        Uses /speech-to-text for non-English languages (returns transcript
        in the original language) and /speech-to-text-translate for English
        (which translates any language → English).

        Simple one-shot transcription — no blob upload, no polling.
        Works for files up to ~50 MB.  Returns immediately with transcript.

        Returns: {
          "request_id": "...",
          "transcript": "Hello world",
          "language_code": "en-IN",
          "diarized_transcript": [...] | null,
          "language_probability": 0.98
        }
        """
        file_path = Path(file_path)
        content_type = self._guess_content_type(file_path)
        model = model or settings.SARVAM_MODEL

        # Use /speech-to-text (no translation) for non-English languages
        # so the transcript stays in the selected language (Tamil, Hindi, etc.)
        if language_code.startswith("en"):
            endpoint = f"{SARVAM_BASE_URL}/speech-to-text-translate"
        else:
            endpoint = f"{SARVAM_BASE_URL}/speech-to-text"

        logger.info(
            f"Direct transcribe: {file_path.name} "
            f"({file_path.stat().st_size} bytes, model={model}, "
            f"lang={language_code}, endpoint={endpoint})"
        )

        async with httpx.AsyncClient(timeout=300) as client:
            with open(file_path, "rb") as f:
                response = await client.post(
                    endpoint,
                    headers={"api-subscription-key": self.api_key},
                    files={"file": (file_path.name, f, content_type)},
                    data={
                        "model": model,
                        "language_code": language_code,
                    },
                )

            if response.status_code == 429:
                raise SarvamRateLimitError(429, "Rate limit exceeded")
            if response.status_code not in (200, 201):
                raise SarvamAPIError(response.status_code, response.text)

            result = response.json()
            logger.info(
                f"Direct transcribe OK – "
                f"{len(result.get('transcript', ''))} chars, "
                f"lang={result.get('language_code')}"
            )
            return result

    # ──────────────────────────────────────────────
    # Direct API: Transcribe multiple chunks
    # ──────────────────────────────────────────────
    async def transcribe_chunks(
        self,
        chunk_paths: list[str | Path],
        language_code: str = "en-IN",
        model: str | None = None,
    ) -> dict:
        """
        Transcribe a list of audio-chunk files sequentially via the
        direct API, then concatenate the results.

        Returns a dict shaped like a single transcribe_direct response:
          {"transcript": "...", "language_code": "...", ...}
        """
        all_text: list[str] = []
        total = len(chunk_paths)

        for idx, path in enumerate(chunk_paths):
            logger.info(f"Transcribing chunk {idx + 1}/{total}: {Path(path).name}")
            try:
                result = await self.transcribe_direct(
                    Path(path),
                    language_code=language_code,
                    model=model,
                )
                text = (result.get("transcript") or "").strip()
                if text:
                    all_text.append(text)
                    logger.info(
                        f"  chunk {idx + 1}: {len(text)} chars – "
                        f"{text[:80]}{'…' if len(text) > 80 else ''}"
                    )
                else:
                    logger.info(f"  chunk {idx + 1}: (no speech detected)")
            except SarvamRateLimitError:
                # Back off and retry once
                logger.warning(f"  chunk {idx + 1}: rate-limited, retrying in 5 s")
                await asyncio.sleep(5)
                result = await self.transcribe_direct(
                    Path(path),
                    language_code=language_code,
                    model=model,
                )
                text = (result.get("transcript") or "").strip()
                if text:
                    all_text.append(text)
            except Exception as exc:
                logger.error(f"  chunk {idx + 1} failed: {exc}")
                all_text.append(f"[Error in segment {idx + 1}]")

        full_text = " ".join(all_text)
        logger.info(
            f"All {total} chunks done – total transcript: {len(full_text)} chars"
        )
        return {
            "transcript": full_text,
            "language_code": language_code,
            "diarized_transcript": None,
        }

    # ──────────────────────────────────────────────
    # Job API Step 1: Create a transcription job
    # ──────────────────────────────────────────────
    async def create_sarvam_job(self, language_code: str = "en-IN") -> dict:
        """
        POST /speech-to-text/job/v1
        Returns: {"job_id": "...", "job_state": "Accepted", ...}
        """
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self.job_api_base,
                headers=self.json_headers,
                json={
                    "job_parameters": {
                        "language_code": language_code,
                    }
                },
            )
            if response.status_code == 429:
                raise SarvamRateLimitError(429, "Rate limit exceeded")
            if response.status_code not in (200, 201, 202):
                raise SarvamAPIError(response.status_code, response.text)
            result = response.json()
            logger.info(f"Sarvam job created: {result.get('job_id')}")
            return result

    # ──────────────────────────────────────────────
    # Job API Step 2: Build upload URL from job_id
    # ──────────────────────────────────────────────
    def build_upload_url(self, job_id: str, filename: str) -> str:
        """
        Derive the Azure Blob upload URL from job_id.
        job_id format: "20260303_2bee913d-1af2-4da7-b6e1-8667d36809c2"
        URL pattern:   .../jobs/{DATE}/SPEECH_TO_TEXT_BULK/{UUID}/inputs/{filename}
        """
        match = re.match(r"^(\d{8})_(.+)$", job_id)
        if not match:
            raise ValueError(f"Invalid Sarvam job_id format: {job_id}")

        date_prefix = match.group(1)
        uuid_part = match.group(2)

        return (
            f"{self.blob_base_url}/jobs/{date_prefix}/"
            f"SPEECH_TO_TEXT_BULK/{uuid_part}/inputs/{filename}"
        )

    # ──────────────────────────────────────────────
    # Job API Step 3: Upload audio file to Azure Blob
    # ──────────────────────────────────────────────
    async def upload_to_sarvam(self, upload_url: str, file_path: Path) -> None:
        """
        PUT the audio file to the Azure Blob upload URL.
        No API key header — access controlled by the URL itself.
        """
        file_path = Path(file_path)
        file_size = file_path.stat().st_size
        content_type = self._guess_content_type(file_path)

        logger.info(
            f"Uploading to Sarvam: {file_path.name} "
            f"({file_size} bytes, {content_type})"
        )

        async with httpx.AsyncClient(timeout=600) as client:
            with open(file_path, "rb") as f:
                response = await client.put(
                    upload_url,
                    content=f.read(),
                    headers={
                        "x-ms-blob-type": "BlockBlob",
                        "Content-Type": content_type,
                        "Content-Length": str(file_size),
                    },
                )
                if response.status_code not in (200, 201):
                    raise SarvamAPIError(
                        response.status_code,
                        f"Upload failed: {response.text}",
                    )
        logger.info("Upload to Sarvam complete")

    # ──────────────────────────────────────────────
    # Job API Step 4: Start the job
    # ──────────────────────────────────────────────
    async def start_sarvam_job(self, job_id: str) -> dict:
        """
        POST /speech-to-text/job/v1/{job_id}/start
        """
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.job_api_base}/{job_id}/start",
                headers=self.json_headers,
            )
            if response.status_code not in (200, 202):
                raise SarvamAPIError(response.status_code, response.text)
            result = response.json()
            logger.info(f"Sarvam job started: {job_id}")
            return result

    # ──────────────────────────────────────────────
    # Job API Step 5: Poll job status
    # ──────────────────────────────────────────────
    async def poll_sarvam_status(self, job_id: str) -> dict:
        """
        GET /speech-to-text/job/v1/{job_id}/status
        Returns: {"job_state": "Completed", "job_details": [...], ...}
        """
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.job_api_base}/{job_id}/status",
                headers=self.json_headers,
            )
            if response.status_code != 200:
                raise SarvamAPIError(response.status_code, response.text)
            return response.json()

    # ──────────────────────────────────────────────
    # Job API Step 6: Request download URLs
    # ──────────────────────────────────────────────
    async def request_download_urls(
        self, job_id: str, files: list[str]
    ) -> dict:
        """
        POST /speech-to-text/job/v1/download-files
        Returns: {"download_urls": {"0.json": {"file_url": "..."}}}
        """
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.job_api_base}/download-files",
                headers=self.json_headers,
                json={
                    "job_id": job_id,
                    "files": files,
                },
            )
            if response.status_code != 200:
                raise SarvamAPIError(response.status_code, response.text)
            return response.json()

    # ──────────────────────────────────────────────
    # Job API Step 7: Download the output JSON
    # ──────────────────────────────────────────────
    async def download_sarvam_result(self, file_url: str) -> dict:
        """
        GET the signed Azure Blob URL — no auth headers needed.
        Returns: parsed JSON transcript.
        """
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(file_url)
            if response.status_code != 200:
                raise SarvamAPIError(
                    response.status_code,
                    f"Download failed: {response.text[:500]}",
                )
            return response.json()

    # ──────────────────────────────────────────────
    # Convenience: Full poll loop with backoff
    # ──────────────────────────────────────────────
    async def wait_for_completion(
        self,
        job_id: str,
        *,
        initial_interval: int = 5,
        max_backoff: int = 60,
        timeout: int = 7200,
        on_poll: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> dict:
        """
        Poll until job_state is 'Completed' or 'Failed', or timeout.
        Uses exponential backoff: 5s → 10s → 20s → 40s → 60s (cap).

        Args:
            on_poll: optional async callback invoked after each poll

        Returns:
            Final status dict

        Raises:
            TimeoutError: if timeout exceeded
            RuntimeError: if job failed
        """
        interval = initial_interval
        elapsed = 0

        while elapsed < timeout:
            status = await self.poll_sarvam_status(job_id)
            state = status.get("job_state", "Unknown")

            if on_poll:
                await on_poll(status)

            if state == "Completed":
                logger.info(f"Sarvam job {job_id} completed after {elapsed}s")
                return status
            elif state == "Failed":
                raise RuntimeError(
                    f"Sarvam job {job_id} failed: {status}"
                )

            await asyncio.sleep(interval)
            elapsed += interval
            interval = min(interval * 2, max_backoff)

        raise TimeoutError(
            f"Sarvam job {job_id} did not complete within {timeout}s"
        )

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────
    @staticmethod
    def _guess_content_type(file_path: Path) -> str:
        suffix = Path(file_path).suffix.lower()
        return {
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".webm": "audio/webm",
            ".m4a": "audio/mp4",
            ".flac": "audio/flac",
        }.get(suffix, "application/octet-stream")

    @staticmethod
    def extract_output_filenames(status: dict) -> list[str]:
        """Extract output file names from a completed status response."""
        filenames = []
        for detail in status.get("job_details", []):
            for output in detail.get("outputs", []):
                fname = output.get("file_name")
                if fname:
                    filenames.append(fname)
        return filenames

    # ──────────────────────────────────────────────
    # WebSocket streaming (unchanged — for hybrid mode)
    # ──────────────────────────────────────────────
    async def stream_transcribe(
        self,
        language: str,
    ) -> "SarvamStreamSession":
        """
        Open a WebSocket connection for real-time streaming transcription.
        Returns a session object to send chunks and receive partials.
        """
        return SarvamStreamSession(self.api_key, language)


class SarvamStreamSession:
    """Manages a WebSocket session for real-time streaming transcription."""

    def __init__(self, api_key: str, language: str):
        self.api_key = api_key
        self.language = language
        self.ws = None
        self._connected = False

    async def connect(self):
        """Open WebSocket connection."""
        import websockets

        url = (
            f"{SARVAM_WS_ENDPOINT}"
            f"?language_code={self.language}"
            f"&api_subscription_key={self.api_key}"
        )

        self.ws = await websockets.connect(
            url,
            additional_headers={
                "api-subscription-key": self.api_key,
            },
            ping_interval=30,
            ping_timeout=10,
        )
        self._connected = True
        logger.info(f"Sarvam WebSocket connected for language {self.language}")

    async def send_audio(self, audio_data: bytes):
        """Send audio chunk to Sarvam via WebSocket."""
        if not self._connected or not self.ws:
            raise RuntimeError("WebSocket not connected")
        await self.ws.send(audio_data)

    async def receive_partial(self) -> Optional[Dict[str, Any]]:
        """Receive a partial transcript from Sarvam. Returns None on close."""
        if not self._connected or not self.ws:
            return None
        try:
            message = await asyncio.wait_for(self.ws.recv(), timeout=30)
            return json.loads(message)
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"WebSocket receive error: {e}")
            return None

    async def close(self):
        """Close WebSocket connection."""
        if self.ws:
            await self.ws.close()
            self._connected = False
            logger.info("Sarvam WebSocket closed")

    @property
    def is_connected(self) -> bool:
        return self._connected
