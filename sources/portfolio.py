"""Portfolio positions and target allocation from config/portfolio.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from sources.watchlist import EarningsWatchlist

PORTFOLIO_PATH = Path(__file__).resolve().parent.parent / "config" / "portfolio.yaml"

# Map watchlist tags → target_allocation theme keys.
TAG_TO_THEME: dict[str, str] = {
    "ai_infra": "ai_silicon",
    "ai_silicon": "ai_silicon",
    "semiconductor": "semiconductor",
    "memory": "memory",
    "hbm": "memory",
    "equipment": "equipment",
    "cloud_software": "cloud_software",
}

KNOWN_ALLOCATION_THEMES = frozenset(
    {"ai_silicon", "semiconductor", "memory", "equipment", "cloud_software", "other"}
)


class Position(BaseModel):
    ticker: str
    shares: float
    avg_cost: float | None = None
    thesis: str = ""  # P3: why held (one line) — drives thesis evidence-linking
    watch: list[str] = Field(default_factory=list)  # P3: what to watch for


class Portfolio(BaseModel):
    base_currency: str = "USD"
    as_of: str = ""
    positions: list[Position] = Field(default_factory=list)
    target_allocation: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path = PORTFOLIO_PATH) -> Portfolio:
        if not path.exists():
            return cls()
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        positions: list[Position] = []
        for row in data.get("positions") or []:
            ticker = str(row.get("ticker", "")).strip().upper()
            if not ticker:
                continue
            shares = float(row.get("shares") or 0)
            if shares == 0:
                continue
            avg_raw = row.get("avg_cost")
            avg_cost = float(avg_raw) if avg_raw is not None else None
            watch_raw = row.get("watch") or []
            watch = [str(w) for w in watch_raw] if isinstance(watch_raw, list) else []
            positions.append(
                Position(
                    ticker=ticker,
                    shares=shares,
                    avg_cost=avg_cost,
                    thesis=str(row.get("thesis") or ""),
                    watch=watch,
                )
            )
        target = {
            str(k): float(v)
            for k, v in (data.get("target_allocation") or {}).items()
        }
        return cls(
            base_currency=str(data.get("base_currency") or "USD"),
            as_of=str(data.get("as_of") or ""),
            positions=positions,
            target_allocation=target,
        )

    def tickers(self) -> list[str]:
        return sorted({p.ticker for p in self.positions})

    def position_for(self, ticker: str | None) -> Position | None:
        if not ticker:
            return None
        key = ticker.upper()
        for p in self.positions:
            if p.ticker == key:
                return p
        return None


def theme_for(ticker: str, watchlist: EarningsWatchlist) -> str:
    """Attribute ticker to a theme; first watchlist tag, normalized for target keys."""
    tags = watchlist.tags(ticker)
    if not tags:
        return "other"
    raw = tags[0]
    mapped = TAG_TO_THEME.get(raw, raw)
    if mapped in KNOWN_ALLOCATION_THEMES:
        return mapped
    return "other"
