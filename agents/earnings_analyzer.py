"""Produce Traditional Chinese investment analysis from verified earnings facts."""

from __future__ import annotations

import json
import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field

from agents.earnings_models import EarningsReport
from llm.gemini_client import GEMINI_MODEL, generate_json, make_client

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL

SYSTEM_PROMPT = """\
You are a semiconductor / AI infrastructure earnings analyst writing for Traditional Chinese (zh-TW) investors.

Rules:
- Use ONLY the verified numeric facts provided in headline_metrics — never invent or recalculate numbers.
- If a metric is missing, say it is not disclosed; do not guess.
- investment_takeaway_zh: one sentence conclusion (<= 80 Chinese characters preferred).
- risk_flags: up to 4 short zh-TW bullets.
- ai_infra_signal: one of strong | medium | weak | not_relevant
- market_surprise_level: high | medium | low | unknown (unknown if no estimate/surprise data)
- earnings_quality_score: 0-10 float reflecting revenue/EPS/guidance quality vs expectations when data allows; else null

Output valid JSON only.
"""


class EarningsAnalysisOutput(BaseModel):
    investment_takeaway_zh: str = ""
    ai_infra_relevance: str = ""
    ai_infra_signal: Literal["strong", "medium", "weak", "not_relevant"] = "not_relevant"
    risk_flags: list[str] = Field(default_factory=list)
    earnings_quality_score: Optional[float] = None
    market_surprise_level: Literal["high", "medium", "low", "unknown"] = "unknown"


class EarningsAnalyzer:
    def __init__(self):
        self._client = None

    def analyze(self, report: EarningsReport) -> EarningsReport:
        if not report.headline_metrics:
            return report
        payload = {
            "ticker": report.ticker,
            "company": report.company,
            "quarter_label": report.quarter_label,
            "headline_metrics": [m.model_dump() for m in report.headline_metrics],
            "scorecard": report.scorecard.model_dump() if report.scorecard else None,
            "guidance": report.guidance,
            "guidance_capex": report.guidance_capex.model_dump() if report.guidance_capex else None,
            "estimates": report.estimates,
            "surprise": report.surprise,
            "key_quotes": report.key_quotes,
            "management_tone": report.management_tone,
            "transcript_status": report.transcript_status,
        }
        prompt = (
            "Analyze this earnings report and return JSON matching the schema.\n\n"
            f"Verified data:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
        try:
            data, _raw = generate_json(
                self._gemini_client,
                model=MODEL,
                max_output_tokens=1024,
                system_instruction=SYSTEM_PROMPT,
                prompt=prompt,
                response_schema=EarningsAnalysisOutput,
            )
            analysis = EarningsAnalysisOutput(**data)
            return report.model_copy(
                update={
                    "investment_takeaway_zh": analysis.investment_takeaway_zh or report.investment_takeaway_zh,
                    "ai_infra_relevance": analysis.ai_infra_relevance or report.ai_infra_relevance,
                    "ai_infra_signal": analysis.ai_infra_signal,
                    "risk_flags": analysis.risk_flags[:4],
                    "earnings_quality_score": analysis.earnings_quality_score,
                    "market_surprise_level": analysis.market_surprise_level,
                }
            )
        except Exception as exc:
            logger.warning("Earnings analysis failed for %s: %s", report.ticker, exc)
            return report

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client
