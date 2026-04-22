"""Quick end-to-end test of the upload + transcription flow."""
import httpx
import asyncio
import struct
import math
import io

BASE = "http://localhost:8000/api"


def create_test_wav(duration=3, sample_rate=16000, frequency=440):
    """Generate a valid WAV file with a sine-wave tone."""
    num_samples = int(duration * sample_rate)
    samples = []
    for i in range(num_samples):
        value = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(struct.pack("<h", value))
    audio_data = b"".join(samples)

    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + len(audio_data)))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", len(audio_data)))
    buf.write(audio_data)
    buf.seek(0)
    return buf.read()


async def main():
    # Create a 10-second WAV (short enough to go direct, triggers no split)
    wav_data = create_test_wav(duration=10)
    file_size = len(wav_data)
    print(f"Test WAV: {file_size} bytes (10 sec sine wave)")

    async with httpx.AsyncClient(timeout=120) as c:
        # 1. Create job
        r = await c.post(f"{BASE}/jobs", json={"language": "en-IN", "mode": "batch"})
        assert r.status_code == 200, f"Create job failed: {r.status_code} {r.text}"
        job = r.json()
        job_id = job["id"]
        print(f"1. Job created: {job_id}, status={job['status']}")

        # 2. Init upload (1 chunk)
        r = await c.post(
            f"{BASE}/jobs/{job_id}/upload/init",
            json={"total_chunks": 1, "file_size": file_size},
        )
        assert r.status_code == 200, f"Init upload failed: {r.status_code} {r.text}"
        print(f"2. Init: {r.json()['message']}")

        # 3. Upload valid WAV as single chunk
        files = {"file": ("chunk_0.wav", wav_data, "audio/wav")}
        r = await c.post(f"{BASE}/jobs/{job_id}/upload/chunks/0", files=files)
        assert r.status_code == 200, f"Upload chunk failed: {r.status_code} {r.text}"
        print(f"3. Chunk uploaded: {r.json()['message']}")

        # 4. Complete upload
        r = await c.post(f"{BASE}/jobs/{job_id}/upload/complete")
        assert r.status_code == 200, f"Complete failed: {r.status_code} {r.text}"
        print(f"4. Complete: {r.json()['message']}")

        # 5. Poll status — wait for transcription
        for i in range(40):
            await asyncio.sleep(3)
            r = await c.get(f"{BASE}/jobs/{job_id}/status")
            status = r.json()
            st = status["status"]
            sarvam = status.get("sarvam_state", "")
            print(f"5.{i} Status: {st}  sarvam_state={sarvam}")
            if st in ("completed", "failed"):
                if status.get("error_message"):
                    print(f"   Error: {status['error_message']}")
                break

        # 6. Get transcript
        r = await c.get(f"{BASE}/jobs/{job_id}/transcript")
        if r.status_code == 200:
            t = r.json()
            print(f"6. Transcript ({len(t['full_text'])} chars): {t['full_text'][:300]}")
        else:
            print(f"6. Transcript not ready: {r.status_code} {r.text[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
