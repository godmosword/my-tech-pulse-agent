"""MSFT / TSM / GOOGL fiscal boundary fixtures — see docs/fixtures/FISCAL_BOUNDARY_FIXTURES.md."""

from __future__ import annotations

import json
from pathlib import Path

from sources.sec_xbrl_fetcher import SecXbrlFetcher

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_msft_june_fy_q2_not_calendar_q4():
    data = _load("sec_companyfacts_msft_fy_boundary.json")
    fetcher = SecXbrlFetcher()
    normalized = fetcher.normalize_quarter_facts(data, accession="0000789019-25-000012")
    assert normalized is not None
    period_meta, facts = normalized
    assert period_meta["fiscal_year"] == 2025
    assert period_meta["fiscal_period"] == "Q2"
    assert str(period_meta["period_end"]).startswith("2024-12-31")
    assert period_meta["fiscal_period"] != "Q4"
    revenue = next(f for f in facts if f["metric"] == "revenue")
    assert revenue["val"] == 69632000000.0


def test_msft_wrong_accession_strict_none():
    data = _load("sec_companyfacts_msft_fy_boundary.json")
    fetcher = SecXbrlFetcher()
    assert fetcher.normalize_quarter_facts(data, accession="0000789019-99-000000") is None


def test_tsm_q4_fy_from_period_end_not_filed_year():
    data = _load("sec_companyfacts_tsm_fy_boundary.json")
    fetcher = SecXbrlFetcher()
    normalized = fetcher.normalize_quarter_facts(data, accession="0001046179-25-000004")
    assert normalized is not None
    period_meta, _ = normalized
    assert period_meta["fiscal_year"] == 2024
    assert period_meta["fiscal_period"] == "Q4"
    assert str(period_meta["period_end"]).startswith("2024-12-31")


def test_tsm_q1_fy2025():
    data = _load("sec_companyfacts_tsm_fy_boundary.json")
    fetcher = SecXbrlFetcher()
    normalized = fetcher.normalize_quarter_facts(data, accession="0001046179-25-000018")
    assert normalized is not None
    period_meta, _ = normalized
    assert period_meta["fiscal_year"] == 2025
    assert period_meta["fiscal_period"] == "Q1"
    assert str(period_meta["period_end"]).startswith("2025-03-31")


def test_tsm_build_facts_accession_scoped():
    data = _load("sec_companyfacts_tsm_fy_boundary.json")
    fetcher = SecXbrlFetcher()
    facts = fetcher.build_facts_from_xbrl(
        data,
        source_url="https://www.sec.gov/example",
        accession="0001046179-25-000004",
    )
    revenue = next(f for f in facts if f["metric"] == "revenue")
    assert revenue["fiscal_year"] == 2024
    assert revenue["fiscal_period"] == "Q4"


def test_googl_september_fy_q1_not_calendar_q4():
    data = _load("sec_companyfacts_googl_fy_boundary.json")
    fetcher = SecXbrlFetcher()
    normalized = fetcher.normalize_quarter_facts(data, accession="0001652044-25-000014")
    assert normalized is not None
    period_meta, facts = normalized
    assert period_meta["fiscal_year"] == 2025
    assert period_meta["fiscal_period"] == "Q1"
    assert str(period_meta["period_end"]).startswith("2024-12-31")
    assert period_meta["fiscal_period"] != "Q4"
    revenue = next(f for f in facts if f["metric"] == "revenue")
    assert revenue["val"] == 96546000000.0


def test_googl_q2_fy2025():
    data = _load("sec_companyfacts_googl_fy_boundary.json")
    fetcher = SecXbrlFetcher()
    normalized = fetcher.normalize_quarter_facts(data, accession="0001652044-25-000043")
    assert normalized is not None
    period_meta, _ = normalized
    assert period_meta["fiscal_year"] == 2025
    assert period_meta["fiscal_period"] == "Q2"
    assert str(period_meta["period_end"]).startswith("2025-03-31")


def test_googl_wrong_accession_strict_none():
    data = _load("sec_companyfacts_googl_fy_boundary.json")
    fetcher = SecXbrlFetcher()
    assert fetcher.normalize_quarter_facts(data, accession="0001652044-99-000000") is None


def test_googl_build_facts_accession_scoped():
    data = _load("sec_companyfacts_googl_fy_boundary.json")
    fetcher = SecXbrlFetcher()
    facts = fetcher.build_facts_from_xbrl(
        data,
        source_url="https://www.sec.gov/example",
        accession="0001652044-25-000014",
    )
    revenue = next(f for f in facts if f["metric"] == "revenue")
    assert revenue["fiscal_year"] == 2025
    assert revenue["fiscal_period"] == "Q1"
