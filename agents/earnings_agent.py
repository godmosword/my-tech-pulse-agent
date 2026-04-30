"""Earnings fact-extraction agent with fact_guard enforcement.

fact_guard rule: numeric fields in earnings JSON must be parsed directly from
structured source data — the LLM must never calculate or infer numbers.
"""

import json
import logging
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from llm.gemini_client import GEMINI_MODEL, generate_json, make_client
from sources.earnings_fetcher import EarningsFiling

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL

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
        self._client = None

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
            data, raw = generate_json(
                self._gemini_client,
                model=MODEL,
                max_output_tokens=1536,
                system_instruction=SYSTEM_PROMPT,
                prompt=prompt,
                response_schema=EarningsOutput,
            )
            output = EarningsOutput(**data)
            output = self._fact_guard_apply(output, filing.raw_text)
            return output

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error from earnings agent: %s", exc)
            return None
        except Exception as exc:
            logger.error("Earnings agent failed for %s: %s", filing.company, exc)
            return None

    def _fact_guard_apply(self, output: EarningsOutput, source_text: str) -> EarningsOutput:
        """Enforce fact_guard: null out unverifiable numeric fields and downgrade confidence.

        Any numeric field whose value cannot be found in the source text is cleared to None.
        If any violations are found, confidence is downgraded to "low".
        beat_pct is cleared whenever revenue.actual or revenue.estimate is absent.
        """
        clean_source = re.sub(r"[$,\s]", "", source_text)
        violations: list[str] = []

        def _in_source(value: float) -> bool:
            for fmt in (str(value), f"{value:.1f}", f"{value:.2f}", str(int(value))):
                if re.sub(r"[$,\s]", "", fmt) in clean_source:
                    return True
            return False

        def _check_and_clear(field_name: str, value: Optional[float]) -> Optional[float]:
            if value is not None and not _in_source(value):
                violations.append(field_name)
                return None
            return value

        output.revenue.actual = _check_and_clear("revenue.actual", output.revenue.actual)
        output.revenue.estimate = _check_and_clear("revenue.estimate", output.revenue.estimate)
        output.eps.actual = _check_and_clear("eps.actual", output.eps.actual)
        output.eps.estimate = _check_and_clear("eps.estimate", output.eps.estimate)
        output.guidance_next_q = _check_and_clear("guidance_next_q", output.guidance_next_q)

        # beat_pct is only valid when both actual and estimate are present
        if output.revenue.beat_pct is not None:
            if output.revenue.actual is None or output.revenue.estimate is None:
                violations.append("revenue.beat_pct (missing actual/estimate)")
                output.revenue.beat_pct = None

        # Validate segments
        for seg_name in list(output.segments.keys()):
            val = output.segments[seg_name]
            if val is not None and not _in_source(val):
                violations.append(f"segments.{seg_name}")
                output.segments[seg_name] = None

        if violations:
            logger.warning(
                "fact_guard cleared %d field(s) for %s: %s — confidence downgraded to low",
                len(violations), output.company, violations,
            )
            output.confidence = "low"

        return output

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client
