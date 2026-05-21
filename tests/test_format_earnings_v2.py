"""Telegram formatter tests for earnings_v2."""

from datetime import datetime, timezone

from agents.earnings_models import EarningsFact, EarningsReport, SourceDocument
from delivery.message_formatter import format_earnings_v2


def _report() -> EarningsReport:
    return EarningsReport(
        report_id="NVDA_2026_FY2026Q1",
        ticker="NVDA",
        company="NVIDIA Corporation",
        cik="0001045810",
        tier=1,
        fiscal_year=2026,
        fiscal_period="FY2026Q1",
        quarter_label="FY2026 Q1",
        published_at=datetime.now(timezone.utc),
        investment_takeaway_zh="AI 基建需求仍強，但需留意供應鏈瓶頸。",
        headline_metrics=[
            EarningsFact(
                metric="revenue",
                label_zh="營收",
                value=30e9,
                source_type="sec_xbrl",
                source_tag="us-gaap:Revenues",
            ),
            EarningsFact(
                metric="eps_diluted",
                label_zh="稀釋 EPS",
                value=5.25,
                unit="USD/share",
                source_type="sec_xbrl",
                source_tag="us-gaap:EarningsPerShareDiluted",
            ),
        ],
        ai_infra_signal="strong",
        ai_infra_relevance="Datacenter GPU demand",
        risk_flags=["毛利率壓力"],
        key_quotes=["Data center revenue grew."],
        source_documents=[
            SourceDocument(form_type="10-Q", filing_url="https://www.sec.gov/example")
        ],
        confidence="high",
    )


def test_format_earnings_v2_includes_takeaway_and_xbrl_tag():
    text = format_earnings_v2(_report())
    assert "NVDA" in text
    assert "AI 基建需求仍強" in text
    assert "us-gaap:Revenues" in text
    assert "SEC 原文" in text or "sec.gov" in text


def test_format_earnings_v2_sec_only_no_estimates():
    report = _report()
    report = report.model_copy(update={"estimates": {}, "surprise": {}})
    text = format_earnings_v2(report)
    assert "核心數字" in text
