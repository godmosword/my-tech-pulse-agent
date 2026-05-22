"""Scorecard builder — basis alignment and surprise rules."""

from datetime import datetime, timezone

from agents.earnings_models import EarningsFact, EarningsReport, SourceDocument
from agents.scorecard_builder import (
    align_basis,
    build_scorecard,
    compute_surprise_pct,
)
from sources.sec_xbrl_fetcher import SecXbrlFetcher


def _report(headline: list[EarningsFact]) -> EarningsReport:
    return EarningsReport(
        report_id="NVDA_2026_Q1",
        ticker="NVDA",
        company="NVIDIA",
        cik="0001045810",
        fiscal_year=2026,
        fiscal_period="Q1",
        quarter_label="FY2026 Q1",
        published_at=datetime.now(timezone.utc),
        headline_metrics=headline,
        source_documents=[SourceDocument(form_type="8-K", filing_url="https://sec.gov/x")],
        confidence="high",
    )


def test_align_basis_mixed_for_gaap_vs_non_gaap():
    assert align_basis("GAAP", "Non-GAAP") == "Mixed"
    assert align_basis("GAAP", "GAAP") == "GAAP"


def test_compute_surprise_pct():
    assert compute_surprise_pct(110.0, 100.0) == 10.0


def test_eps_mixed_when_gaap_actual_and_non_gaap_estimate():
    report = _report(
        [
            EarningsFact(metric="revenue", label_zh="營收", value=30e9, source_tag="rev"),
            EarningsFact(
                metric="eps_diluted",
                label_zh="EPS",
                value=4.0,
                unit="USD/share",
                source_tag="eps",
            ),
        ]
    )
    scorecard = build_scorecard(
        report,
        company_facts={},
        xbrl=SecXbrlFetcher(),
        filing_text="",
        vendor_estimates={"eps": {"value": 5.0, "basis": "Non-GAAP"}},
    )
    assert scorecard.eps is not None
    assert scorecard.eps.accounting_basis == "Mixed"
    assert scorecard.eps.surprise_pct is None
    assert scorecard.headline_verdict == "無法判定"


def test_eps_surprise_when_non_gaap_actual_from_filing():
    text = (
        "NVIDIA announced non-GAAP diluted EPS of $5.25 for the quarter, "
        "compared with analyst expectations."
    )
    report = _report(
        [
            EarningsFact(
                metric="eps_diluted",
                label_zh="EPS",
                value=4.0,
                unit="USD/share",
                source_tag="eps",
            ),
        ]
    )
    scorecard = build_scorecard(
        report,
        company_facts={},
        xbrl=SecXbrlFetcher(),
        filing_text=text,
        vendor_estimates={"eps": {"value": 5.0, "basis": "Non-GAAP"}},
    )
    assert scorecard.eps is not None
    assert scorecard.eps.actual == 5.25
    assert scorecard.eps.actual_source == "8-K Text"
    assert scorecard.eps.accounting_basis == "Non-GAAP"
    assert scorecard.eps.surprise_pct == 5.0
