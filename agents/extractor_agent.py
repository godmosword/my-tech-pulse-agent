"""Layer 1 agent: per-article structured summary with confidence scoring."""

import json
import logging
import os
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"

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
- summary: 2–3 sentence factual summary, no editorializing (string)
- category: one of ["product_launch", "funding", "acquisition", "earnings", "regulation", "research", "other"]
- key_facts: list of up to 5 specific factual claims (list of strings)
- sentiment: one of ["positive", "negative", "neutral"]
- confidence: one of ["high", "medium", "low"]
- cross_ref: true if this story is likely relevant to investment decisions (bool)

Article title: {title}
Article source: {source}
Article text:
{text}
"""


class ArticleSummary(BaseModel):
    entity: str
    summary: str
    category: Literal["product_launch", "funding", "acquisition", "earnings", "regulation", "research", "other"]
    key_facts: list[str] = Field(default_factory=list)
    sentiment: Literal["positive", "negative", "neutral"]
    confidence: Literal["high", "medium", "low"]
    cross_ref: bool = False
    source_url: str = ""
    source_name: str = ""


class ExtractorAgent:
    """Wraps the Claude API for per-article structured extraction."""

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

    def extract(self, title: str, text: str, source_name: str = "", source_url: str = "") -> Optional[ArticleSummary]:
        prompt = EXTRACTION_PROMPT.format(
            title=title,
            source=source_name,
            text=text[:4000],
        )
        try:
            message = self._client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            data = json.loads(raw)
            summary = ArticleSummary(**data)
            summary.source_url = source_url
            summary.source_name = source_name
            return summary

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error from extractor: %s | raw=%s", exc, raw[:200])
            return None
        except Exception as exc:
            logger.error("Extractor agent failed for '%s': %s", title, exc)
            return None

    def extract_batch(self, articles: list[dict]) -> list[ArticleSummary]:
        results = []
        for article in articles:
            text = article.get("content") or article.get("summary", "")
            result = self.extract(
                title=article.get("title", ""),
                text=text,
                source_name=article.get("source", ""),
                source_url=article.get("url", ""),
            )
            if result:
                results.append(result)
        return results
