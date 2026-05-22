"""earnings_v3 additive models — scorecard, market context, transcript state."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

AccountingBasis = Literal["GAAP", "Non-GAAP", "Mixed", "Unknown"]
ActualSource = Literal["XBRL", "8-K Text", "Vendor", "Unknown"]
EstimateSource = Literal["Vendor", "Unknown"]
HeadlineVerdict = Literal["雙擊", "雙殺", "喜憂參半", "無法判定"]
EarningsSession = Literal["pre", "post", "unknown"]
TranscriptStatus = Literal["pending", "ready", "skipped", "timeout"]


class MetricValue(BaseModel):
    actual: Optional[float] = None
    estimate: Optional[float] = None
    surprise_pct: Optional[float] = None
    yoy_pct: Optional[float] = None
    accounting_basis: AccountingBasis = "Unknown"
    actual_source: ActualSource = "Unknown"
    estimate_source: EstimateSource = "Unknown"


class Scorecard(BaseModel):
    revenue: Optional[MetricValue] = None
    eps: Optional[MetricValue] = None
    gross_margin_pct: Optional[MetricValue] = None
    headline_verdict: HeadlineVerdict = "無法判定"


class MarketContext(BaseModel):
    report_generated_at: datetime
    price_usd: Optional[float] = None
    earnings_date: Optional[str] = None
    session: EarningsSession = "unknown"


class CallInsights(BaseModel):
    highlights: list[str] = Field(default_factory=list)
    qa_red_flags: list[str] = Field(default_factory=list)
