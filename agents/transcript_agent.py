"""Summarize earnings call transcripts (non-numeric insights)."""

from __future__ import annotations

import json
import logging
from pydantic import BaseModel, Field, field_validator

from agents.earnings_v3_models import CallInsights
from llm.gemini_client import GEMINI_MODEL, generate_json, make_client

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL
MAX_TRANSCRIPT_CHARS = 24_000


class TranscriptAnalysisOutput(BaseModel):
    highlights: list[str] = Field(default_factory=list)
    qa_red_flags: list[str] = Field(default_factory=list)

    @field_validator("highlights", "qa_red_flags")
    @classmethod
    def cap_items(cls, v: list[str]) -> list[str]:
        return v[:4]


SYSTEM = """\
Summarize an earnings call transcript for semiconductor/AI investors (zh-TW).
Do NOT invent revenue, EPS, or margin numbers.
highlights: up to 3 bullets (management points).
qa_red_flags: up to 3 bullets (analyst concerns / evasive answers).
Each bullet must be a short paraphrase; optional short English quote fragment if in transcript.
Output JSON only.
"""


class TranscriptAgent:
    def __init__(self):
        self._client = None

    def analyze(self, transcript: str) -> CallInsights:
        text = (transcript or "").strip()
        if len(text) < 200:
            return CallInsights()
        clipped = text[:MAX_TRANSCRIPT_CHARS]
        prompt = f"Transcript:\n{clipped}\n\nReturn JSON with highlights and qa_red_flags."
        try:
            data, _ = generate_json(
                self._gemini_client,
                model=MODEL,
                max_output_tokens=1024,
                system_instruction=SYSTEM,
                prompt=prompt,
                response_schema=TranscriptAnalysisOutput,
            )
            out = TranscriptAnalysisOutput(**data)
            highlights = [h.strip() for h in out.highlights if h.strip()][:3]
            flags = [f.strip() for f in out.qa_red_flags if f.strip()][:3]
            return CallInsights(highlights=highlights, qa_red_flags=flags)
        except Exception as exc:
            logger.warning("TranscriptAgent failed: %s", exc)
            return CallInsights()

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client
