"""Watchlist export includes Q-Silicon mega-cap tickers."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MEGA_CAP = {
    "MSFT", "GOOGL", "AAPL", "META", "AMZN", "ORCL", "CRM", "NOW",
    "SNOW", "PLTR", "CRWD", "NET", "DELL", "HPE", "ANET", "CSCO",
    "LITE", "COHR", "FN", "INTC", "QCOM",
}


def test_watchlist_json_contains_mega_cap():
    path = ROOT / "dashboard" / "lib" / "earnings-watchlist-data.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    tickers = {e["ticker"] for e in data["entries"]}
    missing = MEGA_CAP - tickers
    assert not missing, f"missing mega-cap tickers: {sorted(missing)}"
    assert len(tickers) >= 40
