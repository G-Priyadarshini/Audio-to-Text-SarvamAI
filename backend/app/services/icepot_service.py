"""
ICEPOT Service — Comprehensive audio-content analysis powered by Groq LLM.

Produces a structured plain-text report with ten sections:
  1. File Details
  2. Audio Transcription
  3. Summary
  4. Description
  5. MOM (Minutes of Meeting)
  6. Keywords Extraction
  7. Technical Properties & Quality Metrics
  8. Content Analysis Parameters
  9. Recommendations
  10. Overall Assessment
"""

import logging
import re as _re
from groq import Groq
from app.config import settings

logger = logging.getLogger("icepot")


class IcepotService:
    """Generates ICEPOT plain-text analysis reports via Groq LLM."""

    # Maximum characters per LLM chunk — keeps each request within token limits
    MAX_TRANSCRIPT_CHARS_PER_CHUNK = 12000

    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #
    def analyze(
        self,
        transcript: str,
        *,
        filename: str = "unknown",
        duration_seconds: float = 0,
        language: str = "en-IN",
        file_format: str = "wav",
        file_size: str = "0",
    ) -> str:
        """
        Send transcript + metadata to Groq and return an ICEPOT plain-text report.
        For long transcripts (30+ min audio), splits into chunks and merges.
        Falls back to a simple text wrapper when the API is unavailable.
        """
        if not transcript or not transcript.strip():
            return "No transcript available."

        if not settings.GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not set — returning fallback")
            return self._fallback_output(transcript, filename, duration_seconds,
                                         language, file_format, file_size)

        try:
            # For long transcripts, process in chunks then merge
            if len(transcript) > self.MAX_TRANSCRIPT_CHARS_PER_CHUNK:
                logger.info(
                    f"Long transcript detected ({len(transcript)} chars). "
                    f"Splitting into chunks for complete analysis."
                )
                return self._analyze_long_transcript(
                    transcript,
                    filename=filename,
                    duration_seconds=duration_seconds,
                    language=language,
                    file_format=file_format,
                    file_size=file_size,
                )

            prompt = self._build_icepot_prompt(
                transcript, filename, duration_seconds,
                language, file_format, file_size,
            )
            logger.info(f"Sending ICEPOT prompt to Groq ({self.model})...")

            chat = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user",   "content": prompt},
                ],
                model=self.model,
                temperature=0.2,
                max_tokens=8192,
            )

            result = chat.choices[0].message.content.strip()

            # Strip markdown fences if Groq wraps the output
            if result.startswith("```"):
                first_newline = result.index("\n") if "\n" in result else 3
                result = result[first_newline + 1:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()

            logger.info(f"ICEPOT report received ({len(result)} chars)")
            return result

        except Exception as e:
            logger.error(f"Groq ICEPOT error: {e}")
            return self._fallback_output(transcript, filename, duration_seconds,
                                         language, file_format, file_size)

    # ------------------------------------------------------------------ #
    #  Long Transcript Handling                                           #
    # ------------------------------------------------------------------ #
    def _analyze_long_transcript(
        self,
        transcript: str,
        *,
        filename: str,
        duration_seconds: float,
        language: str,
        file_format: str,
        file_size: str,
    ) -> str:
        """
        Split long transcripts into chunks, analyze each chunk for key points,
        then produce a final merged ICEPOT report covering ALL content.
        """
        chunks = self._split_transcript(transcript, self.MAX_TRANSCRIPT_CHARS_PER_CHUNK)
        logger.info(f"Split transcript into {len(chunks)} chunks")

        # Step 1: Extract detailed notes from each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Processing chunk {i}/{len(chunks)} ({len(chunk)} chars)")
            try:
                chunk_analysis = self._analyze_chunk(chunk, i, len(chunks))
                chunk_summaries.append(chunk_analysis)
                logger.info(f"Chunk {i} analysis: {len(chunk_analysis)} chars")
            except Exception as e:
                logger.error(f"Error analyzing chunk {i}: {e}")
                chunk_summaries.append(
                    f"--- Chunk {i} ---\n{chunk[:2000]}\n(Analysis failed)\n"
                )

        # Step 2: Merge all chunk analyses into one final ICEPOT report
        merged_notes = "\n\n".join(chunk_summaries)
        logger.info(
            f"Merging {len(chunk_summaries)} chunk analyses "
            f"({len(merged_notes)} chars) into final report"
        )

        return self._build_final_merged_report(
            merged_notes=merged_notes,
            full_transcript=transcript,
            filename=filename,
            duration_seconds=duration_seconds,
            language=language,
            file_format=file_format,
            file_size=file_size,
        )

    def _split_transcript(self, transcript: str, max_chars: int) -> list:
        """Split transcript into chunks at sentence boundaries."""
        sentences = _re.split(r'(?<=[.!?])\s+', transcript.strip())
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 > max_chars and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # If no sentence splitting happened (e.g., no punctuation), force split
        if not chunks:
            for i in range(0, len(transcript), max_chars):
                chunks.append(transcript[i:i + max_chars])

        return chunks

    def _analyze_chunk(self, chunk: str, chunk_num: int, total_chunks: int) -> str:
        """Extract ALL key points, topics, dialogues, and details from a chunk."""
        prompt = f"""You are analyzing chunk {chunk_num} of {total_chunks} from a long audio transcript.

Extract ALL of the following from this chunk — be EXHAUSTIVE, do not skip anything:

1. **All Topics Covered**: List every distinct topic or subject discussed
2. **All Dialogues/Conversations**: Reproduce key dialogues and exchanges word-for-word
3. **All Key Points**: Every important point, tip, fact, or instruction mentioned
4. **All Examples Given**: Any examples, scenarios, or illustrations used
5. **Speaker Information**: Who is speaking and their role
6. **Vocabulary/Phrases**: Any notable vocabulary, phrases, or expressions used
7. **Actionable Items**: Any advice, instructions, or calls to action

IMPORTANT: Be thorough. Include EVERY point discussed, not just the main ones.
This chunk represents part of a longer audio — capture everything.

=== CHUNK {chunk_num}/{total_chunks} ===
{chunk}
=== END CHUNK ===

Return a detailed, exhaustive analysis of this chunk in plain text.
Do NOT use HTML. Use Markdown formatting (##, -, *, numbered lists).
"""

        chat = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a thorough content analyst. Extract ALL details "
                        "from the given transcript chunk. Be exhaustive — do not "
                        "summarize or skip any content. Return plain text only, no HTML."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            model=self.model,
            temperature=0.1,
            max_tokens=4096,
        )

        result = chat.choices[0].message.content.strip()
        # Strip fences
        if result.startswith("```"):
            first_newline = result.index("\n") if "\n" in result else 3
            result = result[first_newline + 1:]
        if result.endswith("```"):
            result = result[:-3]

        return f"--- Analysis of Part {chunk_num}/{total_chunks} ---\n{result.strip()}"

    def _build_final_merged_report(
        self,
        merged_notes: str,
        full_transcript: str,
        filename: str,
        duration_seconds: float,
        language: str,
        file_format: str,
        file_size: str,
    ) -> str:
        """Build the final ICEPOT report from all chunk analyses."""
        dur_str = self._format_duration(duration_seconds)

        # Include first and last portions of transcript for context
        transcript_preview = full_transcript[:3000]
        transcript_end = full_transcript[-2000:] if len(full_transcript) > 5000 else ""

        prompt = f"""You have detailed analyses of ALL parts of a long audio transcript.
Your job is to compile these into ONE comprehensive ICEPOT report.

CRITICAL INSTRUCTIONS:
- Include ALL topics, points, dialogues, and details from EVERY chunk analysis.
- Do NOT summarize briefly — be thorough and detailed.
- The audio is {dur_str} long — the report should reflect the full depth of content.
- Every topic and sub-topic covered in the audio MUST appear in the report.

=== FILE METADATA ===
Filename   : {filename}
Format     : {file_format}
Duration   : {dur_str}
Language   : {language}
File size  : {file_size} bytes

=== DETAILED ANALYSES FROM ALL PARTS ===
{merged_notes}
=== END OF CHUNK ANALYSES ===

=== TRANSCRIPT START (first portion) ===
{transcript_preview}
=== END PREVIEW ===

{"=== TRANSCRIPT END (last portion) ===" + chr(10) + transcript_end + chr(10) + "=== END ===" if transcript_end else ""}

Now produce the FINAL ICEPOT report with exactly these 10 sections in PLAIN TEXT (no HTML):

## 1. File Details
A text table (using | pipes) with: File Name, Audio Format, Duration, Language, File Size.

## 2. Audio Transcription
Present the COMPLETE transcribed content organized by topic/section.
Include ALL dialogues and conversations — number each distinct exchange.
For a {dur_str} audio, this section should be DETAILED (20+ numbered items minimum).

## 3. Summary
A comprehensive summary (4-6 sentences) covering ALL major topics discussed in the audio.

## 4. Description
A detailed description (6-10 sentences) of the audio content including:
- All speakers identified
- All topics/sections covered
- The flow and structure of the content
- Tone, style, and teaching approach (if educational)

## 5. MOM (Minutes of Meeting)
- Topic: [Main topic]
- Participants: [Speakers]
- Key Discussion Points: [Numbered list — include ALL topics from all chunks]
- Decisions/Conclusions: [Any decisions reached]
- Action Items: [Any follow-ups or practice tasks mentioned]

## 6. Keywords
Extract 10-15 relevant keywords covering all topics discussed.

## 7. Technical Properties & Quality Metrics
A 2-column text table with technical properties and quality ratings.

## 8. Content Analysis Parameters
a) Clarity Score (1-10)
b) Completeness Score (1-10)
c) Testability Score (1-10)

## 9. Recommendations
A numbered list of issues and actionable recommendations (minimum 5 items).

## 10. Overall Assessment
Strengths, Weaknesses, Key Takeaways, Suggested Next Steps.

IMPORTANT:
- Return ONLY plain text. NO HTML tags.
- Use ## for headers, | for tables, - for bullets, numbered lists.
- Be THOROUGH — this is a {dur_str} audio. Cover EVERYTHING.
- The transcription section must have ALL key dialogues and points (not just 5-6).
"""

        chat = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": self._system_prompt(),
                },
                {"role": "user", "content": prompt},
            ],
            model=self.model,
            temperature=0.2,
            max_tokens=8192,
        )

        result = chat.choices[0].message.content.strip()
        if result.startswith("```"):
            first_newline = result.index("\n") if "\n" in result else 3
            result = result[first_newline + 1:]
        if result.endswith("```"):
            result = result[:-3]

        logger.info(f"Final merged ICEPOT report: {len(result.strip())} chars")
        return result.strip()

    # ------------------------------------------------------------------ #
    #  Prompts                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are ICEPOT Analyzer — an expert audio-content analysis engine. "
            "You receive a transcript and file metadata and produce a structured "
            "plain-text report following the ICEPOT framework. "
            "The report MUST include Summary, Description, and MOM (Minutes of Meeting) sections. "
            "Return ONLY clean plain text using Markdown-style formatting (##, -, *, |). "
            "Do NOT use any HTML tags whatsoever. No <div>, <table>, <p>, <h2>, <span>, or any HTML. "
            "Use section headers with ## prefix, tables with | pipe formatting, and lists with - or numbered items. "
            "Be THOROUGH and EXHAUSTIVE — cover every topic and detail from the transcript. "
            "Tone: professional, analytical, precise."
        )

    def _build_icepot_prompt(
        self, transcript, filename, duration, language, fmt, size,
    ) -> str:
        dur_str = self._format_duration(duration)
        return f"""Analyze the following audio transcript and metadata.
Produce an ICEPOT report in plain text with Markdown-style formatting.
Do NOT use any HTML tags. Use ## for headers, | for tables, - for lists, and numbered items.

=== FILE METADATA ===
Filename   : {filename}
Format     : {fmt}
Duration   : {dur_str}
Language   : {language}
File size  : {size} bytes

=== TRANSCRIPT ===
{transcript}
=== END TRANSCRIPT ===

Return the report with exactly these 10 sections in PLAIN TEXT (no HTML):

SECTION 1 — File Details
A text table (using | pipes) with rows: File Name, Audio Format, Bitrate (estimate or N/A),
Duration, Channels (estimate or N/A).

SECTION 2 — Audio Transcription
The complete transcribed text in clean, readable paragraphs.
Fix obvious speech-to-text errors. Preserve meaning.
Present as numbered messages/sentences for clarity.
Include ALL content — do not skip or truncate. List every dialogue and point.

SECTION 3 — Summary
A concise 4-6 sentence summary of the entire audio content.
Capture ALL main topics discussed, the purpose, and conclusion.

SECTION 4 — Description
A detailed description of the audio content in 6-10 sentences.
Include:
- Who is speaking (if identifiable — e.g., two people, a presenter, etc.)
- What is the context/setting of the conversation
- ALL topics discussed (not just the first few)
- The flow of the conversation (beginning, middle, end)
- Any notable tone, emotion, or emphasis detected

SECTION 5 — MOM (Minutes of Meeting)
Format this as a structured meeting minutes document with:
- Date: [Use today's date or mention "From audio"]
- Participants: [Identify speakers if possible, otherwise "Speaker 1, Speaker 2" etc.]
- Agenda/Topic: [Main topic discussed]
- Key Discussion Points: [Numbered list of ALL main points discussed — be thorough]
- Decisions Made: [Any decisions or agreements reached]
- Action Items: [Any tasks, next steps, or follow-ups mentioned]
- Conclusion: [How the conversation ended]
If the audio is NOT a meeting (e.g., a monologue, narration, song),
adapt the MOM format to fit: use "Key Points" instead of "Discussion Points",
skip "Participants" if only one speaker, etc.

SECTION 6 — Keywords
Extract 10-15 relevant keywords. Display as a comma-separated list or bullet points.

SECTION 7 — Technical Properties & Quality Metrics
A 2-column text table using | pipes.
Left column: Technical Properties (format, sample rate, bit depth, channels).
Right column: Quality Metrics (Signal clarity, Background noise level,
Speech intelligibility, Overall quality — each with a rating like High/Medium/Low
and a short note). Estimate values you cannot determine from metadata.

SECTION 8 — Content Analysis Parameters
Three sub-sections:
  a) Clarity Score (1-10 with one-line explanation)
  b) Completeness Score (1-10 with one-line explanation)
  c) Testability Score (1-10 with one-line explanation)

SECTION 9 — Recommendations
A numbered list (minimum 5 items). Each item has an Issue and an Actionable Recommendation.

SECTION 10 — Overall Assessment
Four bullet groups: Strengths, Weaknesses, Key Takeaways, Suggested Next Steps.

Important:
- Return ONLY plain text. No HTML tags at all.
- Every section should have a ## header with section number.
- Use | pipe tables, - bullet lists, and numbered lists.
- Be EXHAUSTIVE — cover ALL content from the transcript, not just highlights.
- The Summary, Description, and MOM sections are MANDATORY — never skip them.
"""

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _format_duration(seconds: float) -> str:
        if not seconds:
            return "N/A"
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h {m}m {s}s"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"

    def _fallback_output(self, transcript, filename, duration,
                         language, fmt, size) -> str:
        """Minimal plain-text output when Groq is unavailable."""
        dur_str = self._format_duration(duration)

        # Build numbered sentences for transcription
        sentences = _re.split(r'(?<=[.!?])\s+', transcript.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        numbered = ""
        for i, s in enumerate(sentences, 1):
            numbered += f"  {i}. {s}\n"
        if not numbered:
            numbered = f"  {transcript}\n"

        # Summary from first/last sentences
        if len(sentences) <= 2:
            summary = " ".join(sentences)
        else:
            summary = (
                f"{sentences[0]} The content covers {len(sentences)} points "
                f"and concludes with: {sentences[-1]}"
            )

        topic = sentences[0] if sentences else 'N/A'
        key_points = ""
        for i, s in enumerate(sentences[:20], 1):
            key_points += f"  {i}. {s}\n"
        if not key_points:
            key_points = "  N/A\n"
        conclusion = sentences[-1] if sentences else 'N/A'

        return f"""============================================================
                    ICEPOT AUDIO ANALYSIS REPORT
============================================================

## 1. File Details

| Property   | Value            |
|------------|------------------|
| File Name  | {filename}       |
| Format     | {fmt}            |
| Duration   | {dur_str}        |
| Language   | {language}       |
| Size       | {size} bytes     |

------------------------------------------------------------

## 2. Audio Transcription

{numbered}
------------------------------------------------------------

## 3. Summary

{summary}

------------------------------------------------------------

## 4. Description

The audio file "{filename}" is {dur_str} long and contains speech content
in {language}. The transcript contains {len(sentences)} sentences/segments.
A detailed AI-powered description is unavailable because the Groq API key
is not configured or the service is temporarily unavailable.

------------------------------------------------------------

## 5. MOM (Minutes of Meeting)

- **Topic:** {topic}
- **Key Discussion Points:**
{key_points}
- **Conclusion:** {conclusion}

Note: Detailed MOM generation requires Groq API access.

------------------------------------------------------------

## 6. Keywords

Groq API unavailable — keyword extraction skipped.

------------------------------------------------------------

## 7. Technical Properties & Quality Metrics

| Technical Properties | Quality Metrics          |
|----------------------|--------------------------|
| Format: {fmt}        | Clarity: N/A             |
| Sample Rate: N/A     | Noise Level: N/A         |
| Bit Depth: N/A       | Intelligibility: N/A     |
| Channels: N/A        | Overall Quality: N/A     |

Groq API unavailable — detailed analysis skipped.

------------------------------------------------------------

## 8. Content Analysis Parameters

a) Clarity Score: N/A — Groq API unavailable
b) Completeness Score: N/A — Groq API unavailable
c) Testability Score: N/A — Groq API unavailable

------------------------------------------------------------

## 9. Recommendations

Groq API unavailable — recommendations skipped.

------------------------------------------------------------

## 10. Overall Assessment

- **Strengths:** Transcript captured ({len(sentences)} segments).
- **Weaknesses:** AI-powered analysis unavailable.
- **Key Takeaways:** Audio was transcribed; full analysis requires Groq API.
- **Suggested Next Steps:** Configure GROQ_API_KEY for complete ICEPOT analysis.

============================================================
"""
