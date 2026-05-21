import json
from pathlib import Path

from sources.sec_xbrl_fetcher import SecXbrlFetcher
from sources.ticker_cik_map import TickerCikMap
from sources.watchlist import EarningsWatchlist


FIXTURE = Path(__file__).parent / "fixtures" / "sec_companyfacts_nvda_sample.json"


def test_normalize_latest_quarter_facts_picks_latest_filed():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
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


def test_build_facts_from_xbrl():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fetcher = SecXbrlFetcher()
    facts = fetcher.build_facts_from_xbrl(data, source_url="https://www.sec.gov/example")
    assert len(facts) >= 2
    revenue = next(f for f in facts if f["metric"] == "revenue")
    assert revenue["value"] == 35082000000.0
    assert revenue["confidence"] == "high"


def test_watchlist_tier_sort():
    wl = EarningsWatchlist.load()
    assert wl.tier("NVDA") == 1
    assert wl.tier("ENTG") == 5
    assert wl.tier("ZZZZ") is None
    assert wl.sort_key("NVDA") < wl.sort_key("ENTG")


def test_ticker_cik_builtin_offline():
    import os

    os.environ["SEC_TICKER_MAP_OFFLINE"] = "1"
    m = TickerCikMap.load()
    assert m.cik_for("NVDA") == "0001045810"
    assert m.resolve_ticker("NVIDIA CORP") == "NVDA"
