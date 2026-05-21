"""Load tiered earnings watchlist from config/earnings_watchlist.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "config" / "earnings_watchlist.yaml"


@dataclass(frozen=True)
class WatchlistEntry:
    ticker: str
    tier: int
    tags: tuple[str, ...] = ()


class EarningsWatchlist:
    def __init__(self, entries: list[WatchlistEntry]):
        self._by_ticker = {e.ticker.upper(): e for e in entries}

    @classmethod
    def load(cls, path: Path = WATCHLIST_PATH) -> EarningsWatchlist:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries: list[WatchlistEntry] = []
        for row in data.get("entries") or []:
            ticker = str(row.get("ticker", "")).strip().upper()
            if not ticker:
                continue
            tier = int(row.get("tier", 99))
            tags = tuple(str(t) for t in (row.get("tags") or []))
            entries.append(WatchlistEntry(ticker=ticker, tier=tier, tags=tags))
        return cls(entries)

    def tier(self, ticker: str | None) -> int | None:
        if not ticker:
            return None
        entry = self._by_ticker.get(ticker.upper())
        return entry.tier if entry else None

    def tags(self, ticker: str | None) -> tuple[str, ...]:
        if not ticker:
            return ()
        entry = self._by_ticker.get(ticker.upper())
        return entry.tags if entry else ()

    def tickers(self) -> list[str]:
        return sorted(self._by_ticker.keys())

    def sort_key(self, ticker: str | None) -> tuple[int, str]:
        """Lower tier number = higher priority."""
        t = self.tier(ticker)
        return (t if t is not None else 99, (ticker or "").upper())
