"""Phase-0 decision-log schema: signal_version / factor_set / benchmark."""

from __future__ import annotations

import json
from pathlib import Path

from agents.earnings_v3_models import InvestmentSignal, SignalFactor
from backtest.decision_log import _factor_payload, log_live_signal


class _Report:
    """Minimal stand-in for EarningsReport for logging (only fields read)."""

    def __init__(self, signal: InvestmentSignal):
        self.investment_signal = signal
        self.ticker = "NVDA"
        self.report_id = "nvda-2026q1"
        self.quarter_label = "FY26 Q1"
        self.filed_at = None
        self.market_context = type("MC", (), {"earnings_date": "2026-05-01"})()


def _signal() -> InvestmentSignal:
    return InvestmentSignal(
        score=72.0,
        rating="看多",
        conviction="medium",
        factors=[
            SignalFactor(name="fundamental_momentum", score=80.0, available=True),
            SignalFactor(name="surprise", score=60.0, available=True),
            SignalFactor(name="market_confirmation", available=False),
            SignalFactor(name="quality", score=None, available=True),
        ],
    )


def test_factor_payload_lists_only_scored_available():
    factor_set, detail = _factor_payload(_signal())
    assert factor_set == ["fundamental_momentum", "surprise"]
    assert detail["market_confirmation"]["available"] is False
    assert detail["quality"]["score"] is None


def test_log_row_has_phase0_fields(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    log_live_signal(_Report(_signal()), log_path=log_path)
    rows = [json.loads(line) for line in log_path.read_text().splitlines() if line]
    assert len(rows) == 1
    row = rows[0]
    assert row["signal_version"]  # non-empty
    assert row["factor_set"] == ["fundamental_momentum", "surprise"]
    assert row["benchmark"] == "SOXX"
    assert row["universe_asof"] == "live"
    # backward-compatible core fields still present
    assert row["ticker"] == "NVDA" and row["rating"] == "看多"


def test_no_signal_does_not_log(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    log_live_signal(_Report(InvestmentSignal()), log_path=log_path)  # score is None
    assert not log_path.exists()
