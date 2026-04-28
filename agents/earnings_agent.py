"""Earnings fact-extraction agent with fact_guard enforcement.

fact_guard rule: numeric fields in earnings JSON must be parsed directly from
structured source data — the LLM must never calculate or infer numbers.
"""

import json
import logging
import os
import re
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field, field_validator

from sources.earnings_fetcher import EarningsFiling

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """\
You are a financial data extractor specializing in earnings filings.

CRITICAL RULES — fact_guard enforcement:
1. Only extract numbers that are EXPLICITLY STATED in the provided filing text.
2. Never calculate, derive, or infer numeric values. If a number is not in the text, use null.
3. beat_pct must only be populated if the text explicitly states an analyst estimate AND actual result.
4. Do not round or reformat numbers — copy them exactly as they appear.
5. key_quotes must be verbatim quotes from the filing, not paraphrases.
6. Output valid JSON only. No markdown, no explanation.
"""

EXTRACTION_PROMPT = """\
Extract earnings data from the filing text below.

Return a JSON object with EXACTLY these fields:
{{
  "company": "string",
  "quarter": "string (e.g. Q1 FY2026)",
  "revenue": {{"actual": number_or_null, "estimate": number_or_null, "beat_pct": number_or_null}},
  "eps": {{"actual": number_or_null, "estimate": number_or_null}},
  "segments": {{}},
  "guidance_next_q": number_or_null,
  "key_quotes": [],
  "source": "SEC {form_type}",
  "confidence": "high | medium | low"
}}

Company: {company}
Form type: {form_type}
Filing text:
{text}
"""


class RevenueData(BaseModel):
    actual: Optional[float] = None
    estimate: Optional[float] = None
    beat_pct: Optional[float] = None


class EPSData(BaseModel):
    actual: Optional[float] = None
    estimate: Optional[float] = None


class EarningsOutput(BaseModel):
    company: str
    quarter: str
    revenue: RevenueData = Field(default_factory=RevenueData)
    eps: EPSData = Field(default_factory=EPSData)
    segments: dict[str, Optional[float]] = Field(default_factory=dict)
    guidance_next_q: Optional[float] = None
    key_quotes: list[str] = Field(default_factory=list)
    source: str
    confidence: Literal["high", "medium", "low"]
    cross_ref: bool = True  # earnings always relevant to investment digest

    @field_validator("key_quotes")
    @classmethod
    def limit_quotes(cls, v: list[str]) -> list[str]:
        return v[:5]


class EarningsAgent:
    """Extracts structured earnings facts from raw filing text."""

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

    def extract(self, filing: EarningsFiling) -> Optional[EarningsOutput]:
        if not filing.raw_text:
            logger.warning("No raw text for filing: %s %s", filing.company, filing.form_type)
            return None

        prompt = EXTRACTION_PROMPT.format(
            company=filing.company,
            form_type=filing.form_type,
            text=filing.raw_text[:6000],
        )

        try:
            message = self._client.messages.create(
                model=MODEL,
                max_tokens=1536,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            data = json.loads(raw)
            output = EarningsOutput(**data)
            self._fact_guard_check(output, filing.raw_text)
            return output

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error from earnings agent: %s | raw=%s", exc, raw[:200])
            return None
        except Exception as exc:
            logger.error("Earnings agent failed for %s: %s", filing.company, exc)
            return None

    def _fact_guard_check(self, output: EarningsOutput, source_text: str) -> None:
        """Warn if extracted numbers cannot be found verbatim in source text."""
        def check_value(field_name: str, value: Optional[float]) -> None:
            if value is None:
                return
            value_str = str(value)
            # Allow for common formatting variants (commas, B/M suffixes omitted)
            stripped = re.sub(r"[,\s]", "", value_str)
            if stripped not in re.sub(r"[,\s]", "", source_text):
                logger.warning(
                    "fact_guard: %s value %s not found verbatim in source for %s",
                    field_name, value, output.company
                )

        check_value("revenue.actual", output.revenue.actual)
        check_value("eps.actual", output.eps.actual)
        check_value("guidance_next_q", output.guidance_next_q)
