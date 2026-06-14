"""FMP fundamentals — normalize, enrich, and financial health fill-in."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from agents.earnings_models import EarningsFact, EarningsReport, SourceDocument
from agents.financial_health_builder import build_financial_health
from sources.fmp_normalize import extract_fundamentals, match_period
from sources.fundamental_provider import FundamentalProvider
from sources.sec_xbrl_fetcher import SecXbrlFetcher


def _report(**kwargs) -> EarningsReport:
    base = dict(
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
    base.update(kwargs)
    return EarningsReport(**base)


def _mock_fmp_rows() -> MagicMock:
    fmp = MagicMock()
    fmp.income_statement.return_value = [
        {"calendarYear": 2026, "period": "Q1", "revenue": 30_000_000_000},
    ]
    fmp.balance_sheet.return_value = [
        {
            "calendarYear": 2026,
            "period": "Q1",
            "totalDebt": 10_000_000_000,
            "cashAndShortTermInvestments": 5_000_000_000,
            "totalStockholdersEquity": 40_000_000_000,
        },
    ]
    fmp.cash_flow.return_value = [
        {
            "calendarYear": 2026,
            "period": "Q1",
            "operatingCashFlow": 8_000_000_000,
            "capitalExpenditure": -1_000_000_000,
            "freeCashFlow": 7_000_000_000,
        },
    ]
    fmp.ratios.return_value = [
        {
            "calendarYear": 2026,
            "period": "Q1",
            "grossProfitMargin": 0.65,
            "operatingProfitMargin": 0.45,
            "netProfitMargin": 0.40,
            "returnOnEquity": 0.25,
            "debtEquityRatio": 0.3,
        },
    ]
    fmp.key_metrics.return_value = [
        {"calendarYear": 2026, "period": "Q1", "roic": 0.18, "freeCashFlowYield": 0.05},
    ]
    fmp.earnings_surprises.return_value = [
        {
            "date": "2026-04-30",
            "actualEarningResult": 1.2,
            "estimatedEarning": 1.0,
            "surprisePercentage": 20.0,
        },
    ]
    return fmp


def test_match_period_exact():
    rows = [{"calendarYear": 2026, "period": "Q1", "revenue": 1}]
    row, matched = match_period(rows, fiscal_year=2026, fiscal_period="Q1")
    assert matched == "exact"
    assert row["revenue"] == 1


def test_match_period_approx_when_no_match():
    rows = [
        {"calendarYear": 2026, "period": "Q2", "revenue": 2},
        {"calendarYear": 2026, "period": "Q1", "revenue": 1},
    ]
    row, matched = match_period(rows, fiscal_year=2025, fiscal_period="Q4")
    assert matched == "approx"
    assert row["revenue"] == 2


def test_extract_fundamentals_exact_period():
    fmp = _mock_fmp_rows()
    out = extract_fundamentals(
        "NVDA",
        fmp=fmp,
        fiscal_year=2026,
        fiscal_period="Q1",
    )
    assert out["period_matched"] == "exact"
    assert out["ratios"]["gross_margin"] == 65.0
    assert out["cash_flow"]["operating_cf"] == 8_000_000_000
    assert out["cash_flow"]["free_cash_flow"] == 7_000_000_000
    assert out["balance_sheet"]["total_debt"] == 10_000_000_000
    assert out["surprise_history"][0]["eps_actual"] == 1.2


def test_build_financial_health_sec_only_regression():
    report = _report()
    with patch("agents.financial_health_builder._metric") as mock_metric:
        mock_metric.side_effect = lambda _x, _c, metric, _fy, _fp: {
            "operating_cash_flow": 1000.0,
            "capex": 200.0,
        }.get(metric)
        with patch(
            "agents.financial_health_builder._xbrl_metric_for_period",
            return_value=50.0,
        ):
            fh_explicit = build_financial_health(
                report,
                company_facts={},
                xbrl=SecXbrlFetcher(),
                filing_text="",
                fundamentals=None,
            )
            fh_default = build_financial_health(
                report,
                company_facts={},
                xbrl=SecXbrlFetcher(),
                filing_text="",
            )
    assert fh_explicit == fh_default
    assert fh_explicit.fcf == 800.0
    assert fh_explicit.source_conflicts == []


def test_build_financial_health_fmp_fills_missing_fcf():
    report = _report()
    fundamentals = {
        "cash_flow": {"free_cash_flow": 5_000_000_000.0, "fcf_margin": 16.7},
        "ratios": {"roic": 18.0},
    }
    with patch("agents.financial_health_builder._metric", return_value=None):
        fh = build_financial_health(
            report,
            company_facts={},
            xbrl=SecXbrlFetcher(),
            fundamentals=fundamentals,
        )
    assert fh.fcf == 5_000_000_000.0
    assert fh.fcf_conversion_pct == 16.7
    assert "ROIC" in fh.roic_trend


def test_build_financial_health_source_conflict_keeps_sec_headline():
    report = _report()
    fundamentals = {"cash_flow": {"operating_cf": 1200.0, "capex": 200.0}}
    with patch("agents.financial_health_builder._metric") as mock_metric:
        mock_metric.side_effect = lambda _x, _c, metric, _fy, _fp: {
            "operating_cash_flow": 1000.0,
            "capex": 200.0,
        }.get(metric)
        fh = build_financial_health(
            report,
            company_facts={},
            xbrl=SecXbrlFetcher(),
            fundamentals=fundamentals,
        )
    assert fh.fcf == 800.0
    assert len(fh.source_conflicts) == 1
    assert "operating_cash_flow" in fh.source_conflicts[0]


def test_fundamental_provider_off_returns_empty(monkeypatch):
    monkeypatch.setenv("EARNINGS_FUNDAMENTAL_MODE", "off")
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    provider = FundamentalProvider()
    assert provider.enrich_for_report(_report()) == {}


def test_try_fundamental_enrich_returns_none_when_empty(monkeypatch):
    """No fundamentals -> None, so fundamental_enriched_count must not increment."""
    from pipeline import earnings_pipeline as ep

    monkeypatch.setattr(
        "sources.fundamental_provider.FundamentalProvider.enrich_for_report",
        lambda self, report: {},
    )
    _, fundamentals = ep._try_fundamental_enrich(_report())
    assert fundamentals is None


def test_try_fundamental_enrich_returns_dict_when_present(monkeypatch):
    """Non-empty fundamentals -> truthy dict, so the counter increments."""
    from pipeline import earnings_pipeline as ep

    monkeypatch.setattr(
        "sources.fundamental_provider.FundamentalProvider.enrich_for_report",
        lambda self, report: {"fcf": 1.0},
    )
    monkeypatch.setattr(
        "sources.fundamental_provider.attach_fmp_fields_to_report",
        lambda report, fundamentals: report,
    )
    _, fundamentals = ep._try_fundamental_enrich(_report())
    assert fundamentals == {"fcf": 1.0}
