"""Price correlation matrix and hierarchical clustering (numpy optional)."""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def _daily_returns(closes: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(closes)):
        prev, cur = closes[i - 1], closes[i]
        if prev == 0:
            continue
        out.append((cur - prev) / prev)
    return out


def _pearson(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    xs, ys = x[:n], y[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den_x = math.sqrt(sum((a - mx) ** 2 for a in xs))
    den_y = math.sqrt(sum((b - my) ** 2 for b in ys))
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def build_correlation_matrix(
    price_series: dict[str, list[float]],
    *,
    window: int = 120,
) -> dict[str, Any]:
    """Pearson correlation of daily returns over the last `window` closes."""
    skipped: list[str] = []
    returns: dict[str, list[float]] = {}

    for ticker, closes in price_series.items():
        series = closes[-window:] if len(closes) >= window else closes
        if len(series) < window:
            skipped.append(ticker)
            continue
        rets = _daily_returns(series)
        if len(rets) < window - 1:
            skipped.append(ticker)
            continue
        returns[ticker.upper()] = rets

    tickers = sorted(returns.keys())
    n = len(tickers)
    matrix = [[0.0] * n for _ in range(n)]
    for i, ti in enumerate(tickers):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            tj = tickers[j]
            c = _pearson(returns[ti], returns[tj])
            matrix[i][j] = c
            matrix[j][i] = c

    return {"tickers": tickers, "matrix": matrix, "skipped": skipped}


def _avg_intra_corr(members: list[str], tickers: list[str], matrix: list[list[float]]) -> float:
    idx = {t: i for i, t in enumerate(tickers)}
    pairs: list[float] = []
    for i, a in enumerate(members):
        for b in members[i + 1 :]:
            ia, ib = idx.get(a), idx.get(b)
            if ia is None or ib is None:
                continue
            pairs.append(matrix[ia][ib])
    if not pairs:
        return 1.0
    return sum(pairs) / len(pairs)


def cluster_tickers(
    corr_matrix: dict[str, Any],
    tickers: list[str],
    *,
    threshold: float = 0.7,
) -> list[dict[str, Any]]:
    """Single-linkage clustering using distance = 1 - correlation."""
    matrix = corr_matrix.get("matrix") or []
    order = corr_matrix.get("tickers") or tickers
    idx = {t: i for i, t in enumerate(order)}

    def dist(a: str, b: str) -> float:
        ia, ib = idx.get(a), idx.get(b)
        if ia is None or ib is None:
            return 1.0
        return 1.0 - matrix[ia][ib]

    clusters: list[list[str]] = [[t] for t in tickers if t in idx]
    max_dist = 1.0 - threshold

    while True:
        best: tuple[float, int, int] | None = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                d = min(dist(a, b) for a in clusters[i] for b in clusters[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        if best is None or best[0] > max_dist:
            break
        _, i, j = best
        merged = clusters[i] + clusters[j]
        clusters = [c for k, c in enumerate(clusters) if k not in (i, j)] + [merged]

    out: list[dict[str, Any]] = []
    for cid, members in enumerate(clusters):
        members_sorted = sorted({m.upper() for m in members})
        out.append(
            {
                "cluster_id": cid,
                "members": members_sorted,
                "avg_intra_corr": round(_avg_intra_corr(members_sorted, order, matrix), 4),
            }
        )
    return out


def correlated_with(
    corr_matrix: dict[str, Any],
    tickers: list[str],
    target: str,
    *,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    matrix = corr_matrix.get("matrix") or []
    order = corr_matrix.get("tickers") or tickers
    target_u = target.upper()
    if target_u not in order:
        return []
    ti = order.index(target_u)
    rows: list[dict[str, Any]] = []
    for j, other in enumerate(order):
        if other == target_u:
            continue
        rows.append({"ticker": other, "corr": round(matrix[ti][j], 4)})
    rows.sort(key=lambda r: r["corr"], reverse=True)
    return rows[:top_n]
