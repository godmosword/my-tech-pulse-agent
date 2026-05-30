"""Strict accession matching for XBRL quarter pick (D1)."""

from __future__ import annotations

import json
from pathlib import Path

from sources.sec_xbrl_fetcher import SecXbrlFetcher, _pick_quarterly_for_accession

NVDA = Path(__file__).parent / "fixtures" / "sec_companyfacts_nvda_sample.json"


def test_no_accession_still_picks_latest():
    data = json.loads(NVDA.read_text(encoding="utf-8"))
    fetcher = SecXbrlFetcher()
    assert fetcher.normalize_latest_quarter_facts(data) is not None


def test_matching_accession_returns_row():
    entries = [
        {"fp": "Q3", "val": 1.0, "accn": "0001045810-24-000123", "filed": "2024-11-20", "end": "2024-10-27"},
        {"fp": "Q2", "val": 2.0, "accn": "0001045810-24-000100", "filed": "2024-08-28", "end": "2024-07-28"},
    ]
    row = _pick_quarterly_for_accession(entries, "0001045810-24-000100")
    assert row is not None
    assert row["val"] == 2.0


def test_mismatched_accession_returns_none_not_latest():
    entries = [
        {"fp": "Q3", "val": 1.0, "accn": "0001045810-24-000123", "filed": "2024-11-20", "end": "2024-10-27"},
    ]
    assert _pick_quarterly_for_accession(entries, "0001045810-99-000999") is None


def test_nvda_wrong_accession_normalize_returns_none():
    data = json.loads(NVDA.read_text(encoding="utf-8"))
    fetcher = SecXbrlFetcher()
    assert fetcher.normalize_quarter_facts(data, accession="0001045810-99-000999") is None


def test_nvda_correct_accession_picks_scoped_quarter():
    data = json.loads(NVDA.read_text(encoding="utf-8"))
    fetcher = SecXbrlFetcher()
    normalized = fetcher.normalize_quarter_facts(data, accession="0001045810-24-000100")
    assert normalized is not None
    period_meta, _ = normalized
    assert period_meta["fiscal_period"] == "Q2"
    assert str(period_meta["period_end"]).startswith("2024-07-28")
