"""Tests for multi-quarter XBRL series and earnings trend builder."""

from __future__ import annotations

import json
from pathlib import Path

from agents.scorecard_builder import compute_yoy_pct
from agents.trend_builder import build_earnings_trend, build_metric_trend
from sources.sec_xbrl_fetcher import SecXbrlFetcher

FIXTURE = Path(__file__).parent / "fixtures" / "sec_companyfacts_nvda_sample.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _revenue_rows_in_fixture(data: dict) -> int:
    rev = data["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    return sum(1 for r in rev if r.get("val") is not None and str(r.get("fp", "")).upper() in {"Q1", "Q2", "Q3", "Q4"})


def test_normalize_quarter_series_order_and_count():
    data = _load_fixture()
    fetcher = SecXbrlFetcher()
    series = fetcher.normalize_quarter_series(data, max_quarters=8)
    rev_rows = series["revenue"]
    expected = min(_revenue_rows_in_fixture(data), 8)
    assert len(rev_rows) == expected
    ends = [str(r.get("end") or "") for r in rev_rows]
    assert ends == sorted(ends)
    filed_pairs = [(str(r.get("end") or ""), str(r.get("filed") or "")) for r in rev_rows]
    assert filed_pairs == sorted(filed_pairs)


def test_build_earnings_trend_yoy_matches_hand_calc():
    data = _load_fixture()
    trend = build_earnings_trend(SecXbrlFetcher(), data, max_quarters=8)
    rev = next(t for t in trend.trends if t.metric == "revenue")
    latest = rev.points[-1]
    prior_y = next(
        p for p in rev.points
        if p.fiscal_year == latest.fiscal_year - 1 and p.fiscal_period == latest.fiscal_period
    )
    assert latest.value is not None and prior_y.value is not None
    expected_yoy = compute_yoy_pct(latest.value, prior_y.value)
    assert rev.yoy_pct == expected_yoy


def test_build_earnings_trend_qoq_matches_hand_calc():
    data = _load_fixture()
    trend = build_earnings_trend(SecXbrlFetcher(), data, max_quarters=8)
    rev = next(t for t in trend.trends if t.metric == "revenue")
    latest, prev = rev.points[-1], rev.points[-2]
    assert latest.value is not None and prev.value is not None
    expected_qoq = compute_yoy_pct(latest.value, prev.value)
    assert rev.qoq_pct == expected_qoq


def test_build_earnings_trend_direction_expansion():
    data = _load_fixture()
    trend = build_earnings_trend(SecXbrlFetcher(), data, max_quarters=8)
    rev = next(t for t in trend.trends if t.metric == "revenue")
    assert rev.direction == "擴張"


def test_gross_margin_trend_value():
    data = _load_fixture()
    fetcher = SecXbrlFetcher()
    series = fetcher.normalize_quarter_series(data, max_quarters=8)
    trend = build_earnings_trend(fetcher, data, max_quarters=8)
    gm = next(t for t in trend.trends if t.metric == "gross_margin")
    latest_end = gm.points[-1].period_end
    gp_row = next(r for r in series["gross_profit"] if str(r.get("end")) == latest_end)
    rev_row = next(r for r in series["revenue"] if str(r.get("end")) == latest_end)
    expected = round(float(gp_row["val"]) / float(rev_row["val"]) * 100.0, 2)
    assert gm.points[-1].value is not None
    assert abs(gm.points[-1].value - expected) < 0.01


def test_normalize_latest_quarter_facts_regression_unchanged():
    data = _load_fixture()
    fetcher = SecXbrlFetcher()
    normalized = fetcher.normalize_latest_quarter_facts(data)
    assert normalized is not None
    period_meta, facts = normalized
    assert period_meta["fiscal_period"] == "Q3"
    assert period_meta["fiscal_year"] == 2025
    assert str(period_meta["period_end"]).startswith("2024-10-27")
    metrics = {row["metric"] for row in facts}
    assert "revenue" in metrics
    assert "eps_diluted" in metrics


def test_build_metric_trend_from_rows():
    data = _load_fixture()
    rows = SecXbrlFetcher().normalize_quarter_series(data)["revenue"]
    mt = build_metric_trend("revenue", rows[0]["label_zh"], rows)
    assert len(mt.points) == len(rows)
    assert mt.label_zh == "營收"
