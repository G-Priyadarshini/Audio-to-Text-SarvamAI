import os
import subprocess
from pathlib import Path

COMMON_PATHS = [
    Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
    Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
    Path(r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"),
    Path(r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"),
    Path(r"C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin\ffmpeg.exe"),
]


def which_ffmpeg() -> str | None:
    # Try common locations
    for p in COMMON_PATHS:
        if p.exists():
            return str(p)

    # Try where.exe (Windows)
    try:
        out = subprocess.check_output(["where", "ffmpeg"], stderr=subprocess.DEVNULL, text=True)
        first = out.splitlines()[0].strip()
        if first:
            return first
    except Exception:
        pass

    # Try scanning user profile (limited depth)
    home = Path.home()
    for root, dirs, files in os.walk(home):
        for fname in files:
            if fname.lower() == "ffmpeg.exe":
                return str(Path(root) / fname)
        # limit search depth
        if len(Path(root).relative_to(home).parts) > 4:
            # prune deeper dirs for speed
            dirs[:] = []

    return None


def update_env(ffmpeg_path: str) -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print(".env not found; create one or set FFMPEG_BINARY manually")
        return

    text = env_path.read_text(encoding="utf-8")
    key = "FFMPEG_BINARY="
    newline = f"FFMPEG_BINARY={ffmpeg_path}"
    if key in text:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith(key):
                lines[i] = newline
                break
        text = "\n".join(lines) + "\n"
    else:
        text = text + "\n" + newline + "\n"

    env_path.write_text(text, encoding="utf-8")
    print(f"Updated {env_path} with FFMPEG_BINARY={ffmpeg_path}")


def main():
    print("Detecting ffmpeg...")
    path = which_ffmpeg()
    if not path:
        print("ffmpeg not found on system. Please install ffmpeg and add it to PATH, or set FFMPEG_BINARY in .env manually.")
        return

    print("Found ffmpeg:", path)
    update_env(path)


if __name__ == "__main__":
    main()
