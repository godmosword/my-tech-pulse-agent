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


class SegmentRow(BaseModel):
    name_zh: str
    revenue: Optional[float] = None
    yoy_pct: Optional[float] = None
    driver_zh: str = ""


class GuidanceCapex(BaseModel):
    next_q_revenue_low: Optional[float] = None
    next_q_revenue_high: Optional[float] = None
    vs_consensus_note: str = ""
    capex_amount: Optional[float] = None
    capex_focus_zh: str = ""
    outlook_tone: Literal["樂觀", "謹慎", "悲觀", "未知"] = "未知"


class FinancialHealth(BaseModel):
    fcf: Optional[float] = None
    fcf_conversion_pct: Optional[float] = None
    roic_trend: str = "資料不足"
    shareholder_returns_zh: str = ""
    source_conflicts: list[str] = Field(default_factory=list)


class ValuationRatios(BaseModel):
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    roic: Optional[float] = None
    debt_to_equity: Optional[float] = None
    fcf_margin: Optional[float] = None
    source: str = "fmp"
    period_matched: str = "none"


class SurprisePoint(BaseModel):
    period: str
    eps_actual: Optional[float] = None
    eps_estimate: Optional[float] = None
    surprise_pct: Optional[float] = None


class ConclusionBlock(BaseModel):
    bull_case_zh: str = ""
    bear_case_zh: str = ""
    watch_items_zh: list[str] = Field(default_factory=list)




class QuarterPoint(BaseModel):
    fiscal_year: int
    fiscal_period: str
    period_end: Optional[str] = None
    value: Optional[float] = None
    filed: Optional[str] = None


class MetricTrend(BaseModel):
    metric: str
    label_zh: str = ""
    points: list[QuarterPoint] = Field(default_factory=list)
    yoy_pct: Optional[float] = None
    qoq_pct: Optional[float] = None
    direction: Literal["擴張", "收縮", "持平", "資料不足"] = "資料不足"


class EarningsTrend(BaseModel):
    trends: list[MetricTrend] = Field(default_factory=list)
    quarters_covered: int = 0


class PriceReaction(BaseModel):
    earnings_date: Optional[str] = None
    session: str = "unknown"
    ref_close: Optional[float] = None
    ret_1d_pct: Optional[float] = None
    ret_5d_pct: Optional[float] = None
    bench_symbol: str = "SOXX"
    bench_ret_1d_pct: Optional[float] = None
    bench_ret_5d_pct: Optional[float] = None
    excess_1d_pct: Optional[float] = None
    excess_5d_pct: Optional[float] = None
    reaction_label: Literal[
        "確認上漲", "利多不漲", "利空出盡", "確認下跌", "中性", "資料不足"
    ] = "資料不足"
    degraded: bool = False
    notes: list[str] = Field(default_factory=list)


class SignalFactor(BaseModel):
    name: str
    score: Optional[float] = None
    weight: float = 0.0
    detail_zh: str = ""
    available: bool = False


InvestmentSignalRating = Literal[
    "強力看多", "看多", "中性", "看空", "強力看空", "資料不足"
]
InvestmentSignalConviction = Literal["high", "medium", "low"]


class InvestmentSignal(BaseModel):
    score: Optional[float] = None
    rating: InvestmentSignalRating = "資料不足"
    conviction: InvestmentSignalConviction = "low"
    factors: list[SignalFactor] = Field(default_factory=list)
    rationale_zh: str = ""
    as_of: Optional[str] = None
