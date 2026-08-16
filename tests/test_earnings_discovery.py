from sources.earnings_fetcher import (
    EarningsFiling,
    accession_from_filing_url,
    filing_accession_key,
)
from pipeline.earnings_pipeline import merge_filings_by_accession, rotate_tickers


def test_rotate_tickers_wraps_from_day_index():
    assert rotate_tickers(["A", "B", "C"], 1) == ["B", "C", "A"]
    assert rotate_tickers(["A", "B", "C"], 3) == ["A", "B", "C"]
    assert rotate_tickers([], 4) == []


def test_merge_filings_prefers_first_accession():
    watch = EarningsFiling(
        company="NVIDIA",
        ticker="NVDA",
        form_type="8-K",
        accession="000-1",
        filing_url="https://sec.example/watch",
        source="SEC 8-K",
    )
    atom = EarningsFiling(
        company="NVIDIA",
        ticker="NVDA",
        form_type="8-K",
        accession="000-1",
        filing_url="https://sec.example/atom",
        source="SEC 8-K",
    )
    other = EarningsFiling(
        company="Other",
        ticker="FOO",
        form_type="8-K",
        accession="000-2",
        filing_url="https://sec.example/foo",
        source="SEC 8-K",
    )
    merged = merge_filings_by_accession([watch], [atom, other])
    assert [f.accession for f in merged] == ["000-1", "000-2"]
    assert merged[0].filing_url == "https://sec.example/watch"


def test_accession_from_archives_url():
    url = "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000003/nvda-20260120.htm"
    assert accession_from_filing_url(url) == "0001045810-26-000003"
    assert accession_from_filing_url("https://example.com/not-sec") is None


def test_merge_filings_dedups_atom_without_accession():
    watch = EarningsFiling(
        company="NVIDIA",
        ticker="NVDA",
        form_type="8-K",
        accession="0001045810-26-000003",
        filing_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581026000003/nvda-20260120",
        source="SEC 8-K",
    )
    atom = EarningsFiling(
        company="NVIDIA CORP",
        form_type="8-K",
        accession=None,
        filing_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581026000003/nvda-20260120.htm",
        source="SEC 8-K",
    )
    assert filing_accession_key(watch) == filing_accession_key(atom)
    merged = merge_filings_by_accession([watch], [atom])
    assert len(merged) == 1
    assert merged[0].accession == "0001045810-26-000003"
