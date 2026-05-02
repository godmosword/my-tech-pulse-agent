"""Layer 1 agent: per-article structured summary with confidence scoring."""

import json
import logging
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from llm.gemini_client import GEMINI_MODEL, generate_json, make_client

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL

SYSTEM_PROMPT = """\
You are a tech news extractor. Your only job is to extract structured information from a given article.

Rules:
- Only summarize what is explicitly stated in the source. Do not infer or add context.
- Never fabricate quotes, statistics, or claims not present in the article.
- Use confidence = "high" when all fields are directly supported by the text.
- Use confidence = "medium" when some fields require mild interpretation.
- Use confidence = "low" when the source is thin or ambiguous.
- Output valid JSON only. No markdown, no explanation.
"""

EXTRACTION_PROMPT = """\
Extract the following fields from the article below and return a single JSON object.

Fields:
- entity: primary company or technology mentioned (string)
- summary: max 2 sentence factual summary, no editorializing (string, fallback compatibility)
- what_happened: up to 3 concise sentences with objective facts only (numbers, timing, concrete actions) (string)
- why_it_matters: second sentence describing impact on industry/supply chain/valuation when supported; empty if insufficient info (string)
- category: one of ["product_launch", "funding", "acquisition", "earnings", "regulation", "research", "other"]
- key_facts: list of up to 5 specific factual claims (list of strings)
- sentiment: one of ["positive", "negative", "neutral"]
- confidence: one of ["high", "medium", "low"]
- cross_ref: true if this story is likely relevant to investment decisions (bool)

Formatting constraints for structured summary fields:
- what_happened must be one sentence of objective facts only.
- why_it_matters should be one sentence on implications for industry/supply chain/valuation only when the article supports it.
- If implication evidence is insufficient, set why_it_matters to an empty string.
- Keep summary as a compatible fallback narrative.
- Keep every field concise so the JSON object can complete within the token limit.

Article title: {title}
Article source: {source}
Article text:
{text}
"""


class ArticleSummary(BaseModel):
    entity: str
    summary: str
    what_happened: str = ""
    why_it_matters: str = ""
    category: Literal["product_launch", "funding", "acquisition", "earnings", "regulation", "research", "other"]
    key_facts: list[str] = Field(default_factory=list)
    sentiment: Literal["positive", "negative", "neutral"]
    confidence: Literal["high", "medium", "low"]
    cross_ref: bool = False
    source_url: str = ""
    source_name: str = ""
    source_display_name: str = ""
    source_language: str = "en"
    title: str = ""
    score: float = 0.0  # propagated from Scorer; 0.0 = unscored
    score_status: str = "ok"  # propagated from Scorer; "fallback" means score unavailable
    label: str = "news"   # "news" | "kol" — propagated from Article
    author: str = ""      # KOL author name; empty for standard news
    published_at: str = ""  # ISO timestamp propagated from source article when available
    history_context: str = ""  # optional retrieval-memory hint for downstream synthesis/display
    semantic_duplicate: bool = False
    semantic_distance: Optional[float] = None
    source_text: str = Field(default="", exclude=True)  # raw article text for reviewer; not serialized


class ExtractorAgent:
    """Wraps the Gemini API for per-article structured extraction."""

    def __init__(self):
        self._client = None

    def extract(self, title: str, text: str, source_name: str = "", source_url: str = "") -> Optional[ArticleSummary]:
        prompt = EXTRACTION_PROMPT.format(
            title=title,
            source=source_name,
            text=text[:4000],
        )
        try:
            data, raw = generate_json(
                self._gemini_client,
                model=MODEL,
                max_output_tokens=2048,
                system_instruction=SYSTEM_PROMPT,
                prompt=prompt,
                response_schema=ArticleSummary,
            )
            summary = ArticleSummary(**data)
            if not self._has_required_fields(summary):
                logger.warning(
                    "Extractor returned incomplete JSON for '%s' | missing_required_field",
                    title[:80],
                )
                return None
            summary.source_url = source_url
            summary.source_name = source_name
            return summary

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error from extractor: %s", exc)
            return None
        except Exception as exc:
            logger.error("Extractor agent failed for '%s': %s", title, exc)
            return None

    def extract_batch(self, articles: list[dict]) -> list[ArticleSummary]:
        results = []
        max_articles = int(os.getenv("MAX_EXTRACTION_ARTICLES", "8"))
        candidates = articles[:max_articles]
        if len(articles) > len(candidates):
            logger.info(
                "Extraction capped at %d/%d articles to stay within runtime budget",
                len(candidates), len(articles),
            )

        for article in candidates:
            text = article.get("content") or article.get("summary", "")
            result = self.extract(
                title=article.get("title", ""),
                text=text,
                source_name=article.get("source", ""),
                source_url=article.get("url", ""),
            )
            if result:
                result.score = float(article.get("score", 0.0))
                result.score_status = str(article.get("score_status", "ok"))
                result.title = article.get("title", "")
                result.label = str(article.get("label", "news"))
                result.author = str(article.get("author", ""))
                result.source_display_name = str(article.get("source_display_name", ""))
                result.source_language = str(article.get("source_language", "en") or "en")
                published_at = article.get("published_at")
                result.published_at = published_at.isoformat() if hasattr(published_at, "isoformat") else str(published_at or "")
                result.source_text = text[:4000]
                self._postprocess_flags(result)
                results.append(result)
        return results

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client

    def _postprocess_flags(self, summary: ArticleSummary) -> None:
        corpus = " ".join([
            summary.title,
            summary.summary,
            " ".join(summary.key_facts),
        ]).lower()

        earnings_signals = [
            r"\brevenue\b", r"\beps\b", r"\bguidance\b", r"\bquarter\b",
            r"\bq[1-4]\b", r"\bprofit\b", r"\boperating income\b",
        ]
        if summary.category == "earnings":
            has_earnings_signal = any(re.search(p, corpus) for p in earnings_signals)
            if not has_earnings_signal:
                summary.category = "other"

        investment_signals = [
            r"\bearnings\b", r"\brevenue\b", r"\beps\b", r"\bguidance\b",
            r"\bacquisition\b", r"\bmerger\b", r"\binvest\b", r"\bfunding\b",
            r"\bdeal\b", r"\btax\b", r"\bregulat", r"\bfine\b", r"\bbillion\b",
            r"\bmillion\b", r"\bstock\b", r"\bshares\b",
        ]
        summary.cross_ref = any(re.search(p, corpus) for p in investment_signals)

    @staticmethod
    def _has_required_fields(summary: ArticleSummary) -> bool:
        required = (summary.entity, summary.summary, summary.what_happened)
        return all(isinstance(value, str) and bool(value.strip()) for value in required)
