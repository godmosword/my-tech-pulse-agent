"""Forward return and backtest evaluation metrics (no heavy deps)."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable

from backtest.pit_data import return_between

BULLISH_RATINGS = frozenset({"強力看多", "看多"})
BEARISH_RATINGS = frozenset({"強力看空", "看空"})


def _spearman(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 3 or len(y) != n:
        return None

    def _rank(vals: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg_rank
            i = j + 1
        return ranks

    rx, ry = _rank(x), _rank(y)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    den_x = math.sqrt(sum((a - mx) ** 2 for a in rx))
    den_y = math.sqrt(sum((b - my) ** 2 for b in ry))
    if den_x == 0 or den_y == 0:
        return None
    return round(num / (den_x * den_y), 4)


def forward_return(
    finnhub: Any,
    symbol: str,
    *,
    decision_date: str,
    horizon_days: int,
    bench: str = "SOXX",
) -> dict[str, Any]:
    """Stock and benchmark returns from decision_date over horizon trading days."""
    sym_ret = return_between(
        finnhub,
        symbol,
        start_date=decision_date,
        horizon_trading_days=horizon_days,
    )
    bench_ret = return_between(
        finnhub,
        bench,
        start_date=decision_date,
        horizon_trading_days=horizon_days,
    )
    excess = None
    if sym_ret is not None and bench_ret is not None:
        excess = round(sym_ret - bench_ret, 4)
    return {
        "horizon_days": horizon_days,
        "return_pct": sym_ret,
        "bench_return_pct": bench_ret,
        "excess_return_pct": excess,
        "bench": bench,
    }


def _mean(vals: Iterable[float | None]) -> float | None:
    nums = [v for v in vals if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 4)


def _win_rate(vals: Iterable[float | None]) -> float | None:
    nums = [v for v in vals if v is not None]
    if not nums:
        return None
    wins = sum(1 for v in nums if v > 0)
    return round(wins / len(nums), 4)


def evaluate(
    records_with_returns: list[dict[str, Any]],
    *,
    horizons: tuple[int, ...] = (5, 20, 60),
    min_bucket_n: int = 20,
) -> dict[str, Any]:
    """Summarize backtest calibration: buckets, IC, hit rate, sample warnings."""
    out: dict[str, Any] = {
        "horizons": list(horizons),
        "by_rating": {},
        "quantile_spread": {},
        "ic": {},
        "hit_rate": {},
        "sample_warnings": [],
        "n_records": len(records_with_returns),
    }

    for h in horizons:
        key = f"excess_{h}d"
        rated: dict[str, list[float]] = defaultdict(list)
        scores: list[float] = []
        excesses: list[float] = []
        hits = 0
        hit_total = 0

        for row in records_with_returns:
            block = row.get("returns") or {}
            excess = block.get(key)
            if excess is None:
                continue
            rating = str(row.get("rating") or "資料不足")
            rated[rating].append(float(excess))
            score = row.get("score")
            if score is not None:
                scores.append(float(score))
                excesses.append(float(excess))
            if rating in BULLISH_RATINGS:
                hit_total += 1
                if excess > 0:
                    hits += 1
            elif rating in BEARISH_RATINGS:
                hit_total += 1
                if excess < 0:
                    hits += 1

        by_rating_h: dict[str, Any] = {}
        for rating, vals in sorted(rated.items()):
            n = len(vals)
            entry = {
                "n": n,
                "mean_excess_pct": _mean(vals),
                "win_rate": _win_rate(vals),
            }
            if n < min_bucket_n:
                entry["insufficient_sample"] = True
                out["sample_warnings"].append(
                    {"horizon_days": h, "rating": rating, "n": n, "min_required": min_bucket_n}
                )
            by_rating_h[rating] = entry
        out["by_rating"][str(h)] = by_rating_h

        if len(scores) >= 6:
            paired = sorted(zip(scores, excesses, strict=True), key=lambda p: p[0])
            third = max(len(paired) // 3, 1)
            low = [e for _, e in paired[:third]]
            high = [e for _, e in paired[-third:]]
            low_m = _mean(low)
            high_m = _mean(high)
            spread = None
            if low_m is not None and high_m is not None:
                spread = round(high_m - low_m, 4)
            out["quantile_spread"][str(h)] = {
                "top_tertile_mean_excess_pct": high_m,
                "bottom_tertile_mean_excess_pct": low_m,
                "spread_pct": spread,
                "n": len(scores),
            }
        else:
            out["quantile_spread"][str(h)] = {"n": len(scores), "spread_pct": None}

        out["ic"][str(h)] = {"spearman": _spearman(scores, excesses), "n": len(scores)}
        out["hit_rate"][str(h)] = {
            "rate": round(hits / hit_total, 4) if hit_total else None,
            "n": hit_total,
        }

    return out
