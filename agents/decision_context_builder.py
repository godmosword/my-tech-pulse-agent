"""P2 — market-context flags at the moment of news (decision context).

Pure functions over a price series. Flags are descriptive technical states
(``near_52w_high``, ``above_200dma``, ``post_event_excess_move``); we deliberately
do NOT assert "priced in". Valuation percentile is computed from a supplied
historical series and is marked point-in-time — it must never be mixed into the
Phase-0 track record.

Live fetching (Finnhub candles) is gated to material/held names by the caller;
this module keeps the logic pure so it is testable without network access.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

NEAR_HIGH_FRAC = 0.95
NEAR_LOW_FRAC = 1.05
EXCESS_MOVE_THRESHOLD = 0.05  # 5% 5-day move vs benchmark


class MarketContext(BaseModel):
    flags: list[str] = Field(default_factory=list)
    last_close: Optional[float] = None
    pct_vs_200dma: Optional[float] = None
    pct_from_52w_high: Optional[float] = None
    valuation_percentile: Optional[float] = None
    point_in_time: bool = True


def closes_from_candle(candle: Optional[dict]) -> list[float]:
    """Extract the close series from a Finnhub /stock/candle response."""
    if not candle:
        return []
    return [float(x) for x in (candle.get("c") or []) if x is not None]


def build_market_context(
    finnhub: object,
    symbol: str,
    *,
    bench_closes: Optional[list[float]] = None,
    days_back: int = 250,
) -> MarketContext:
    """Network-backed wrapper: fetch a candle, then compute pure flags.

    Gated to material/held names by the caller; the heavy logic lives in
    ``compute_market_context_flags`` so it stays unit-testable without network.
    """
    candle = finnhub.candle(symbol, days_back=days_back)  # type: ignore[attr-defined]
    return compute_market_context_flags(
        closes_from_candle(candle), bench_closes=bench_closes
    )


def _mean(vals: list[float]) -> Optional[float]:
    return sum(vals) / len(vals) if vals else None


def valuation_percentile(history: list[float], current: float) -> Optional[float]:
    """Rank of `current` within `history` (0 = cheapest, 1 = most expensive)."""
    clean = [v for v in history if v is not None]
    if len(clean) < 8 or current is None:
        return None
    below = sum(1 for v in clean if v <= current)
    return round(below / len(clean), 4)


def compute_market_context_flags(
    closes: list[float],
    *,
    bench_closes: Optional[list[float]] = None,
    valuation_history: Optional[list[float]] = None,
    current_valuation: Optional[float] = None,
) -> MarketContext:
    """Descriptive technical/valuation state — never a buy/sell verdict."""
    closes = [c for c in closes if c is not None]
    if not closes:
        return MarketContext()

    last = closes[-1]
    flags: list[str] = []

    ma200 = _mean(closes[-200:]) if len(closes) >= 200 else None
    pct_vs_200 = None
    if ma200:
        pct_vs_200 = round((last - ma200) / ma200, 4)
        flags.append("above_200dma" if last >= ma200 else "below_200dma")

    hi = max(closes)
    lo = min(closes)
    pct_from_high = round((last - hi) / hi, 4) if hi else None
    if hi and last >= NEAR_HIGH_FRAC * hi:
        flags.append("near_52w_high")
    if lo and last <= NEAR_LOW_FRAC * lo:
        flags.append("near_52w_low")

    if bench_closes and len(closes) >= 6 and len(bench_closes) >= 6:
        sym_ret = closes[-1] / closes[-6] - 1
        bench_ret = bench_closes[-1] / bench_closes[-6] - 1
        if abs(sym_ret - bench_ret) >= EXCESS_MOVE_THRESHOLD:
            flags.append("post_event_excess_move")

    val_pct = None
    if valuation_history is not None and current_valuation is not None:
        val_pct = valuation_percentile(valuation_history, current_valuation)

    return MarketContext(
        flags=flags,
        last_close=round(last, 4),
        pct_vs_200dma=pct_vs_200,
        pct_from_52w_high=pct_from_high,
        valuation_percentile=val_pct,
    )
