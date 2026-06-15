"""Tests for Phase-0 evidence governance (scoring/track_record.py)."""

from __future__ import annotations

from scoring.track_record import (
    _evidence_level,
    bootstrap_mean_ci,
    build_track_record,
    effective_sample_size,
    wilson_interval,
)


def test_wilson_interval_basic_bounds():
    lo, hi = wilson_interval(50, 100)
    assert 0.0 <= lo < 0.5 < hi <= 1.0
    # Wilson is narrower and pulled toward 0.5 vs naive; sanity range.
    assert 0.39 < lo < 0.41
    assert 0.59 < hi < 0.61


def test_wilson_interval_edge_cases():
    assert wilson_interval(0, 0) == (0.0, 0.0)
    lo, hi = wilson_interval(10, 10)
    assert hi <= 1.0 and lo > 0.6  # all-success still has uncertainty


def test_bootstrap_is_deterministic_and_handles_small_n():
    vals = [0.1, -0.2, 0.3, 0.05, -0.1, 0.2]
    a = bootstrap_mean_ci(vals, seed=42)
    b = bootstrap_mean_ci(vals, seed=42)
    assert a == b
    assert a is not None and a[0] <= a[1]
    assert bootstrap_mean_ci([0.1, 0.2]) is None  # < 3 points


def test_effective_sample_size_counts_distinct_groups():
    # 3 tickers with 4/2/1 observations -> 3 effective independent samples
    assert effective_sample_size([4, 2, 1]) == 3
    assert effective_sample_size([0, 0]) == 0


def test_evidence_level_thresholds():
    assert _evidence_level(n=5, n_eff=2, mean_ci_excludes_zero=True) == "insufficient"
    assert _evidence_level(n=12, n_eff=6, mean_ci_excludes_zero=False) == "weak"
    assert _evidence_level(n=30, n_eff=10, mean_ci_excludes_zero=True) == "moderate"
    assert _evidence_level(n=60, n_eff=25, mean_ci_excludes_zero=True) == "strong"
    # signal present but too few independent names -> never "strong"
    assert _evidence_level(n=100, n_eff=4, mean_ci_excludes_zero=True) == "insufficient"


def _rec(ticker: str, rating: str, score: float, excess: float, version: str = "v1"):
    return {
        "ticker": ticker,
        "rating": rating,
        "score": score,
        "signal_version": version,
        "returns": {"excess_5d": excess, "excess_20d": excess, "excess_60d": excess},
    }


def test_build_track_record_structure_and_version_filter():
    records = [
        _rec("NVDA", "看多", 70, 0.03),
        _rec("AMD", "看多", 65, 0.01),
        _rec("INTC", "看空", 30, -0.02),
        _rec("OLD", "看多", 80, 0.5, version="v0"),  # filtered out
    ]
    tr = build_track_record(records, signal_version="v1")
    assert tr["signal_version"] == "v1"
    assert tr["n_records"] == 3  # v0 excluded
    assert set(tr["by_horizon"].keys()) == {"5", "20", "60"}
    h5 = tr["by_horizon"]["5"]
    assert h5["overall"]["n"] == 3
    assert h5["bullish"]["directional_n"] == 2
    # small sample -> not strong
    assert h5["overall"]["evidence_level"] in {"insufficient", "weak"}
    assert "buckets_tested" in tr["multiple_comparisons"]
    assert tr["disclaimer_zh"]


def test_build_track_record_empty():
    tr = build_track_record([], signal_version="v1")
    assert tr["n_records"] == 0
    assert tr["by_horizon"]["5"]["overall"] is None
