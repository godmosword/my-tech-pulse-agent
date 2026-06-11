#!/usr/bin/env python3
"""Offline CLI: backtest records → signal factor weight adjustment suggestions."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from backtest.weight_suggestions import (
    build_weight_suggestion_report,
    load_records,
    write_report_outputs,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECORDS = ROOT / "backtest" / "results" / "records.csv"
DEFAULT_OUT = ROOT / "backtest" / "results"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Suggest signal_config.yaml weight adjustments from backtest calibration"
    )
    parser.add_argument(
        "--records",
        default=str(DEFAULT_RECORDS),
        help="Backtest records CSV/JSON (from scripts/backtest_signal.py)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=20,
        help="Forward return horizon in trading days (default: 20)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=20,
        help="Minimum samples required before emitting suggestions (default: 20)",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="Output directory for weight_suggestions.json / .md",
    )
    parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Also print JSON report to stdout",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    records_path = Path(args.records)
    out_dir = Path(args.out)

    if not records_path.is_file():
        logging.error("Records file not found: %s", records_path)
        logging.error("Run scripts/backtest_signal.py first or pass --records")
        return 1

    try:
        records = load_records(records_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logging.error("Failed to load records: %s", exc)
        return 1

    report = build_weight_suggestion_report(
        records,
        horizon_days=args.horizon,
        min_samples=args.min_samples,
    )

    out_json = out_dir / "weight_suggestions.json"
    out_md = out_dir / "weight_suggestions.md"
    write_report_outputs(report, out_json=out_json, out_md=out_md)

    logging.info("Wrote %s", out_json)
    logging.info("Wrote %s", out_md)
    logging.info("Report status: %s — %s", report.get("status"), report.get("message"))

    if args.stdout_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
