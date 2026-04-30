"""Deep-tier argument extraction and Chinese insight brief generation."""

from __future__ import annotations

import json
import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from llm.gemini_client import GEMINI_MODEL, generate_json, make_client
from sources.deep_scraper import count_mixed_words

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL

DEEP_EXTRACTOR_SYSTEM = """\
You are an academic argument analyst. Your task is not to summarize.
Map the logical structure of the article and reply only with valid JSON.
Evidence must be near-verbatim from the source. Do not invent numbers or technical terms.
"""

DEEP_EXTRACTOR_PROMPT = """\
Extract an ArgumentMap from this deep technology article.

Fields:
- title
- author
- source_name
- url
- domain: one of ["ai", "semiconductor", "crypto", "other"]
- tier: "deep"
- core_thesis: the author's central claim in one sentence
- evidence: 2-5 near-verbatim claims, data points, mechanisms, or examples from source
- assumption: the implicit premise needed for the thesis to hold, or null
- counter_ignored: one obvious counterargument not addressed, or null
- score: article score from upstream
- confidence: "high", "medium", or "low"
- item_id

Title: {title}
Author: {author}
Source: {source_name}
URL: {url}
Domain hints: {domain_hints}
Score: {score}
Item ID: {item_id}

Article text:
{text}
"""

BRIEF_SYSTEM = """\
You are a senior technology analyst writing Chinese reading guidance for #科技脈搏.
Write clearly for a technical investor/operator audience.
Keep English technical terms when translation would reduce precision.
Reply only with valid JSON.
"""

BRIEF_PROMPT = """\
Create a Chinese InsightBrief from this ArgumentMap.

Requirements:
- Total length across insight + tech_rationale + implication must be 100-200 Chinese-readable characters/tokens.
- insight: core thesis or contrarian point.
- tech_rationale: explain the technical mechanism using only the evidence.
- implication: who or what changes in the ecosystem.
- Do not cite facts that are absent from evidence.

ArgumentMap JSON:
{argument_json}
"""


class ArgumentMap(BaseModel):
    title: str
    author: Optional[str] = None
    source_name: str
    url: str
    domain: Literal["ai", "semiconductor", "crypto", "other"] = "other"
    tier: Literal["deep"] = "deep"
    core_thesis: str
    evidence: list[str] = Field(default_factory=list)
    assumption: Optional[str] = None
    counter_ignored: Optional[str] = None
    score: float = 0.0
    confidence: Literal["high", "medium", "low"] = "medium"
    item_id: str


class InsightBrief(BaseModel):
    item_id: str
    title: str
    author: Optional[str] = None
    source_name: str
    url: str
    domain: Literal["ai", "semiconductor", "crypto", "other"] = "other"
    insight: str
    tech_rationale: str
    implication: str
    word_count: int = 0
    cross_ref: bool = False
    confidence: Literal["high", "medium", "low"] = "medium"

    @model_validator(mode="after")
    def enforce_summary_length(self):
        total = count_mixed_words(" ".join([self.insight, self.tech_rationale, self.implication]))
        self.word_count = total
        if total < 100 or total > 200:
            raise ValueError(f"InsightBrief is {total} words/chars, must be 100-200")
        return self


class DeepInsightAgent:
    """Runs the deep article chain: ArgumentMap -> review -> InsightBrief."""

    def __init__(self):
        self._client = make_client()

    def extract_argument_map(
        self,
        *,
        title: str,
        text: str,
        source_name: str,
        url: str,
        author: str = "",
        domain_hints: list[str] | None = None,
        score: float = 0.0,
        item_id: str = "",
    ) -> Optional[ArgumentMap]:
        prompt = DEEP_EXTRACTOR_PROMPT.format(
            title=title,
            author=author or "unknown",
            source_name=source_name,
            url=url,
            domain_hints=", ".join(domain_hints or []),
            score=f"{score:.1f}",
            item_id=item_id,
            text=text[:10000],
        )
        try:
            data, _ = generate_json(
                self._client,
                model=MODEL,
                max_output_tokens=1536,
                system_instruction=DEEP_EXTRACTOR_SYSTEM,
                prompt=prompt,
                response_schema=ArgumentMap,
            )
            return ArgumentMap(**data)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Deep ArgumentMap extraction failed for '%s': %s", title[:80], exc)
            return None

    def review_argument_map(self, argument: ArgumentMap) -> Optional[ArgumentMap]:
        if not argument.evidence:
            logger.warning("Deep article rejected: no evidence for '%s'", argument.title[:80])
            return None
        if not argument.assumption or not argument.counter_ignored:
            argument.confidence = "low"
        return argument

    def synthesize_brief(self, argument: ArgumentMap) -> Optional[InsightBrief]:
        argument_json = json.dumps(argument.model_dump(), ensure_ascii=False, indent=2)
        prompt = BRIEF_PROMPT.format(argument_json=argument_json[:6000])
        try:
            data, _ = generate_json(
                self._client,
                model=MODEL,
                max_output_tokens=1024,
                system_instruction=BRIEF_SYSTEM,
                prompt=prompt,
                response_schema=InsightBrief,
            )
            return InsightBrief(**data)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Deep InsightBrief synthesis failed for '%s': %s", argument.title[:80], exc)
            return None

    def create_brief(
        self,
        *,
        title: str,
        text: str,
        source_name: str,
        url: str,
        author: str = "",
        domain_hints: list[str] | None = None,
        score: float = 0.0,
        item_id: str = "",
        cross_ref: bool = False,
    ) -> Optional[InsightBrief]:
        argument = self.extract_argument_map(
            title=title,
            text=text,
            source_name=source_name,
            url=url,
            author=author,
            domain_hints=domain_hints,
            score=score,
            item_id=item_id,
        )
        if not argument:
            return None
        reviewed = self.review_argument_map(argument)
        if not reviewed:
            return None
        brief = self.synthesize_brief(reviewed)
        if brief:
            brief.cross_ref = cross_ref
            if reviewed.confidence == "low":
                brief.confidence = "low"
        return brief
