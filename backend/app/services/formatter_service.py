import re
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger("icepot")


class FormatterService:
    """Generates downloadable transcript formats with ICEPOT analysis."""

    _icepot_service = None

    @classmethod
    def _get_icepot(cls):
        """Lazy-init IcepotService."""
        if cls._icepot_service is None:
            from app.services.icepot_service import IcepotService
            cls._icepot_service = IcepotService()
        return cls._icepot_service

    @staticmethod
    def to_txt(
        full_text: str,
        diarized_json: Optional[List[Dict[str, Any]]] = None,
        *,
        filename: str = "unknown",
        duration_seconds: float = 0,
        language: str = "en-IN",
        file_format: str = "wav",
        file_size: str = "0",
    ) -> str:
        """Generate ICEPOT HTML analysis report via Groq LLM."""
        # Build plain text from diarized or full text
        if diarized_json and len(diarized_json) > 0:
            plain_text = " ".join(
                entry.get("text", "").strip()
                for entry in diarized_json
                if entry.get("text", "").strip()
            )
        else:
            plain_text = full_text.strip() if full_text else ""

        if not plain_text:
            return "<p>No transcript available.</p>"

        # Send to ICEPOT analysis via Groq
        try:
            icepot = FormatterService._get_icepot()
            return icepot.analyze(
                plain_text,
                filename=filename,
                duration_seconds=duration_seconds,
                language=language,
                file_format=file_format,
                file_size=file_size,
            )
        except Exception as e:
            logger.error(f"ICEPOT analysis failed: {e}")
            # Return HTML fallback instead of raw text
            try:
                icepot = FormatterService._get_icepot()
                return icepot._fallback_output(
                    plain_text, filename, duration_seconds,
                    language, file_format, file_size,
                )
            except Exception:
                return f"<p>{plain_text}</p>"

    @staticmethod
    def _format_time_srt(seconds: float) -> str:
        """Format seconds to HH:MM:SS,mmm for SRT."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def _format_time_vtt(seconds: float) -> str:
        """Format seconds to HH:MM:SS.mmm for VTT."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    @staticmethod
    def to_srt(
        segments_json: Optional[List[Dict[str, Any]]] = None,
        diarized_json: Optional[List[Dict[str, Any]]] = None,
        full_text: str = "",
    ) -> str:
        """Generate SRT format transcript."""
        entries = segments_json or diarized_json

        if not entries:
            # Fallback: single block with no timestamps
            return f"1\n00:00:00,000 --> 00:00:00,000\n{full_text}\n"

        lines = []
        for i, entry in enumerate(entries, 1):
            start = entry.get("start", 0)
            end = entry.get("end", 0)
            text = entry.get("text", entry.get("transcript", ""))
            speaker = entry.get("speaker", "")

            start_str = FormatterService._format_time_srt(start)
            end_str = FormatterService._format_time_srt(end)

            prefix = f"[{speaker}] " if speaker else ""
            lines.append(f"{i}")
            lines.append(f"{start_str} --> {end_str}")
            lines.append(f"{prefix}{text}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def to_vtt(
        segments_json: Optional[List[Dict[str, Any]]] = None,
        diarized_json: Optional[List[Dict[str, Any]]] = None,
        full_text: str = "",
    ) -> str:
        """Generate WebVTT format transcript."""
        lines = ["WEBVTT", ""]
        entries = segments_json or diarized_json

        if not entries:
            lines.append("00:00:00.000 --> 00:00:00.000")
            lines.append(full_text)
            lines.append("")
            return "\n".join(lines)

        for i, entry in enumerate(entries, 1):
            start = entry.get("start", 0)
            end = entry.get("end", 0)
            text = entry.get("text", entry.get("transcript", ""))
            speaker = entry.get("speaker", "")

            start_str = FormatterService._format_time_vtt(start)
            end_str = FormatterService._format_time_vtt(end)

            if speaker:
                lines.append(f"{i}")
                lines.append(f"{start_str} --> {end_str}")
                lines.append(f"<v {speaker}>{text}")
            else:
                lines.append(f"{i}")
                lines.append(f"{start_str} --> {end_str}")
                lines.append(text)
            lines.append("")

        return "\n".join(lines)
