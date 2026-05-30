from datetime import date
from pathlib import Path

import json

from sources.sec_submissions import EARNINGS_FORMS, SecSubmissionsClient, _is_earnings_form

FIXTURES = Path(__file__).parent / "fixtures"


def test_is_earnings_form():
    assert _is_earnings_form("8-K", EARNINGS_FORMS) is True
    assert _is_earnings_form("8-K/A", EARNINGS_FORMS) is True
    assert _is_earnings_form("S-1", EARNINGS_FORMS) is False


def test_list_filings_in_range_filters_dates(monkeypatch):
    submissions = {
        "name": "NVIDIA CORP",
        "filings": {
            "recent": {
                "form": ["8-K", "10-Q", "4"],
                "accessionNumber": [
                    "0001045810-26-000001",
                    "0001045810-26-000002",
                    "0001045810-26-000003",
                ],
                "filingDate": ["2026-05-15", "2026-04-20", "2026-05-18"],
                "reportDate": ["2026-05-14", "2026-04-19", ""],
                "primaryDocument": ["d8k.htm", "q10.htm", "form4.xml"],
            }
        },
    }
    client = SecSubmissionsClient()
    monkeypatch.setattr(client, "get_submissions", lambda _cik: submissions)
    filings = client.list_filings_in_range(
        ticker="NVDA",
        company="NVIDIA CORP",
        cik="0001045810",
        since=date(2026, 5, 1),
        until=date(2026, 5, 21),
    )
    # Only 8-K on 5/15 in range (10-Q is April, form 4 excluded)
    assert len(filings) == 1
    assert filings[0].form_type == "8-K"
    assert filings[0].filed_at.date() == date(2026, 5, 15)


def test_list_filings_in_range_fetches_archive_when_needed(monkeypatch):
    submissions = json.loads(
        (FIXTURES / "sec_submissions_with_archive.json").read_text(encoding="utf-8")
    )
    archive_page = json.loads(
        (FIXTURES / "sec_submissions_archive_page.json").read_text(encoding="utf-8")
    )
    client = SecSubmissionsClient()

    def fake_get(url: str):
        if url.endswith("CIK0001045810-submissions-001.json"):
            return archive_page
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(client._client, "get_json", fake_get)
    monkeypatch.setattr(client, "get_submissions", lambda _cik: submissions)

    recent_only = client.list_filings_in_range(
        ticker="NVDA",
        company="NVIDIA CORP",
        cik="0001045810",
        since=date(2026, 5, 1),
        until=date(2026, 5, 21),
    )
    assert len(recent_only) == 1
    assert recent_only[0].form_type == "8-K"

    with_archive = client.list_filings_in_range(
        ticker="NVDA",
        company="NVIDIA CORP",
        cik="0001045810",
        since=date(2024, 11, 1),
        until=date(2024, 11, 30),
    )
    assert len(with_archive) == 1
    assert with_archive[0].form_type == "10-Q"
    assert with_archive[0].filed_at.date() == date(2024, 11, 15)


def test_archive_overlap_skips_non_overlapping_pages(monkeypatch):
    submissions = {
        "filings": {
            "recent": {"form": [], "accessionNumber": [], "filingDate": [], "primaryDocument": []},
            "files": [
                {
                    "name": "CIK0001045810-submissions-001.json",
                    "filingFrom": "2020-01-01",
                    "filingTo": "2020-12-31",
                }
            ],
        }
    }
    client = SecSubmissionsClient()
    called: list[str] = []

    def fake_get(url: str):
        called.append(url)
        return {"form": [], "accessionNumber": [], "filingDate": [], "primaryDocument": []}

    monkeypatch.setattr(client._client, "get_json", fake_get)
    monkeypatch.setattr(client, "get_submissions", lambda _cik: submissions)

    client.list_filings_in_range(
        ticker="NVDA",
        company="NVIDIA CORP",
        cik="0001045810",
        since=date(2024, 11, 1),
        until=date(2024, 11, 30),
    )
    assert called == []
