"""Layer 2 agent: cross-article theme synthesis and daily digest narrative."""

import difflib
import json
import logging
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

from llm.gemini_client import GEMINI_MODEL, generate_json, make_client
from llm.localization import normalize_llm_payload
from .extractor_agent import ArticleSummary

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL

SYSTEM_PROMPT = """\
You are a senior tech analyst writing a daily intelligence digest for a professional audience.
You receive a batch of pre-extracted article summaries and must synthesize them into a coherent narrative.

Rules:
- Absolute language lock: output every final string EXCLUSIVELY in fluent, professional Traditional Chinese (zh-TW), regardless of source language.
- Only reference claims that appear in the provided summaries. Do not add outside knowledge.
- Identify genuine cross-article themes, not superficial keyword matches.
- Explicitly flag contradictions between sources.
- Write in clear, direct prose. No hype, no filler.
- Avoid weak summarization phrases such as "這篇文章報導了", "本文指出", or "作者認為"; start directly with the thesis.
- Output valid JSON only.
"""

SYNTHESIS_PROMPT = """\
Given the article summaries below, produce a daily tech digest.

Return a JSON object with these fields:
- date: today's date as ISO string
- headline: one punchy Traditional Chinese headline summarising the day's biggest story (string)
- themes: list of up to 4 cross-article themes, each with:
    - theme: theme name in Traditional Chinese (string)
    - description: 2-sentence Traditional Chinese explanation (string)
    - supporting_entities: list of entities involved (list of strings)
    - confidence: "high" | "medium" | "low"
- contradictions: list of any conflicting claims across sources (list of strings, may be empty)
- narrative: 3–5 paragraph Traditional Chinese digest narrative suitable for Telegram (string)
- top_stories: list of up to 3 high-signal stories, each with:
    - entity: company/protocol/technology name (string)
    - title: source title or concise rewritten title (string)
    - source_name: stable source id from ArticleSummary.source_name (string)
    - source_display_name: ArticleSummary.source_display_name when present, otherwise source_name (string)
    - source_url: ArticleSummary.source_url (string)
    - source_language: ArticleSummary.source_language, usually "en" or "zh-TW" (string)
    - insight: maps to 【核心洞見】; one sentence capturing the contrarian view, architectural breakthrough, or core thesis. Max 40 Chinese words.
    - tech_rationale: maps to 【底層邏輯】; explain how the mechanism works, why the bottleneck exists, or what makes the protocol sound. No fluff. 80-100 Chinese words.
    - implication: maps to 【生態影響】; explain what changes in the industry stack, who loses share, or the second-order effect. Max 50 Chinese words.
- cross_ref_count: number of cross_ref=true articles (int)

Do not make the first sentence of "narrative" paraphrase the "headline" (same thesis in different words). Open narrative with a complementary angle, mechanism detail, or tension across sources. The Telegram preamble uses narrative line 1 separately—ensure headline vs narrative line 1 are meaningfully distinct.

Article summaries (JSON array):
{summaries_json}
"""


class Theme(BaseModel):
    theme: str
    description: str
    supporting_entities: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


class StoryInsight(BaseModel):
    entity: str = ""
    title: str = ""
    source_name: str = ""
    source_display_name: str = ""
    source_url: str = ""
    source_language: str = "en"
    insight: str = ""
    tech_rationale: str = ""
    implication: str = ""
    summary: str = ""


class DigestOutput(BaseModel):
    date: str
    headline: str
    themes: list[Theme] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    narrative: str
    top_stories: list[StoryInsight] = Field(default_factory=list)
    cross_ref_count: int = 0


class SynthesizerAgent:
    """Wraps the Gemini API for cross-article digest synthesis."""

    def __init__(self):
        self._client = None

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
                self._gemini_client,
                model=MODEL,
                max_output_tokens=3072,
                system_instruction=SYSTEM_PROMPT,
                prompt=prompt,
                response_schema=DigestOutput,
            )
            data = normalize_llm_payload(data)
            if "date" not in data:
                data["date"] = date.today().isoformat()
            return DigestOutput(**data)

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error from synthesizer: %s", exc)
            return None
        except Exception as exc:
            logger.error("Synthesizer agent failed: %s", exc)
            return None

    @staticmethod
    def build_market_takeaway(digest: DigestOutput) -> str:
        """Build a short 1-2 line takeaway from digest narrative/themes for item digest preamble."""
        headline = (digest.headline or "").strip()

        def _similar(a: str, b: str) -> float:
            a, b = a.strip(), b.strip()
            if not a or not b:
                return 0.0
            return float(difflib.SequenceMatcher(None, a, b).ratio())

        if digest.narrative:
            lines = [ln.strip() for ln in digest.narrative.splitlines() if ln.strip()]
            for line in lines[:5]:
                if len(line) < 10:
                    continue
                if headline and _similar(line, headline) > 0.55:
                    continue
                return line[:180]
        if digest.themes:
            return "；".join(theme.theme for theme in digest.themes[:2])
        return ""

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client
