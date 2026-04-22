"""Test the audio splitting path with a 60-second WAV file."""
import httpx
import asyncio
import struct
import math
import io

BASE = "http://localhost:8000/api"


def create_test_wav(duration, sample_rate=16000, frequency=440):
    num_samples = int(duration * sample_rate)
    samples = [
        struct.pack("<h", int(32767 * 0.5 * math.sin(2 * math.pi * frequency * i / sample_rate)))
        for i in range(num_samples)
    ]
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
    wav = create_test_wav(duration=60)
    print(f"Test WAV: {len(wav)} bytes (60s → should split into 3 chunks)")

    async with httpx.AsyncClient(timeout=300) as c:
        r = await c.post(f"{BASE}/jobs", json={"language": "en-IN", "mode": "batch"})
        job = r.json()
        jid = job["id"]
        print(f"Job: {jid}")

        await c.post(f"{BASE}/jobs/{jid}/upload/init", json={"total_chunks": 1, "file_size": len(wav)})
        await c.post(f"{BASE}/jobs/{jid}/upload/chunks/0", files={"file": ("c.wav", wav, "audio/wav")})
        await c.post(f"{BASE}/jobs/{jid}/upload/complete")
        print("Upload complete, polling...")

        for i in range(60):
            await asyncio.sleep(3)
            r = await c.get(f"{BASE}/jobs/{jid}/status")
            s = r.json()
            st = s["status"]
            sarvam = s.get("sarvam_state", "")
            err = s.get("error_message", "")
            print(f"  {i}: status={st}  sarvam={sarvam}")
            if st in ("completed", "failed"):
                if err:
                    print(f"  ERROR: {err}")
                break

        r = await c.get(f"{BASE}/jobs/{jid}/transcript")
        if r.status_code == 200:
            t = r.json()
            print(f"Transcript ({len(t['full_text'])} chars): {t['full_text'][:200]}")
        else:
            print(f"Transcript: {r.status_code} {r.text[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
