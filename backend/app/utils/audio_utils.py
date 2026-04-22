import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("icepot")


# ── ffmpeg discovery ──────────────────────────────────────────────
def _find_ffmpeg() -> Optional[str]:
    """Return the path to ffmpeg, or None."""
    from app.config import settings

    # Explicit setting
    if settings.FFMPEG_BINARY and os.path.isfile(settings.FFMPEG_BINARY):
        return settings.FFMPEG_BINARY

    # On PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # Common Windows locations
    for p in [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]:
        if os.path.isfile(p):
            return p
    return None


def _find_ffprobe() -> Optional[str]:
    ffmpeg = _find_ffmpeg()
    if ffmpeg:
        ffprobe = ffmpeg.replace("ffmpeg", "ffprobe")
        if os.path.isfile(ffprobe):
            return ffprobe
    return shutil.which("ffprobe")


# ── duration ──────────────────────────────────────────────────────
async def get_audio_duration(file_path: str) -> float:
    """
    Get audio duration in seconds.
    Uses ffprobe when available, then pydub, then file-size estimate.
    """
    # Strategy 1: ffprobe (most reliable)
    ffprobe = _find_ffprobe()
    if ffprobe:
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                [
                    ffprobe, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    file_path,
                ],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return float(proc.stdout.strip())
        except Exception as e:
            logger.warning(f"ffprobe duration failed: {e}")

    # Strategy 2: pydub
    try:
        from pydub import AudioSegment
        audio = await asyncio.to_thread(AudioSegment.from_file, file_path)
        return len(audio) / 1000.0
    except Exception as e:
        logger.warning(f"pydub duration check failed: {e}")

    # Strategy 3: rough file-size estimate
    file_size = os.path.getsize(file_path)
    ext = Path(file_path).suffix.lower()
    if ext == ".wav":
        return max((file_size - 44) / 32000.0, 0)
    # ~128 kbps MP3 → 16 000 bytes/sec
    return max(file_size / 16000.0, 0)


# ── conversion ────────────────────────────────────────────────────
async def convert_to_wav(input_path: str, output_path: str) -> str:
    """
    Convert any audio file to WAV (16 kHz, mono, 16-bit PCM).
    Returns *output_path* on success, or *input_path* if ffmpeg is absent.
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        logger.warning("ffmpeg not found — skipping conversion")
        return input_path

    proc = await asyncio.to_thread(
        subprocess.run,
        [
            ffmpeg, "-y", "-i", input_path,
            "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
            output_path,
        ],
        capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {proc.stderr[:500]}")

    logger.info(f"Converted {input_path} → {output_path}")
    return output_path


# ── splitting ─────────────────────────────────────────────────────
async def split_audio(
    input_path: str,
    output_dir: str,
    chunk_seconds: int = 25,
) -> List[str]:
    """
    Split *input_path* into WAV chunks of *chunk_seconds* each.
    Each chunk is 16 kHz / mono / s16 so that Sarvam accepts it directly.
    Returns a sorted list of chunk file paths.
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        logger.warning("ffmpeg not found — returning file as single chunk")
        return [input_path]

    duration = await get_audio_duration(input_path)
    if duration <= chunk_seconds:
        # Small enough — just convert in-place
        out = os.path.join(output_dir, "chunk_0000.wav")
        os.makedirs(output_dir, exist_ok=True)
        await convert_to_wav(input_path, out)
        return [out]

    num_chunks = int(duration // chunk_seconds) + (
        1 if duration % chunk_seconds > 1 else 0
    )
    logger.info(
        f"Splitting {Path(input_path).name} ({duration:.0f}s) "
        f"into ≤{num_chunks} × {chunk_seconds}s chunks"
    )

    os.makedirs(output_dir, exist_ok=True)
    chunk_paths: List[str] = []

    for i in range(num_chunks):
        start = i * chunk_seconds
        out = os.path.join(output_dir, f"chunk_{i:04d}.wav")
        proc = await asyncio.to_thread(
            subprocess.run,
            [
                ffmpeg, "-y",
                "-i", input_path,
                "-ss", str(start),
                "-t", str(chunk_seconds),
                "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
                out,
            ],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 44:
            chunk_paths.append(out)
        else:
            logger.warning(f"Chunk {i} failed: {proc.stderr[:200]}")

    if not chunk_paths:
        raise RuntimeError("ffmpeg produced no audio chunks")

    logger.info(f"Created {len(chunk_paths)} chunks in {output_dir}")
    return chunk_paths


# ── validation ────────────────────────────────────────────────────
async def validate_audio_file(file_path: str) -> dict:
    """
    Basic validation of an audio file.
    Returns dict with 'valid', 'duration', 'error' keys.
    """
    if not os.path.exists(file_path):
        return {"valid": False, "duration": 0, "error": "File not found"}

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return {"valid": False, "duration": 0, "error": "File is empty"}

    try:
        duration = await get_audio_duration(file_path)
        return {"valid": True, "duration": duration, "error": None}
    except Exception as e:
        return {"valid": False, "duration": 0, "error": str(e)}
