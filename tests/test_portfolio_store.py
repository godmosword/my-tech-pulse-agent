"""Tests for portfolio config store and IBKR Flex import parsing."""

from __future__ import annotations

import textwrap
from pathlib import Path

import yaml

from sources.portfolio import Portfolio, theme_for
from sources.watchlist import EarningsWatchlist

FIXTURE_FLEX = Path(__file__).parent / "fixtures" / "ibkr_flex_open_positions.xml"


def test_portfolio_load_missing_file_returns_empty(tmp_path: Path):
    pf = Portfolio.load(tmp_path / "missing.yaml")
    assert pf.positions == []
    assert pf.target_allocation == {}


def test_theme_for_uses_first_watchlist_tag():
    wl = EarningsWatchlist.load()
    assert theme_for("NVDA", wl) == "ai_silicon"
    assert theme_for("MU", wl) == "memory"
    assert theme_for("ZZZZ", wl) == "other"


def test_ibkr_flex_parse_aggregates_shares_and_cost():
    from scripts.import_ibkr_portfolio import build_yaml_payload, parse_open_positions

    xml_text = FIXTURE_FLEX.read_text(encoding="utf-8")
    positions = parse_open_positions(xml_text)
    by_ticker = {p["ticker"]: p for p in positions}
    assert by_ticker["NVDA"]["shares"] == 150.0
    assert abs(by_ticker["NVDA"]["avg_cost"] - 113.3333) < 0.01
    assert by_ticker["MU"]["shares"] == 200.0
    assert by_ticker["MU"]["avg_cost"] == 95.0


def test_ibkr_import_preserves_target_allocation(tmp_path: Path):
    from scripts.import_ibkr_portfolio import build_yaml_payload, parse_open_positions

    path = tmp_path / "portfolio.yaml"
    path.write_text(
        textwrap.dedent(
            """
            base_currency: USD
            as_of: "2026-01-01"
            positions:
              - { ticker: OLD, shares: 1, avg_cost: 1.0 }
            target_allocation:
              ai_silicon: 0.40
              memory: 0.15
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    existing = Portfolio.load(path)
    positions = parse_open_positions(FIXTURE_FLEX.read_text(encoding="utf-8"))
    payload = build_yaml_payload(positions, existing)
    assert payload["target_allocation"] == {"ai_silicon": 0.40, "memory": 0.15}
    assert payload["positions"][0]["ticker"] == "MU" or any(
        p["ticker"] == "NVDA" for p in payload["positions"]
    )
