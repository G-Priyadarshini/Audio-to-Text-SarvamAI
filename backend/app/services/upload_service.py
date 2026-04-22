import os
import json
import shutil
import time
import aiofiles
from typing import List, Optional
from fastapi import UploadFile
from app.config import settings
import logging

logger = logging.getLogger("icepot")


class UploadService:
    """Chunked upload manager.

    Uses Redis for tracking when available; falls back to simple
    filesystem-based tracking so the app still works without Redis.
    """

    def __init__(self, redis=None):
        self.redis = redis

    # ── path helpers ──────────────────────────────────────────────
    def _get_upload_dir(self, job_id: str) -> str:
        return os.path.join(settings.TEMP_DIR, job_id)

    def _get_chunk_path(self, job_id: str, chunk_index: int) -> str:
        upload_dir = self._get_upload_dir(job_id)
        return os.path.join(upload_dir, f"chunk_{chunk_index:05d}")

    def _get_combined_path(self, job_id: str, ext: str = ".wav") -> str:
        return os.path.join(settings.TEMP_DIR, f"{job_id}_combined{ext}")

    def _get_meta_path(self, job_id: str) -> str:
        return os.path.join(self._get_upload_dir(job_id), "_meta.json")

    # ── init ──────────────────────────────────────────────────────
    async def init_upload(
        self, job_id: str, total_chunks: int, file_size: int
    ) -> None:
        """Initialize upload tracking and create temp directory."""
        if file_size > settings.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size {file_size} exceeds maximum "
                f"{settings.MAX_FILE_SIZE_BYTES} bytes"
            )

        upload_dir = self._get_upload_dir(job_id)
        os.makedirs(upload_dir, exist_ok=True)

        if self.redis is not None:
            key = f"upload:{job_id}"
            await self.redis.hset(key, "total_chunks", str(total_chunks))
            await self.redis.hset(key, "file_size", str(file_size))
            await self.redis.hset(key, "status", "uploading")
            await self.redis.expire(key, 7200)
        else:
            # Filesystem meta
            meta = {"total_chunks": total_chunks, "file_size": file_size, "status": "uploading"}
            async with aiofiles.open(self._get_meta_path(job_id), "w") as f:
                await f.write(json.dumps(meta))

        logger.info(
            f"Upload initialized for job {job_id}: "
            f"{total_chunks} chunks, {file_size} bytes"
        )

    # ── save chunk ────────────────────────────────────────────────
    async def save_chunk(
        self, job_id: str, chunk_index: int, file: UploadFile
    ) -> None:
        """Save a single upload chunk to disk."""
        chunk_path = self._get_chunk_path(job_id, chunk_index)
        # Ensure upload dir exists (in case init was skipped)
        os.makedirs(self._get_upload_dir(job_id), exist_ok=True)

        async with aiofiles.open(chunk_path, "wb") as f:
            content = await file.read()
            if len(content) > settings.MAX_CHUNK_SIZE_BYTES:
                raise ValueError(
                    f"Chunk size {len(content)} exceeds maximum "
                    f"{settings.MAX_CHUNK_SIZE_BYTES} bytes"
                )
            await f.write(content)

        if self.redis is not None:
            key = f"upload:{job_id}:chunks"
            await self.redis.sadd(key, str(chunk_index))
            await self.redis.expire(key, 7200)

    # ── received chunks ───────────────────────────────────────────
    async def get_received_chunks(self, job_id: str) -> List[int]:
        """Get list of received chunk indices."""
        if self.redis is not None:
            key = f"upload:{job_id}:chunks"
            members = await self.redis.smembers(key)
            return sorted([int(m) for m in members])

        # Filesystem fallback: scan directory
        upload_dir = self._get_upload_dir(job_id)
        received = []
        if os.path.isdir(upload_dir):
            for fname in os.listdir(upload_dir):
                if fname.startswith("chunk_"):
                    try:
                        received.append(int(fname.replace("chunk_", "")))
                    except ValueError:
                        pass
        return sorted(received)

    # ── status ────────────────────────────────────────────────────
    async def get_upload_status(self, job_id: str) -> dict:
        """Get full upload status."""
        received = await self.get_received_chunks(job_id)

        if self.redis is not None:
            meta_key = f"upload:{job_id}"
            meta = await self.redis.hgetall(meta_key)
            total_chunks = int(meta.get("total_chunks", 0))
        else:
            total_chunks = 0
            meta_path = self._get_meta_path(job_id)
            if os.path.exists(meta_path):
                async with aiofiles.open(meta_path, "r") as f:
                    meta = json.loads(await f.read())
                    total_chunks = meta.get("total_chunks", 0)

        return {
            "job_id": job_id,
            "total_chunks": total_chunks,
            "received_chunks": received,
            "is_complete": len(received) == total_chunks and total_chunks > 0,
        }

    # ── combine ───────────────────────────────────────────────────
    @staticmethod
    def _detect_ext(first_chunk_path: str) -> str:
        """Detect audio format from magic bytes of the first chunk."""
        try:
            with open(first_chunk_path, "rb") as f:
                header = f.read(12)
            if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
                return ".wav"
            if header[:3] == b"ID3" or header[:2] == b"\xff\xfb" or header[:2] == b"\xff\xf3" or header[:2] == b"\xff\xf2":
                return ".mp3"
            if header[:4] == b"OggS":
                return ".ogg"
            if header[:4] == b"fLaC":
                return ".flac"
            if header[4:8] == b"ftyp":
                return ".m4a"
            if header[:4] == b"\x1a\x45\xdf\xa3":
                return ".webm"
        except Exception:
            pass
        return ".wav"  # fallback

    async def combine_chunks(self, job_id: str) -> str:
        """Concatenate all chunks into a single file. Returns combined file path."""
        status = await self.get_upload_status(job_id)
        if not status["is_complete"]:
            missing = set(range(status["total_chunks"])) - set(
                status["received_chunks"]
            )
            raise ValueError(f"Missing chunks: {sorted(missing)}")

        upload_dir = self._get_upload_dir(job_id)

        # Detect the actual audio format from the first chunk
        first_chunk = self._get_chunk_path(job_id, 0)
        ext = self._detect_ext(first_chunk)
        combined_path = self._get_combined_path(job_id, ext)

        async with aiofiles.open(combined_path, "wb") as combined:
            for i in range(status["total_chunks"]):
                chunk_path = self._get_chunk_path(job_id, i)
                async with aiofiles.open(chunk_path, "rb") as chunk:
                    data = await chunk.read()
                    await combined.write(data)

        # Clean up chunk directory
        shutil.rmtree(upload_dir, ignore_errors=True)

        # Clean up Redis keys if available
        if self.redis is not None:
            await self.redis.delete(f"upload:{job_id}")
            await self.redis.delete(f"upload:{job_id}:chunks")

        logger.info(f"Chunks combined for job {job_id}: {combined_path}")
        return combined_path

    # ── cleanup ───────────────────────────────────────────────────
    async def cleanup_job(self, job_id: str) -> None:
        """Clean up all temp files and Redis keys for a job."""
        upload_dir = self._get_upload_dir(job_id)

        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir, ignore_errors=True)

        # Remove combined file with any extension
        for ext in (".wav", ".mp3", ".webm", ".ogg", ".m4a", ".flac"):
            combined_path = self._get_combined_path(job_id, ext)
            if os.path.exists(combined_path):
                os.remove(combined_path)

        if self.redis is not None:
            await self.redis.delete(f"upload:{job_id}")
            await self.redis.delete(f"upload:{job_id}:chunks")

    @staticmethod
    async def cleanup_abandoned_uploads(redis) -> int:
        """Clean up uploads older than 1 hour with no activity. Returns count."""
        cleaned = 0
        temp_dir = settings.TEMP_DIR

        if not os.path.exists(temp_dir):
            return 0

        for entry in os.listdir(temp_dir):
            entry_path = os.path.join(temp_dir, entry)
            if os.path.isdir(entry_path):
                mtime = os.path.getmtime(entry_path)
                if time.time() - mtime > 3600:
                    shutil.rmtree(entry_path, ignore_errors=True)
                    job_id = entry
                    if redis is not None:
                        await redis.delete(f"upload:{job_id}")
                        await redis.delete(f"upload:{job_id}:chunks")
                    cleaned += 1
                    logger.info(f"Cleaned abandoned upload: {job_id}")

        return cleaned
