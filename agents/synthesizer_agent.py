"""Layer 2 agent: cross-article theme synthesis and daily digest narrative."""

import json
import logging
import os
from datetime import date
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field

from .extractor_agent import ArticleSummary

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """\
You are a senior tech analyst writing a daily intelligence digest for a professional audience.
You receive a batch of pre-extracted article summaries and must synthesize them into a coherent narrative.

Rules:
- Only reference claims that appear in the provided summaries. Do not add outside knowledge.
- Identify genuine cross-article themes, not superficial keyword matches.
- Explicitly flag contradictions between sources.
- Write in clear, direct prose. No hype, no filler.
- Output valid JSON only.
"""

SYNTHESIS_PROMPT = """\
Given the article summaries below, produce a daily tech digest.

Return a JSON object with these fields:
- date: today's date as ISO string
- headline: one punchy headline summarising the day's biggest story (string)
- themes: list of up to 4 cross-article themes, each with:
    - theme: theme name (string)
    - description: 2-sentence explanation (string)
    - supporting_entities: list of entities involved (list of strings)
    - confidence: "high" | "medium" | "low"
- contradictions: list of any conflicting claims across sources (list of strings, may be empty)
- narrative: 3–5 paragraph digest narrative suitable for Telegram (string)
- top_stories: list of up to 5 ArticleSummary entity+summary pairs worth highlighting
- cross_ref_count: number of cross_ref=true articles (int)

Article summaries (JSON array):
{summaries_json}
"""


class Theme(BaseModel):
    theme: str
    description: str
    supporting_entities: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


class DigestOutput(BaseModel):
    date: str
    headline: str
    themes: list[Theme] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    narrative: str
    top_stories: list[dict] = Field(default_factory=list)
    cross_ref_count: int = 0


class SynthesizerAgent:
    """Wraps the Claude API for cross-article digest synthesis."""

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

    def synthesize(self, summaries: list[ArticleSummary]) -> Optional[DigestOutput]:
        if not summaries:
            logger.warning("Synthesizer received empty summaries list")
            return None

        summaries_json = json.dumps(
            [s.model_dump() for s in summaries], ensure_ascii=False, indent=2
        )
        prompt = SYNTHESIS_PROMPT.format(summaries_json=summaries_json[:12000])

        try:
            message = self._client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            data = json.loads(raw)
            if "date" not in data:
                data["date"] = date.today().isoformat()
            return DigestOutput(**data)

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error from synthesizer: %s | raw=%s", exc, raw[:200])
            return None
        except Exception as exc:
            logger.error("Synthesizer agent failed: %s", exc)
            return None
