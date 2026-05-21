from datetime import date

from sources.sec_submissions import EARNINGS_FORMS, SecSubmissionsClient, _is_earnings_form


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
