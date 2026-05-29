#!/usr/bin/env python3
"""Build price correlation clusters for earnings watchlist (offline).

Usage:
  python scripts/build_clusters.py
  python scripts/build_clusters.py --window 90

Requires FINNHUB_API_KEY. Writes data/clusters.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

from scoring.correlation_cluster import (  # noqa: E402
    build_correlation_matrix,
    cluster_tickers,
    correlated_with,
)
from sources.finnhub_provider import FinnhubProvider  # noqa: E402
from sources.watchlist import EarningsWatchlist  # noqa: E402

logger = logging.getLogger(__name__)
OUT_PATH = ROOT / "data" / "clusters.json"


def _closes_from_candle(data: dict | None) -> list[float]:
    if not data or data.get("s") != "ok":
        return []
    closes = data.get("c") or []
    return [float(x) for x in closes if x is not None]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build correlation clusters")
    parser.add_argument("--window", type=int, default=120, help="Trading days window")
    parser.add_argument("--threshold", type=float, default=0.7, help="Cluster merge threshold")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    api_key = os.getenv("FINNHUB_API_KEY", "").strip()
    if not api_key:
        logger.error("FINNHUB_API_KEY required")
        return 1

    fh = FinnhubProvider(api_key)
    watchlist = EarningsWatchlist.load()
    tickers = watchlist.tickers()

    price_series: dict[str, list[float]] = {}
    for ticker in tickers:
        candle = fh.candle(ticker, days_back=max(args.window + 30, 180))
        closes = _closes_from_candle(candle)
        if closes:
            price_series[ticker] = closes
        else:
            logger.warning("No candle data for %s", ticker)

    corr = build_correlation_matrix(price_series, window=args.window)
    clusters = cluster_tickers(corr, corr["tickers"], threshold=args.threshold)

    correlations: dict[str, list[dict]] = {}
    for t in corr["tickers"]:
        correlations[t] = correlated_with(corr, corr["tickers"], t, top_n=8)

    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "window": args.window,
        "threshold": args.threshold,
        "tickers": corr["tickers"],
        "skipped": corr.get("skipped") or [],
        "clusters": clusters,
        "correlations": correlations,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({len(clusters)} clusters, {len(corr['tickers'])} tickers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
