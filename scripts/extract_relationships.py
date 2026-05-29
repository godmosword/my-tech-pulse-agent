#!/usr/bin/env python3
"""Offline 10-K business relationship extraction for watchlist tickers.

Usage:
  python scripts/extract_relationships.py --dry-run
  python scripts/extract_relationships.py --tickers NVDA,TSM
  python scripts/extract_relationships.py --force

Writes data/relationships/{TICKER}.json (does not touch online pipeline).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

from agents.relationship_extractor import extract_relationships  # noqa: E402
from sources.sec_client import SecClient  # noqa: E402
from sources.sec_submissions import SecSubmissionsClient  # noqa: E402
from sources.tenk_fetcher import fetch_latest_10k  # noqa: E402
from sources.ticker_cik_map import TickerCikMap  # noqa: E402
from sources.watchlist import EarningsWatchlist  # noqa: E402

logger = logging.getLogger(__name__)
OUT_DIR = ROOT / "data" / "relationships"


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract 10-K business relationships")
    parser.add_argument("--tickers", default="", help="Comma-separated tickers")
    parser.add_argument("--dry-run", action="store_true", help="Process 2-3 tickers only, no writes")
    parser.add_argument("--force", action="store_true", help="Re-extract even if JSON exists")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    watchlist = EarningsWatchlist.load()
    cik_map = TickerCikMap.load(watchlist=watchlist)
    submissions = SecSubmissionsClient(SecClient())

    tickers = (
        [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        if args.tickers
        else watchlist.tickers()
    )
    if args.dry_run:
        tickers = tickers[:3]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0

    for ticker in tickers:
        out_path = OUT_DIR / f"{ticker}.json"
        if out_path.is_file() and not args.force and not args.dry_run:
            logger.info("Skip %s (exists, use --force)", ticker)
            continue

        cik = cik_map.cik_for(ticker)
        if not cik:
            logger.warning("Skip %s: no CIK", ticker)
            continue

        sub_payload = submissions.get_submissions(cik)
        company = str(sub_payload.get("name") or ticker)
        text, meta = fetch_latest_10k(
            ticker=ticker,
            company=company,
            cik=cik,
            submissions=submissions,
        )
        if not text:
            logger.warning("%s: no 10-K text", ticker)
            continue

        rel = extract_relationships(
            ticker,
            tenk_text=text,
            fiscal_year=meta.get("fiscal_year"),
            filed=meta.get("filed"),
        )

        if args.dry_run:
            print(
                f"  [dry-run] {ticker} edges={len(rel.edges)} filed={meta.get('filed')} "
                f"sample={[e.counterparty_name for e in rel.edges[:3]]}"
            )
            continue

        out_path.write_text(
            json.dumps(rel.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        saved += 1
        logger.info("Wrote %s (%d edges)", out_path, len(rel.edges))

    if args.dry_run:
        print(f"\nDry-run complete for {len(tickers)} ticker(s)")
        return 0

    print(f"\nDone: saved={saved} as_of={datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
