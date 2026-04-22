import logging
from groq import Groq
from app.config import settings

logger = logging.getLogger("icepot")


class GroqService:
    """Uses Groq LLM to generate formatted MOM from plain transcript."""

    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    def generate_mom(self, plain_text: str) -> str:
        """
        Send plain transcript to Groq LLM and get formatted output
        with numbered messages, highlight, and MOM.
        """
        if not plain_text or not plain_text.strip():
            return "No transcript available."

        if not settings.GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not set, returning plain text")
            return plain_text

        try:
            prompt = self._build_prompt(plain_text)
            logger.info(f"Sending transcript to Groq ({self.model})...")

            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a transcript formatter. Your job is to take raw "
                            "speech-to-text output and format it into a clean, structured "
                            "output with numbered messages, a highlight summary, and a "
                            "MOM (Message of the Moment). Follow the exact output format "
                            "specified by the user. Do not add any extra commentary or "
                            "explanation outside the format."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                model=self.model,
                temperature=0.3,
                max_tokens=2048,
            )

            result = chat_completion.choices[0].message.content.strip()
            logger.info(f"Groq response received ({len(result)} chars)")
            return result

        except Exception as e:
            logger.error(f"Groq API error: {e}")
            # Fallback to plain text if Groq fails
            return self._fallback_format(plain_text)

    def _build_prompt(self, plain_text: str) -> str:
        """Build the prompt for the LLM."""
        return f"""Analyze the following raw transcript from a speech-to-text system and format it exactly as shown below.

Rules:
1. Break the transcript into individual sentences/dialogues and number them.
2. Write a one-line "Highlight" summarizing what the conversation/audio is about.
3. Write a "MOM (Message of the Moment)" capturing the key takeaway or main message.
4. If there are multiple speakers, try to identify dialogue turns.
5. Clean up any speech-to-text errors or filler words.
6. Keep the original meaning intact.

Output format (follow this EXACTLY):
Here are the messages:

1. [First sentence/dialogue]
2. [Second sentence/dialogue]
3. [Continue numbering...]

Highlight: [One-line summary of the conversation/audio]

MOM (Message of the Moment): [Key takeaway or main message]

--- RAW TRANSCRIPT ---
{plain_text}
--- END TRANSCRIPT ---

Now format the above transcript:"""

    def _fallback_format(self, plain_text: str) -> str:
        """Fallback formatting if Groq API fails."""
        import re
        sentences = re.split(r'(?<=[.!?])\s+', plain_text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return plain_text

        lines = ["Here are the messages:\n"]
        for i, sentence in enumerate(sentences, 1):
            lines.append(f"{i}. {sentence}")

        lines.append("")
        lines.append(f"Highlight: {sentences[0]}")
        lines.append("")
        lines.append(f"MOM (Message of the Moment): {sentences[-1]}")

        return "\n".join(lines)
