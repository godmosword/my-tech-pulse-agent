"""P2 — market-context flags (descriptive, never "priced in")."""

from __future__ import annotations

from agents.decision_context_builder import (
    compute_market_context_flags,
    valuation_percentile,
)


def test_above_200dma_and_near_high():
    closes = [100.0] * 200 + [150.0]  # well above the 200d mean, at the top
    ctx = compute_market_context_flags(closes)
    assert "above_200dma" in ctx.flags
    assert "near_52w_high" in ctx.flags
    assert ctx.pct_vs_200dma and ctx.pct_vs_200dma > 0


def test_below_200dma_and_near_low():
    closes = [100.0] * 200 + [50.0]
    ctx = compute_market_context_flags(closes)
    assert "below_200dma" in ctx.flags
    assert "near_52w_low" in ctx.flags


def test_post_event_excess_move():
    closes = [100, 100, 100, 100, 100, 112.0]  # +12% over 5 days
    bench = [100, 100, 100, 100, 100, 101.0]  # +1%
    ctx = compute_market_context_flags(closes, bench_closes=bench)
    assert "post_event_excess_move" in ctx.flags


def test_no_flags_when_quiet_and_no_priced_in_wording():
    closes = [100.0, 100.5, 100.2, 100.1]
    ctx = compute_market_context_flags(closes)
    assert "post_event_excess_move" not in ctx.flags
    assert all("priced" not in f for f in ctx.flags)


def test_valuation_percentile():
    history = [10, 12, 14, 16, 18, 20, 22, 24]
    assert valuation_percentile(history, 14) == 0.375  # 3 of 8 <= 14
    assert valuation_percentile([1, 2], 1) is None  # too few points


def test_empty_series():
    assert compute_market_context_flags([]).flags == []
