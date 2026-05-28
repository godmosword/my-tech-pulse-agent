"""Append-only live signal log for forward validation (not backtest)."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from agents.earnings_models import EarningsReport
from backtest.metrics import evaluate, forward_return
from backtest.pit_data import first_trading_day_after

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path(__file__).resolve().parent / "decision_log.jsonl"


def _log_path(path: Path | None) -> Path:
    return path or DEFAULT_LOG_PATH


def log_live_signal(
    report: EarningsReport,
    *,
    log_path: Path | None = None,
    finnhub: Any | None = None,
) -> None:
    """Persist one pipeline investment_signal row for later forward validation."""
    sig = report.investment_signal
    if not sig or sig.score is None:
        return

    filed = None
    if report.filed_at:
        filed = report.filed_at.strftime("%Y-%m-%d")
    elif report.market_context and report.market_context.earnings_date:
        filed = str(report.market_context.earnings_date)[:10]

    decision_date = None
    if finnhub and filed:
        decision_date = first_trading_day_after(finnhub, report.ticker, from_date=filed)
    if not decision_date and report.market_context and report.market_context.earnings_date:
        decision_date = str(report.market_context.earnings_date)[:10]

    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ticker": report.ticker,
        "report_id": report.report_id,
        "period": report.quarter_label,
        "filed": filed,
        "score": sig.score,
        "rating": sig.rating,
        "conviction": sig.conviction,
        "decision_date": decision_date,
    }

    path = _log_path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_log(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def evaluate_live_log(
    *,
    finnhub: Any,
    as_of: str | None = None,
    log_path: Path | None = None,
    horizons: tuple[int, ...] = (5, 20, 60),
) -> dict[str, Any]:
    """Evaluate forward returns for logged signals whose horizons have elapsed."""
    as_of_day = (as_of or date.today().isoformat())[:10]
    path = _log_path(log_path)
    raw = _load_log(path)
    enriched: list[dict[str, Any]] = []

    for row in raw:
        decision = row.get("decision_date")
        if not decision:
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        returns: dict[str, Any] = {}
        for h in horizons:
            fr = forward_return(finnhub, ticker, decision_date=decision, horizon_days=h)
            if fr.get("excess_return_pct") is not None:
                returns[f"excess_{h}d"] = fr["excess_return_pct"]
                returns[f"return_{h}d"] = fr.get("return_pct")
        if not returns:
            continue
        enriched.append({**row, "returns": returns, "evaluated_as_of": as_of_day})

    summary = evaluate(enriched, horizons=horizons) if enriched else {"n_records": 0}
    return {
        "as_of": as_of_day,
        "n_logged": len(raw),
        "n_evaluated": len(enriched),
        "records": enriched,
        "summary": summary,
    }
