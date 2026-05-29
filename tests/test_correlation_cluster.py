"""Tests for price correlation clustering and exposure passthrough."""

from scoring.correlation_cluster import (
    build_correlation_matrix,
    cluster_tickers,
    correlated_with,
)


def _trend_series(start: float, daily: float, n: int) -> list[float]:
    out = [start]
    for _ in range(n - 1):
        out.append(out[-1] * (1 + daily))
    return out


def _correlated_pair(seed: float, n: int, *, noise: float = 0.0) -> tuple[list[float], list[float]]:
    """Two price series with stochastic but highly correlated daily returns."""
    import random

    rng = random.Random(seed)
    a = [100.0]
    b = [200.0]
    for _ in range(n - 1):
        r = rng.uniform(-0.02, 0.02)
        a.append(a[-1] * (1 + r))
        b.append(b[-1] * (1 + r + rng.uniform(-noise, noise)))
    return a, b


def test_cluster_two_correlated_groups():
    n = 130
    group_a, group_a2 = _correlated_pair(1, n, noise=0.001)
    group_b, group_b2 = _correlated_pair(2, n, noise=0.001)
    noise = _trend_series(50, -0.0005, n)

    price_series = {
        "A1": group_a,
        "A2": group_a2,
        "B1": group_b,
        "B2": group_b2,
        "X": noise,
    }
    corr = build_correlation_matrix(price_series, window=120)
    clusters = cluster_tickers(corr, corr["tickers"], threshold=0.7)

    member_sets = [frozenset(c["members"]) for c in clusters]
    assert frozenset({"A1", "A2"}) in member_sets
    assert frozenset({"B1", "B2"}) in member_sets


def test_correlated_with_orders_by_strength():
    n = 130
    base, high = _correlated_pair(42, n, noise=0.0005)
    import random

    rng = random.Random(99)
    low = [100.0]
    for _ in range(n - 1):
        low.append(low[-1] * (1 + rng.uniform(-0.03, 0.01)))
    price_series = {
        "TGT": base,
        "HIGH": high,
        "LOW": low,
    }
    corr = build_correlation_matrix(price_series, window=120)
    rows = correlated_with(corr, corr["tickers"], "TGT", top_n=3)
    assert rows[0]["ticker"] == "HIGH"
    assert rows[0]["corr"] >= rows[-1]["corr"]


def test_short_series_skipped():
    price_series = {"OK": _trend_series(50, 0.001, 130), "SHORT": _trend_series(10, 0.01, 30)}
    corr = build_correlation_matrix(price_series, window=120)
    assert "SHORT" in corr["skipped"]
    assert "OK" in corr["tickers"]
    assert "SHORT" not in corr["tickers"]


