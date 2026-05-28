"""Investment signal engine — read-only synthesis from report fields."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agents.earnings_models import EarningsFact, EarningsReport, SourceDocument
from agents.earnings_v3_models import (
    EarningsTrend,
    FinancialHealth,
    MetricTrend,
    MetricValue,
    PriceReaction,
    QuarterPoint,
    Scorecard,
    ValuationRatios,
)
from scoring.signal_engine import (
    _saturate,
    build_investment_signal,
)


def _base_report(**updates) -> EarningsReport:
    base = EarningsReport(
        report_id="NVDA_2026_Q1",
        ticker="NVDA",
        company="NVIDIA",
        cik="0001045810",
        fiscal_year=2026,
        fiscal_period="Q1",
        quarter_label="FY2026 Q1",
        published_at=datetime.now(timezone.utc),
        headline_metrics=[
            EarningsFact(metric="revenue", label_zh="營收", value=30e9, source_tag="rev"),
        ],
        source_documents=[SourceDocument(form_type="8-K", filing_url="https://sec.gov/x")],
        confidence="high",
    )
    return base.model_copy(update=updates)


def _bullish_report() -> EarningsReport:
    return _base_report(
        scorecard=Scorecard(
            revenue=MetricValue(surprise_pct=12.0),
            eps=MetricValue(surprise_pct=8.0, accounting_basis="GAAP"),
            headline_verdict="雙擊",
        ),
        trend=EarningsTrend(
            trends=[
                MetricTrend(
                    metric="revenue",
                    yoy_pct=35.0,
                    direction="擴張",
                    points=[QuarterPoint(fiscal_year=2026, fiscal_period="Q1", value=30e9)],
                ),
                MetricTrend(
                    metric="eps_diluted",
                    yoy_pct=45.0,
                    direction="擴張",
                    points=[QuarterPoint(fiscal_year=2026, fiscal_period="Q1", value=5.0)],
                ),
            ],
            quarters_covered=8,
        ),
        price_reaction=PriceReaction(
            excess_5d_pct=6.0,
            excess_1d_pct=4.0,
            reaction_label="確認上漲",
            bench_symbol="SOXX",
        ),
        ratios=ValuationRatios(roic=22.0, fcf_margin=28.0, debt_to_equity=0.4),
        financial_health=FinancialHealth(fcf=7e9, fcf_conversion_pct=23.0),
    )


def test_saturate_boundaries():
    assert _saturate(0.0, 10.0, center=0.0) == pytest.approx(50.0)
    assert _saturate(10.0, 10.0, center=0.0) == pytest.approx(100.0)
    assert _saturate(-10.0, 10.0, center=0.0) == pytest.approx(0.0)
    assert _saturate(999.0, 10.0, center=0.0) == pytest.approx(100.0)
    assert _saturate(-999.0, 10.0, center=0.0) == pytest.approx(0.0)


def test_full_factors_bullish_high_conviction():
    sig = build_investment_signal(_bullish_report())
    assert sig.score is not None and sig.score >= 75
    assert sig.rating in {"強力看多", "看多"}
    assert sig.conviction == "high"
    assert len([f for f in sig.factors if f.available]) == 4


def test_missing_market_and_quality_redistributes_weights():
    report = _bullish_report().model_copy(update={"price_reaction": None, "ratios": None})
    sig = build_investment_signal(report)
    avail = [f for f in sig.factors if f.available]
    assert len(avail) == 2
    assert sig.conviction in {"medium", "low"}
    total_w = sum(f.weight for f in sig.factors if f.available)
    assert total_w == pytest.approx(1.0, abs=1e-6)
    for f in sig.factors:
        if not f.available:
            assert f.weight == 0.0


def test_low_conviction_caps_strong_rating():
    report = _base_report(
        scorecard=Scorecard(
            revenue=MetricValue(surprise_pct=20.0),
            headline_verdict="雙擊",
        ),
    )
    sig = build_investment_signal(report)
    assert sig.conviction == "low"
    assert sig.score is not None and sig.score >= 75
    assert sig.rating == "看多"
    assert sig.rating != "強力看多"


def test_all_factors_missing_insufficient_data():
    sig = build_investment_signal(_base_report())
    assert sig.rating == "資料不足"
    assert sig.score is None
    assert sig.conviction == "low"


def test_weight_redistribution_sums_to_one():
    report = _bullish_report().model_copy(update={"ratios": None})
    sig = build_investment_signal(report)
    total = sum(f.weight for f in sig.factors if f.available)
    assert total == pytest.approx(1.0, abs=1e-6)


def test_example_bullish_signal_output():
    sig = build_investment_signal(_bullish_report())
    assert sig.model_dump() == sig.model_dump()  # smoke serialize
    assert sig.score is not None
    assert sig.rating in {"強力看多", "看多"}
    assert sig.conviction == "high"
    names = {f.name: f.score for f in sig.factors if f.available}
    assert set(names) == {
        "fundamental_momentum",
        "surprise",
        "market_confirmation",
        "quality",
    }
