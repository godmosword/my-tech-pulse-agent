"""Tests for earnings_v2 fact_guard."""

from datetime import datetime, timezone

from agents.earnings_fact_guard import apply_fact_guard_v2, verify_quote_substring
from agents.earnings_models import EarningsFact, EarningsReport, SourceDocument


def _sample_report(**kwargs) -> EarningsReport:
    base = dict(
        report_id="NVDA_2026_FY2026Q1",
        ticker="NVDA",
        company="NVIDIA",
        cik="0001045810",
        fiscal_year=2026,
        fiscal_period="FY2026Q1",
        quarter_label="FY2026 FY2026Q1",
        published_at=datetime.now(timezone.utc),
        headline_metrics=[
            EarningsFact(
                metric="revenue",
                label_zh="營收",
                value=30_000_000_000,
                source_type="sec_xbrl",
                source_tag="us-gaap:Revenues",
            )
        ],
        key_quotes=["Data center revenue grew 50 percent year over year."],
        source_documents=[
            SourceDocument(form_type="10-Q", filing_url="https://sec.gov/example")
        ],
        confidence="high",
    )
    base.update(kwargs)
    return EarningsReport(**base)


def test_fact_guard_v2_clears_fake_quote():
    src = "Data center revenue grew 50 percent year over year."
    report = _sample_report(key_quotes=["This quote was invented by the model entirely."])
    out = apply_fact_guard_v2(report, filing_text=src)
    assert out.key_quotes == []
    assert out.confidence == "low"


def test_fact_guard_v2_keeps_verified_quote():
    src = "Data center revenue grew 50 percent year over year."
    report = _sample_report()
    out = apply_fact_guard_v2(report, filing_text=src)
    assert len(out.key_quotes) == 1
    assert out.confidence == "high"


def test_fact_guard_v2_strips_headline_without_source_tag():
    bad = EarningsFact(metric="revenue", label_zh="營收", value=1.0, source_type="sec_xbrl", source_tag="")
    report = _sample_report(headline_metrics=[bad])
    out = apply_fact_guard_v2(report)
    assert out.headline_metrics == []
    assert out.confidence == "low"


def test_verify_quote_substring():
    assert verify_quote_substring("revenue grew 50 percent", "We said revenue grew 50 percent in the quarter.")
