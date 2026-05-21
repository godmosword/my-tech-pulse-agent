"""Extract narrative-only fields from earnings filings (no numeric facts)."""

from __future__ import annotations

import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from agents.earnings_fact_guard import apply_fact_guard_v2, verify_quote_substring
from agents.earnings_models import EarningsReport
from llm.gemini_client import GEMINI_MODEL, generate_json, make_client
from sources.earnings_fetcher import EarningsFiling

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL

SYSTEM_PROMPT = """\
You extract narrative content from SEC earnings filings for tech / semiconductor investors.

CRITICAL — fact_guard:
- Do NOT output revenue, EPS, margins, or any numeric financial results.
- key_quotes must be verbatim substrings from the filing text (copy exactly).
- guidance_wording must paraphrase only what is explicitly stated about forward guidance.
- management_tone: one short phrase (e.g. cautious, optimistic, mixed).
- ai_infra_narrative: optional English note on datacenter/GPU/HBM/cloud/capex themes if stated.

Output valid JSON only.
"""

EXTRACTION_PROMPT = """\
Company: {company} ({ticker})
Form: {form_type}

Return JSON:
{{
  "key_quotes": ["verbatim quote 1", ...],
  "guidance_wording": "string or null",
  "management_tone": "string or null",
  "ai_infra_narrative": "string or null"
}}

Filing text:
{text}
"""


class EarningsNarrativeOutput(BaseModel):
    key_quotes: list[str] = Field(default_factory=list)
    guidance_wording: Optional[str] = None
    management_tone: Optional[str] = None
    ai_infra_narrative: Optional[str] = None

    @field_validator("key_quotes")
    @classmethod
    def limit_quotes(cls, v: list[str]) -> list[str]:
        return v[:5]


class EarningsNarrativeExtractor:
    def __init__(self):
        self._client = None

    def enrich_report(
        self,
        report: EarningsReport,
        filing: EarningsFiling,
    ) -> EarningsReport:
        if not filing.raw_text:
            return report
        narrative = self._extract(filing)
        if not narrative:
            return report

        guidance = report.guidance.copy()
        if narrative.guidance_wording:
            guidance["wording"] = narrative.guidance_wording

        updated = report.model_copy(
            update={
                "key_quotes": narrative.key_quotes,
                "management_tone": narrative.management_tone,
                "guidance": guidance,
                "ai_infra_relevance": narrative.ai_infra_narrative or report.ai_infra_relevance,
            }
        )
        return apply_fact_guard_v2(updated, filing_text=filing.raw_text)

    def _extract(self, filing: EarningsFiling) -> Optional[EarningsNarrativeOutput]:
        ticker = filing.ticker or filing.company
        prompt = EXTRACTION_PROMPT.format(
            company=filing.company,
            ticker=ticker,
            form_type=filing.form_type,
            text=filing.raw_text[:6000],
        )
        try:
            data, _raw = generate_json(
                self._gemini_client,
                model=MODEL,
                max_output_tokens=1024,
                system_instruction=SYSTEM_PROMPT,
                prompt=prompt,
                response_schema=EarningsNarrativeOutput,
            )
            out = EarningsNarrativeOutput(**data)
            verified_quotes = [
                q for q in out.key_quotes if verify_quote_substring(q, filing.raw_text or "")
            ]
            out = out.model_copy(update={"key_quotes": verified_quotes})
            return out
        except Exception as exc:
            logger.warning("Narrative extract failed for %s: %s", filing.company, exc)
            return None

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client
