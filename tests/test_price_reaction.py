"""Tests for post-earnings price reaction builder (mock Finnhub, no network)."""

from __future__ import annotations

from datetime import datetime, timezone

from agents.price_reaction_builder import build_price_reaction


def _ts(date: str) -> int:
    return int(datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def _candle(dates_closes: list[tuple[str, float]]) -> dict:
    return {
        "s": "ok",
        "t": [_ts(d) for d, _ in dates_closes],
        "c": [c for _, c in dates_closes],
    }


class MockFinnhub:
    def __init__(
        self,
        candles: dict[str, dict] | None = None,
        quotes: dict[str, dict] | None = None,
    ):
        self._candles = candles or {}
        self._quotes = quotes or {}

    def candle(self, symbol: str, **kwargs) -> dict | None:
        return self._candles.get(symbol.upper())

    def quote(self, symbol: str) -> dict | None:
        return self._quotes.get(symbol.upper())


STOCK_DAYS = [
    ("2024-01-08", 100.0),
    ("2024-01-09", 102.0),
    ("2024-01-10", 105.0),
    ("2024-01-11", 110.0),
    ("2024-01-12", 108.0),
    ("2024-01-16", 115.0),
    ("2024-01-17", 120.0),
    ("2024-01-18", 118.0),
    ("2024-01-19", 125.0),
]

BENCH_DAYS = [
    ("2024-01-08", 50.0),
    ("2024-01-09", 51.0),
    ("2024-01-10", 52.0),
    ("2024-01-11", 53.0),
    ("2024-01-12", 52.5),
    ("2024-01-16", 54.0),
    ("2024-01-17", 55.0),
    ("2024-01-18", 54.5),
    ("2024-01-19", 56.0),
]


def _mock() -> MockFinnhub:
    return MockFinnhub(
        candles={
            "NVDA": _candle(STOCK_DAYS),
            "SOXX": _candle(BENCH_DAYS),
        }
    )


def test_session_pre_ref_close_prior_trading_day():
    pr = build_price_reaction(
        _mock(),
        "NVDA",
        earnings_date="2024-01-10",
        session="pre",
        headline_verdict="雙擊",
    )
    assert pr.ref_close == 102.0
    assert pr.ret_1d_pct == round(((105.0 - 102.0) / 102.0) * 100, 2)
    assert pr.ret_5d_pct == round(((120.0 - 102.0) / 102.0) * 100, 2)


def test_session_post_ref_close_on_earnings_day():
    pr = build_price_reaction(
        _mock(),
        "NVDA",
        earnings_date="2024-01-10",
        session="post",
        headline_verdict="雙擊",
    )
    assert pr.ref_close == 105.0
    assert pr.ret_1d_pct == round(((110.0 - 105.0) / 105.0) * 100, 2)


def test_quadrant_label_beat_positive_excess():
    pr = build_price_reaction(
        _mock(),
        "NVDA",
        earnings_date="2024-01-10",
        session="post",
        headline_verdict="雙擊",
    )
    assert pr.excess_1d_pct is not None and pr.excess_1d_pct > 0
    assert pr.reaction_label == "確認上漲"


def test_quadrant_label_beat_negative_excess():
    flat_stock = [(d, 100.0) for d, _ in STOCK_DAYS]
    rising_bench = list(BENCH_DAYS)
    rising_bench[3] = ("2024-01-11", 70.0)
    fh = MockFinnhub(
        candles={"NVDA": _candle(flat_stock), "SOXX": _candle(rising_bench)}
    )
    pr = build_price_reaction(
        fh,
        "NVDA",
        earnings_date="2024-01-10",
        session="post",
        headline_verdict="雙擊",
    )
    assert pr.excess_1d_pct is not None and pr.excess_1d_pct < 0
    assert pr.reaction_label == "利多不漲"


def test_quadrant_label_miss_positive_excess():
    mild_stock = list(STOCK_DAYS)
    mild_stock[3] = ("2024-01-11", 100.0)
    weak_bench = list(BENCH_DAYS)
    weak_bench[3] = ("2024-01-11", 45.0)
    fh = MockFinnhub(
        candles={"NVDA": _candle(mild_stock), "SOXX": _candle(weak_bench)}
    )
    pr = build_price_reaction(
        fh,
        "NVDA",
        earnings_date="2024-01-10",
        session="post",
        headline_verdict="雙殺",
    )
    assert pr.excess_1d_pct is not None and pr.excess_1d_pct > 0
    assert pr.reaction_label == "利空出盡"


def test_quadrant_label_miss_negative_excess():
    weak_stock = list(STOCK_DAYS)
    weak_stock[3] = ("2024-01-11", 80.0)
    mild_bench = list(BENCH_DAYS)
    mild_bench[3] = ("2024-01-11", 51.5)
    fh = MockFinnhub(
        candles={"NVDA": _candle(weak_stock), "SOXX": _candle(mild_bench)}
    )
    pr = build_price_reaction(
        fh,
        "NVDA",
        earnings_date="2024-01-10",
        session="post",
        headline_verdict="雙殺",
    )
    assert pr.excess_1d_pct is not None and pr.excess_1d_pct < 0
    assert pr.reaction_label == "確認下跌"


def test_excess_equals_stock_minus_bench():
    pr = build_price_reaction(
        _mock(),
        "NVDA",
        earnings_date="2024-01-10",
        session="post",
        headline_verdict="雙擊",
    )
    assert pr.ret_1d_pct is not None and pr.bench_ret_1d_pct is not None
    assert pr.excess_1d_pct == round(pr.ret_1d_pct - pr.bench_ret_1d_pct, 2)


def test_missing_candle_degraded_no_exception():
    fh = MockFinnhub(candles={}, quotes={"NVDA": {"c": 130.0}})
    pr = build_price_reaction(
        fh,
        "NVDA",
        earnings_date="2024-01-10",
        session="post",
        headline_verdict="雙擊",
    )
    assert pr.degraded is True
    assert pr.reaction_label in ("資料不足", "中性", "利多不漲", "確認上漲")
