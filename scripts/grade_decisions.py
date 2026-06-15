#!/usr/bin/env python3
"""Grade logged live signals and emit an honest track record (Phase 0).

Reads the append-only decision log, computes realized forward *excess* returns
for matured signals (strict point-in-time via backtest.pit_data), then builds a
calibration/disclosure track record: hit rate + Wilson CI, mean excess +
bootstrap CI, IC, effective-independent-sample estimate, multiple-comparisons
note, and an ``evidence_level`` per bucket. Survivorship coverage is disclosed.

This produces metrics ONLY — it never rewrites the signal's ``conviction``.

Usage:
  python scripts/grade_decisions.py --dry-run
  python scripts/grade_decisions.py --as-of 2026-06-15
  python scripts/grade_decisions.py --signal-version v1 --out backtest/results/track_record.json

Requires FINNHUB_API_KEY (forward returns need price candles).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

from backtest.decision_log import DEFAULT_LOG_PATH, evaluate_live_log  # noqa: E402
from backtest.universe import survivorship_status  # noqa: E402
from scoring.signal_engine import load_signal_config  # noqa: E402
from scoring.track_record import build_track_record  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_OUT = ROOT / "backtest" / "results" / "track_record.json"


def _maturity_breakdown(
    raw: list[dict], evaluated_ids: set[str], *, as_of: str, min_horizon: int
) -> dict[str, int]:
    """Classify why un-evaluated rows produced no return (disclosure, not error)."""
    as_of_day = date.fromisoformat(as_of[:10])
    counts = {"no_decision_date": 0, "immature": 0, "missing_prices": 0}
    for row in raw:
        rid = str(row.get("report_id") or row.get("ts") or "")
        if rid in evaluated_ids:
            continue
        decision = row.get("decision_date")
        if not decision:
            counts["no_decision_date"] += 1
            continue
        try:
            elapsed = (as_of_day - date.fromisoformat(str(decision)[:10])).days
        except ValueError:
            counts["no_decision_date"] += 1
            continue
        # Approx trading days ~ calendar * 5/7; immature if shortest horizon unmet.
        if elapsed * 5 / 7 < min_horizon:
            counts["immature"] += 1
        else:
            counts["missing_prices"] += 1
    return counts


def run(*, as_of: str, signal_version: str, out: Path, dry_run: bool) -> dict:
    from sources.finnhub_provider import FinnhubProvider  # noqa: PLC0415

    api_key = os.getenv("FINNHUB_API_KEY", "")
    if not api_key:
        raise SystemExit("FINNHUB_API_KEY required for forward returns")
    finnhub = FinnhubProvider(api_key)

    horizons = (5, 20, 60)
    evald = evaluate_live_log(finnhub=finnhub, as_of=as_of, horizons=horizons)
    records = evald["records"]
    evaluated_ids = {str(r.get("report_id") or r.get("ts") or "") for r in records}

    from backtest.decision_log import _load_log  # noqa: PLC0415

    raw = _load_log(DEFAULT_LOG_PATH)
    maturity = _maturity_breakdown(
        raw, evaluated_ids, as_of=as_of, min_horizon=min(horizons)
    )

    track = build_track_record(
        records, horizons=horizons, signal_version=signal_version
    )
    survivorship = survivorship_status(
        [r.get("decision_date") for r in records if r.get("decision_date")]
    )

    report = {
        "as_of": as_of,
        "signal_version": signal_version,
        "n_logged": evald["n_logged"],
        "n_evaluated": evald["n_evaluated"],
        "maturity_breakdown": maturity,
        "survivorship": survivorship,
        "track_record": track,
    }

    if dry_run:
        logger.info("dry-run: %s", json.dumps(report, ensure_ascii=False)[:600])
        return report

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Wrote %s (logged=%d evaluated=%d version=%s)",
        out,
        evald["n_logged"],
        evald["n_evaluated"],
        signal_version,
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument(
        "--signal-version",
        default=None,
        help="Only grade this signal version (default: current config version)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    version = args.signal_version or str(load_signal_config().get("version") or "v1")
    run(as_of=args.as_of, signal_version=version, out=args.out, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
