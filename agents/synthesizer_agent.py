"""Layer 2 agent: cross-article theme synthesis and daily digest narrative."""

import json
import logging
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

from llm.gemini_client import GEMINI_MODEL, generate_json, make_client
from .extractor_agent import ArticleSummary

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL

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
    """Wraps the Gemini API for cross-article digest synthesis."""

    def __init__(self):
        self._client = make_client()

    def synthesize(self, summaries: list[ArticleSummary]) -> Optional[DigestOutput]:
        if not summaries:
            logger.warning("Synthesizer received empty summaries list")
            return None

        summaries_json = json.dumps(
            [s.model_dump() for s in summaries], ensure_ascii=False, indent=2
        )
        prompt = SYNTHESIS_PROMPT.format(summaries_json=summaries_json[:12000])

        try:
            data, raw = generate_json(
                self._client,
                model=MODEL,
                max_output_tokens=2048,
                system_instruction=SYSTEM_PROMPT,
                prompt=prompt,
                response_schema=DigestOutput,
            )
            if "date" not in data:
                data["date"] = date.today().isoformat()
            return DigestOutput(**data)

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error from synthesizer: %s", exc)
            return None
        except Exception as exc:
            logger.error("Synthesizer agent failed: %s", exc)
            return None
