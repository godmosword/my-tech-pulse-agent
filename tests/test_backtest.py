"""Tests for point-in-time backtest (mocked, no network)."""

from __future__ import annotations

from typing import Any

import pytest

from backtest.metrics import evaluate, forward_return
from backtest.pit_data import (
    candle_series,
    price_after,
    reconstruct_company_facts_asof,
    return_between,
)


def _sample_company_facts() -> dict[str, Any]:
    return {
        "cik": "1045810",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "end": "2023-01-29",
                                "val": 10.0,
                                "fy": 2023,
                                "fp": "Q4",
                                "filed": "2023-02-24",
                                "form": "10-K",
                            },
                            {
                                "end": "2024-01-28",
                                "val": 20.0,
                                "fy": 2024,
                                "fp": "Q4",
                                "filed": "2024-02-21",
                                "form": "10-K",
                            },
                        ]
                    }
                }
            }
        },
    }


def test_reconstruct_company_facts_asof_filters_future_filed():
    facts = _sample_company_facts()
    pit = reconstruct_company_facts_asof(facts, asof_filed_date="2023-06-01")
    entries = pit["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    assert len(entries) == 1
    assert entries[0]["filed"] == "2023-02-24"
    assert entries[0]["val"] == 10.0

    # Future filing must not appear when asof is before it
    assert all(e["filed"] <= "2023-06-01" for e in entries)


class _MockFinnhub:
    def __init__(self, series: list[tuple[str, float]]):
        self._series = series

    def candle(self, symbol: str, **kwargs: Any) -> dict[str, Any]:
        del symbol, kwargs
        ts = []
        closes = []
        from datetime import datetime, timezone

        for day, close in self._series:
            ts.append(int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()))
            closes.append(close)
        return {"s": "ok", "t": ts, "c": closes}


def test_forward_return_and_price_after():
    stock = [
        ("2024-01-02", 100.0),
        ("2024-01-03", 102.0),
        ("2024-01-04", 104.0),
        ("2024-01-05", 110.0),
    ]
    bench = [
        ("2024-01-02", 200.0),
        ("2024-01-03", 201.0),
        ("2024-01-04", 202.0),
        ("2024-01-05", 204.0),
    ]

    class _DualFinnhub:
        def candle(self, symbol: str, **kwargs: Any) -> dict[str, Any]:
            series = stock if symbol == "NVDA" else bench
            return _MockFinnhub(series).candle(symbol, **kwargs)

    fh = _DualFinnhub()
    assert price_after(fh, "NVDA", from_date="2024-01-02", trading_days=4) == 110.0

    fr = forward_return(fh, "NVDA", decision_date="2024-01-02", horizon_days=3)
    assert fr["return_pct"] == pytest.approx(10.0, abs=0.01)
    assert fr["bench_return_pct"] == pytest.approx(2.0, abs=0.01)
    assert fr["excess_return_pct"] == pytest.approx(8.0, abs=0.01)


def test_evaluate_positive_ic_and_quantile_spread():
    records = []
    for i, score in enumerate([90, 80, 70, 40, 30, 20]):
        records.append(
            {
                "score": float(score),
                "rating": "看多" if score >= 60 else "看空",
                "returns": {"excess_5d": float(score - 50) * 0.5},
            }
        )
    summary = evaluate(records, horizons=(5,))
    assert summary["ic"]["5"]["spearman"] is not None
    assert summary["ic"]["5"]["spearman"] > 0.5
    assert summary["quantile_spread"]["5"]["spread_pct"] > 0
    assert summary["hit_rate"]["5"]["rate"] == 1.0


def test_evaluate_random_data_ic_near_zero():
    import random

    random.seed(42)
    records = []
    ratings = ["看多", "看空", "中性"]
    for _ in range(40):
        records.append(
            {
                "score": random.uniform(20, 90),
                "rating": random.choice(ratings),
                "returns": {"excess_5d": random.uniform(-5, 5)},
            }
        )
    summary = evaluate(records, horizons=(5,))
    ic = summary["ic"]["5"]["spearman"]
    assert ic is not None
    assert abs(ic) < 0.35


def test_evaluate_sample_warnings_when_n_below_20():
    records = [
        {"score": 80.0, "rating": "強力看多", "returns": {"excess_5d": 1.0}}
        for _ in range(5)
    ]
    summary = evaluate(records, horizons=(5,), min_bucket_n=20)
    assert summary["sample_warnings"]
    assert summary["by_rating"]["5"]["強力看多"]["insufficient_sample"] is True


def test_candle_series_empty_on_bad_status():
    assert candle_series({"s": "no_data"}) == []


def test_return_between_none_when_insufficient_sessions():
    fh = _MockFinnhub([("2024-01-02", 100.0)])
    assert return_between(fh, "X", start_date="2024-01-02", horizon_trading_days=5) is None
