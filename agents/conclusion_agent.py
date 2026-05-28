"""§6 bull/bear conclusion from verified scorecard + insights."""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from agents.earnings_models import EarningsReport
from agents.earnings_v3_models import ConclusionBlock
from llm.gemini_client import GEMINI_MODEL, generate_json, make_client

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL

SYSTEM = """\
Write Traditional Chinese (zh-TW) bull/bear/watch bullets for an earnings report.
Rules:
- Use ONLY facts in the JSON payload (scorecard, segments, call_insights, financial_health, price_reaction, investment_signal).
- If scorecard.eps.accounting_basis is Mixed, do NOT claim EPS beat/miss.
- If headline_verdict is 無法判定, say data basis is insufficient for EPS surprise claims.
- If investment_signal is present, you may reference its rating and conviction to describe overall tilt,
  but MUST note this is a system composite signal, not investment advice.
- If investment_signal.conviction is low, explicitly state that data is insufficient and signal 參考性有限.
- If price_reaction.reaction_label is 利多不漲: bear_case or watch_items must note that
  results beat expectations but the stock did not earn excess returns vs the benchmark
  (priced-in risk). Do not claim causality — describe market reaction only.
- If price_reaction.reaction_label is 利空出盡: bull_case or watch_items may note that
  results missed but the stock held up vs the benchmark (possible sell-the-news reversal).
  Do not claim causality — describe market reaction only.
- All numbers in bull/bear/watch must come from the payload.
- bull_case_zh / bear_case_zh: one sentence each.
- watch_items_zh: up to 3 short bullets.
Output JSON only.
"""


class ConclusionOutput(BaseModel):
    bull_case_zh: str = ""
    bear_case_zh: str = ""
    watch_items_zh: list[str] = Field(default_factory=list)


class ConclusionAgent:
    def __init__(self):
        self._client = None

    def build(self, report: EarningsReport) -> ConclusionBlock:
        payload = {
            "ticker": report.ticker,
            "quarter_label": report.quarter_label,
            "scorecard": report.scorecard.model_dump() if report.scorecard else None,
            "guidance_capex": report.guidance_capex.model_dump() if report.guidance_capex else None,
            "segments": [s.model_dump() for s in report.segments],
            "call_insights": report.call_insights.model_dump() if report.call_insights else None,
            "financial_health": report.financial_health.model_dump() if report.financial_health else None,
            "price_reaction": report.price_reaction.model_dump() if report.price_reaction else None,
            "investment_signal": (
                report.investment_signal.model_dump() if report.investment_signal else None
            ),
            "investment_takeaway_zh": report.investment_takeaway_zh,
            "risk_flags": report.risk_flags,
            "transcript_status": report.transcript_status,
        }
        try:
            data, _ = generate_json(
                self._gemini_client,
                model=MODEL,
                max_output_tokens=1024,
                system_instruction=SYSTEM,
                prompt=json.dumps(payload, ensure_ascii=False, indent=2),
                response_schema=ConclusionOutput,
            )
            out = ConclusionOutput(**data)
            return ConclusionBlock(
                bull_case_zh=out.bull_case_zh.strip(),
                bear_case_zh=out.bear_case_zh.strip(),
                watch_items_zh=[w.strip() for w in out.watch_items_zh[:3] if w.strip()],
            )
        except Exception as exc:
            logger.warning("ConclusionAgent failed for %s: %s", report.ticker, exc)
            return _rule_based_conclusion(report)

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client


def _rule_based_conclusion(report: EarningsReport) -> ConclusionBlock:
    sc = report.scorecard
    verdict = sc.headline_verdict if sc else "無法判定"
    bull = bear = ""
    if verdict == "雙擊":
        bull = "核心指標多數優於共識，短期情緒偏正面。"
        bear = "若宏觀或供應鏈反轉，估值仍可能回調。"
    elif verdict == "雙殺":
        bull = "若下修已充分反映，長線仍看 AI 需求結構性成長。"
        bear = "核心指標低於共識，短期股價承壓風險高。"
    elif verdict == "喜憂參半":
        bull = "部分業務動能仍強，可關注結構性成長分部。"
        bear = "指標分化，需等待更多能見度。"
    else:
        bull = "數據基準不足（如 EPS GAAP/Non-GAAP 未對齊），宜以 SEC 實際值為主。"
        bear = "在驚喜度無法判定前，避免過度解讀 beat/miss 敘事。"

    watch = list(report.risk_flags[:2]) if report.risk_flags else []
    if report.transcript_status == "pending":
        watch.append("電話會議逐字稿完成後再檢視 Q&A 紅旗")
    return ConclusionBlock(bull_case_zh=bull, bear_case_zh=bear, watch_items_zh=watch[:3])
