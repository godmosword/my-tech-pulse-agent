"""Evidence governance for the investment signal — calibration & disclosure only.

This module turns graded live-signal records (each carrying realized forward
*excess* returns) into an honest track record: hit rate with a Wilson interval,
mean excess with a bootstrap interval, rank IC, an effective-independent-sample
estimate (semiconductor names are highly correlated, so nominal ``n`` overstates
information), a multiple-comparisons note, and an ``evidence_level``.

Critical governance rule (from plan review): ``evidence_level`` is kept SEPARATE
from the signal's structural ``conviction``. ``conviction`` measures how complete
the signal inputs were; ``evidence_level`` measures whether the signal has been
empirically shown to predict returns. The decision brief may only use
``evidence_level`` to soften tone — never to manufacture a buy/sell call.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any

# Directional rating buckets (mirror backtest.metrics).
BULLISH_RATINGS = frozenset({"強力看多", "看多"})
BEARISH_RATINGS = frozenset({"強力看空", "看空"})

EvidenceLevel = str  # "insufficient" | "weak" | "moderate" | "strong"

# Effective-sample thresholds for evidence_level. Deliberately conservative:
# with a tiny, correlated universe we should under-claim, not over-claim.
_MIN_EFF_WEAK = 5
_MIN_EFF_MODERATE = 8
_MIN_EFF_STRONG = 20


def wilson_interval(successes: int, n: int, *, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (no scipy)."""
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return (round(max(0.0, center - half), 4), round(min(1.0, center + half), 4))


def bootstrap_mean_ci(
    values: list[float],
    *,
    n_resamples: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float] | None:
    """Deterministic percentile bootstrap CI for the mean. None if too few points."""
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 3:
        return None
    rng = random.Random(seed)
    n = len(vals)
    means: list[float] = []
    for _ in range(n_resamples):
        resample = [vals[rng.randrange(n)] for _ in range(n)]
        means.append(sum(resample) / n)
    means.sort()
    lo_idx = int((alpha / 2) * n_resamples)
    hi_idx = min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))
    return (round(means[lo_idx], 4), round(means[hi_idx], 4))


def _ci_excludes_zero(ci: tuple[float, float] | None) -> bool:
    if ci is None:
        return False
    lo, hi = ci
    return lo > 0 or hi < 0


def effective_sample_size(group_sizes: list[int]) -> int:
    """Conservative effective-independent-sample estimate.

    Correlated observations (e.g. multiple quarters of the same ticker, or peers
    in one cluster) carry less than one independent observation each. We use the
    number of distinct groups (tickers) as a conservative floor on independent
    information, never exceeding the nominal count.
    """
    return len([g for g in group_sizes if g > 0])


def _evidence_level(
    *, n: int, n_eff: int, mean_ci_excludes_zero: bool
) -> EvidenceLevel:
    if n < 10 or n_eff < _MIN_EFF_WEAK:
        return "insufficient"
    if not mean_ci_excludes_zero or n_eff < _MIN_EFF_MODERATE:
        return "weak"
    if n_eff < _MIN_EFF_STRONG:
        return "moderate"
    return "strong"


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
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    rx, ry = _rank(x), _rank(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    den_x = math.sqrt(sum((a - mx) ** 2 for a in rx))
    den_y = math.sqrt(sum((b - my) ** 2 for b in ry))
    if den_x == 0 or den_y == 0:
        return None
    return round(num / (den_x * den_y), 4)


def _direction(rating: str) -> str:
    if rating in BULLISH_RATINGS:
        return "bullish"
    if rating in BEARISH_RATINGS:
        return "bearish"
    return "neutral"


def _bucket_stats(rows: list[dict[str, Any]], excess_key: str) -> dict[str, Any] | None:
    """Hit rate (directional) + mean-excess CI + evidence for one rating direction."""
    excesses: list[float] = []
    tickers: dict[str, int] = defaultdict(int)
    hits = 0
    directional = 0
    for row in rows:
        excess = (row.get("returns") or {}).get(excess_key)
        if excess is None:
            continue
        excess = float(excess)
        excesses.append(excess)
        tickers[str(row.get("ticker") or "?").upper()] += 1
        direction = _direction(str(row.get("rating") or ""))
        if direction == "bullish":
            directional += 1
            hits += 1 if excess > 0 else 0
        elif direction == "bearish":
            directional += 1
            hits += 1 if excess < 0 else 0
    n = len(excesses)
    if n == 0:
        return None
    n_eff = effective_sample_size(list(tickers.values()))
    mean_ci = bootstrap_mean_ci(excesses)
    hit_rate = round(hits / directional, 4) if directional else None
    hit_ci = wilson_interval(hits, directional) if directional else None
    return {
        "n": n,
        "n_effective": n_eff,
        "distinct_tickers": len(tickers),
        "mean_excess_pct": round(sum(excesses) / n, 4),
        "mean_excess_ci": mean_ci,
        "directional_n": directional,
        "hit_rate": hit_rate,
        "hit_rate_ci": hit_ci,
        "evidence_level": _evidence_level(
            n=n, n_eff=n_eff, mean_ci_excludes_zero=_ci_excludes_zero(mean_ci)
        ),
    }


def build_track_record(
    records: list[dict[str, Any]],
    *,
    horizons: tuple[int, ...] = (5, 20, 60),
    signal_version: str | None = None,
) -> dict[str, Any]:
    """Aggregate graded records into an honest, disclosed track record.

    Only records matching ``signal_version`` are included (mixing factor sets
    would compare apples to oranges). ``records`` are shaped like the rows from
    ``backtest.decision_log.evaluate_live_log`` (rating/score/ticker + a
    ``returns`` map of ``excess_<h>d``).
    """
    if signal_version is not None:
        records = [r for r in records if r.get("signal_version") == signal_version]

    by_horizon: dict[str, Any] = {}
    bucket_count = 0
    for h in horizons:
        excess_key = f"excess_{h}d"
        scores: list[float] = []
        excesses: list[float] = []
        for row in records:
            ex = (row.get("returns") or {}).get(excess_key)
            sc = row.get("score")
            if ex is not None and sc is not None:
                scores.append(float(sc))
                excesses.append(float(ex))

        overall = _bucket_stats(records, excess_key)
        bullish = _bucket_stats(
            [r for r in records if _direction(str(r.get("rating") or "")) == "bullish"],
            excess_key,
        )
        bearish = _bucket_stats(
            [r for r in records if _direction(str(r.get("rating") or "")) == "bearish"],
            excess_key,
        )
        bucket_count += sum(1 for b in (overall, bullish, bearish) if b)
        by_horizon[str(h)] = {
            "overall": overall,
            "bullish": bullish,
            "bearish": bearish,
            "ic_spearman": _spearman(scores, excesses),
            "ic_n": len(scores),
        }

    return {
        "signal_version": signal_version,
        "horizons": list(horizons),
        "n_records": len(records),
        "by_horizon": by_horizon,
        "multiple_comparisons": {
            "buckets_tested": bucket_count,
            "note": (
                "多個 horizon × 評級方向 同時檢定；單一 bucket 的 CI 未做 "
                "family-wise 校正，請以整體一致性而非單點顯著性解讀。"
            ),
        },
        "disclaimer_zh": (
            "本戰績為事後校準揭露，非投資建議；樣本小且半導體標的高度相關，"
            "有效獨立樣本數遠低於名目筆數。"
        ),
    }
