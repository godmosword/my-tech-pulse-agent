"""Structured earnings report models (earnings_v2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from agents.earnings_agent import EarningsOutput, EPSData, RevenueData
from agents.earnings_v3_models import (
    CallInsights,
    ConclusionBlock,
    EarningsTrend,
    FinancialHealth,
    GuidanceCapex,
    MarketContext,
    Scorecard,
    SegmentRow,
    TranscriptStatus,
)

AiInfraSignal = Literal["strong", "medium", "weak", "not_relevant"]
MarketSurpriseLevel = Literal["high", "medium", "low", "unknown"]


class EarningsFact(BaseModel):
    metric: str
    label_zh: str
    value: float
    unit: str = "USD"
    period: str = ""
    fiscal_year: Optional[int] = None
    fiscal_period: str = ""
    form_type: Optional[str] = None
    source_type: str = "sec_xbrl"
    source_url: str = ""
    source_tag: str = ""
    confidence: Literal["high", "medium", "low"] = "high"


class SourceDocument(BaseModel):
    form_type: str
    filing_url: str
    accession: Optional[str] = None
    filed_at: Optional[datetime] = None


class EarningsReport(BaseModel):
    report_id: str
    ticker: str
    company: str
    cik: str
    tier: Optional[int] = None
    fiscal_year: Optional[int] = None
    fiscal_period: str
    period_end: Optional[datetime] = None
    quarter_label: str
    published_at: datetime
    filed_at: Optional[datetime] = None
    headline_metrics: list[EarningsFact] = Field(default_factory=list)
    segment_metrics: list[EarningsFact] = Field(default_factory=list)
    guidance: dict[str, Any] = Field(default_factory=dict)
    estimates: dict[str, Any] = Field(default_factory=dict)
    surprise: dict[str, Any] = Field(default_factory=dict)
    key_quotes: list[str] = Field(default_factory=list)
    management_tone: Optional[str] = None
    ai_infra_relevance: Optional[str] = None
    investment_takeaway_zh: Optional[str] = None
    risk_flags: list[str] = Field(default_factory=list)
    ai_infra_signal: AiInfraSignal = "not_relevant"
    earnings_quality_score: Optional[float] = None
    market_surprise_level: MarketSurpriseLevel = "unknown"
    source_documents: list[SourceDocument] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    schema_version: str = "earnings_v2"
    # earnings_v3 (additive)
    scorecard: Scorecard | None = None
    market_context: MarketContext | None = None
    rendered_markdown_zh: str | None = None
    transcript_status: TranscriptStatus | None = None
    transcript_id: str | None = None
    guidance_capex: GuidanceCapex | None = None
    segments: list[SegmentRow] = Field(default_factory=list)
    call_insights: CallInsights | None = None
    financial_health: FinancialHealth | None = None
    conclusion: ConclusionBlock | None = None
    trend: EarningsTrend | None = None


def _metric_value(metrics: list[EarningsFact], name: str) -> Optional[float]:
    for m in metrics:
        if m.metric == name:
            return m.value
    return None


def report_to_legacy_output(report: EarningsReport) -> EarningsOutput:
    """Map v2 report to legacy EarningsOutput for Telegram / memory compat."""
    rev_raw = _metric_value(report.headline_metrics, "revenue")
    rev = (rev_raw / 1e9) if rev_raw is not None and rev_raw > 1e6 else rev_raw
    eps = _metric_value(report.headline_metrics, "eps_diluted") or _metric_value(
        report.headline_metrics, "eps_basic"
    )
    source = report.source_documents[0].form_type if report.source_documents else "SEC"
    return EarningsOutput(
        company=report.company,
        quarter=report.quarter_label,
        revenue=RevenueData(actual=rev),
        eps=EPSData(actual=eps),
        key_quotes=report.key_quotes[:5],
        source=f"SEC {source}",
        confidence=report.confidence,
        cross_ref=True,
    )


def build_report_id(ticker: str, fiscal_year: int | None, fiscal_period: str) -> str:
    fy = fiscal_year if fiscal_year is not None else "unknown"
    fp = fiscal_period or "unknown"
    return f"{ticker.upper()}_{fy}_{fp}"


def quarter_label_zh(fiscal_year: int | None, fiscal_period: str, period_end: str | None) -> str:
    fy = f"FY{fiscal_year}" if fiscal_year else "FY?"
    end = f"（至 {period_end}）" if period_end else ""
    return f"{fy} {fiscal_period}{end}"
