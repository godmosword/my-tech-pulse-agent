#!/usr/bin/env python3
"""Offline CLI: audit config/earnings_watchlist.yaml coverage (read-only).

Examples:
  python scripts/watchlist_coverage.py
  python scripts/watchlist_coverage.py --tickers NVDA,FOO,BAR
  python scripts/watchlist_coverage.py --observed seen_tickers.csv --targets targets.json
  python scripts/watchlist_coverage.py --format json --out backtest/results/watchlist_coverage.json

Candidates come only from the supplied --observed / --tickers data (real
observations); the script never invents tickers and never edits the watchlist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sources.watchlist import WATCHLIST_PATH  # noqa: E402
from sources.watchlist_audit import (  # noqa: E402
    coverage_report,
    format_report_md,
    load_observed,
    load_raw_entries,
    load_targets,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit earnings watchlist coverage (read-only).")
    parser.add_argument("--watchlist", type=Path, default=WATCHLIST_PATH)
    parser.add_argument(
        "--observed",
        type=Path,
        default=None,
        help="CSV (ticker/symbol column) or JSON list of observed tickers.",
    )
    parser.add_argument(
        "--tickers",
        default=None,
        help="Comma-separated observed tickers for ad-hoc use (merged with --observed).",
    )
    parser.add_argument(
        "--targets",
        type=Path,
        default=None,
        help='JSON of per-tier targets, e.g. {"3": 10, "5": 10}. Sole target source (comments not parsed).',
    )
    parser.add_argument("--out", type=Path, default=None, help="Write to file instead of stdout.")
    parser.add_argument("--format", choices=("md", "json"), default="md")
    args = parser.parse_args(argv)

    try:
        entries = load_raw_entries(args.watchlist)
    except (OSError, ValueError) as exc:
        print(f"error: failed to load watchlist {args.watchlist}: {exc}", file=sys.stderr)
        return 1

    observed: list[str] | None = None
    if args.observed is not None or args.tickers:
        observed = []
        if args.observed is not None:
            try:
                observed.extend(load_observed(args.observed))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                print(f"error: failed to load observed {args.observed}: {exc}", file=sys.stderr)
                return 1
        if args.tickers:
            observed.extend(t for t in (x.strip() for x in args.tickers.split(",")) if t)

    targets = None
    if args.targets is not None:
        try:
            targets = load_targets(args.targets)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: failed to load targets {args.targets}: {exc}", file=sys.stderr)
            return 1

    report = coverage_report(entries, observed=observed, targets=targets)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json" else format_report_md(report)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + ("\n" if not rendered.endswith("\n") else ""), encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
