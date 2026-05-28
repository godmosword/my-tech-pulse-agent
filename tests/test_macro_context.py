"""Tests for macro/supply-chain context (mocked, no network)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from agents.macro_context_builder import build_macro_context
from sources._cache import cache_path, cached_call
from sources.macro_fred import MacroFred


def _fred_obs(values: list[tuple[str, float]]) -> list[dict[str, Any]]:
    return [{"date": d, "value": v} for d, v in values]


def test_macro_fred_snapshot_trend_and_cpi_yoy():
    mf = MacroFred(api_key="test-key")

    def fake_latest(series_id: str, *, observations: int = 14) -> list[dict[str, Any]]:
        if series_id == "FEDFUNDS":
            return _fred_obs(
                [("2025-10-01", 4.0), ("2025-11-01", 4.2), ("2025-12-01", 4.5)]
            )
        if series_id == "CPIAUCSL":
            base = 300.0
            rows = []
            for i in range(14):
                rows.append((f"2025-{i+1:02d}-01", base + i * 0.5))
            return _fred_obs(rows)
        if series_id == "DGS10":
            return _fred_obs(
                [("2025-10-01", 4.0), ("2025-11-01", 4.1), ("2025-12-01", 4.3)]
            )
        return []

    with patch.object(mf, "series_latest", side_effect=fake_latest):
        with patch("sources.macro_fred.cached_call", side_effect=lambda _k, _t, fn: fn()):
            snap = mf.snapshot()

    assert snap["fed_funds_rate"]["trend"] == "上升"
    assert snap["treasury_10y"]["trend"] == "上升"
    assert "cpi_yoy" in snap
    assert snap["cpi_yoy"]["unit"] == "pct_yoy"
    assert isinstance(snap["cpi_yoy"]["value"], float)


def test_build_macro_context_ai_silicon_tailwind():
    fred = {
        "fed_funds_rate": {"value": 4.5, "date": "2025-12-01", "trend": "下降"},
        "cpi_yoy": {"value": 2.1, "date": "2025-12-01", "trend": "下降"},
    }
    tsm = [
        {"month": "2025-10", "yoy_pct": 5.0, "mom_pct": 1.0},
        {"month": "2025-11", "yoy_pct": 8.0, "mom_pct": 2.5},
    ]
    sia = [
        {"month": "2025-09", "sales_usd_b": 58.0, "yoy_pct": 1.0},
        {"month": "2025-10", "sales_usd_b": 59.0, "yoy_pct": 2.5},
        {"month": "2025-11", "sales_usd_b": 60.0, "yoy_pct": 4.0},
    ]
    ctx = build_macro_context(
        fred_snapshot=fred,
        tsm_rev=tsm,
        sia_sales=sia,
        asml_bookings={"quarter": "2025-Q4", "bookings_eur_b": 7.9, "trend": "上升", "as_of": "2026-01-01"},
    )
    ai = ctx["theme_bias"].get("ai_silicon")
    assert ai is not None
    assert ai["bias"] == "順風"
    joined = " ".join(ai["drivers_zh"])
    assert "SIA" in joined or "半導體" in joined
    assert "TSM" in joined


def test_build_macro_context_headwind_on_rates_and_semi_drop():
    fred = {
        "fed_funds_rate": {"value": 5.0, "date": "2025-12-01", "trend": "上升"},
        "cpi_yoy": {"value": 4.5, "date": "2025-12-01", "trend": "上升"},
    }
    sia = [
        {"month": "2025-09", "sales_usd_b": 58.0, "yoy_pct": -2.0},
        {"month": "2025-10", "sales_usd_b": 57.0, "yoy_pct": -3.0},
        {"month": "2025-11", "sales_usd_b": 56.0, "yoy_pct": -4.0},
    ]
    ctx = build_macro_context(fred_snapshot=fred, tsm_rev=[], sia_sales=sia)
    eq = ctx["theme_bias"].get("equipment")
    assert eq is not None
    assert eq["bias"] == "逆風"


def test_build_macro_context_skips_themes_without_data():
    ctx = build_macro_context(fred_snapshot={}, tsm_rev=[], sia_sales=[])
    assert ctx["theme_bias"] == {}


def test_cached_call_hits_cache_within_ttl(tmp_path: Path):
    calls = {"n": 0}

    def fetch() -> dict[str, int]:
        calls["n"] += 1
        return {"v": calls["n"]}

    key = "test_key"
    first = cached_call(key, 3600, fetch, cache_dir=tmp_path)
    second = cached_call(key, 3600, fetch, cache_dir=tmp_path)
    assert first == second == {"v": 1}
    assert calls["n"] == 1
    assert cache_path(key, cache_dir=tmp_path).is_file()


def test_build_macro_context_graceful_when_sources_empty():
    ctx = build_macro_context(fred_snapshot={}, tsm_rev=[], sia_sales=[], asml_bookings=None)
    assert "macro" in ctx
    assert "supply_chain" in ctx
    assert isinstance(ctx["theme_bias"], dict)


def test_macro_fred_no_key_returns_empty():
    mf = MacroFred(api_key="")
    assert mf.series_latest("FEDFUNDS") == []
    assert mf.snapshot() == {}
