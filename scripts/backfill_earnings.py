#!/usr/bin/env python3
"""Backfill earnings reports for a filed-date range (watchlist tickers).

Reads SEC submissions per CIK, builds earnings_v2 reports from XBRL, writes
tech_pulse_earnings_reports and memory_items (kind=earnings).

Usage:
  # Dry-run: list filings that would be processed
  python scripts/backfill_earnings.py --since 2026-05-01 --until 2026-05-21 --dry-run

  # Write to Firestore (requires ADC / service account)
  python scripts/backfill_earnings.py --since 2026-05-01 --until 2026-05-21

  # Optional: run Gemini narrative on each filing (slow, costs API)
  python scripts/backfill_earnings.py --since 2026-05-01 --until 2026-05-21 --with-llm

Env: SEC_USER_AGENT, FIRESTORE_* , GEMINI_API_KEY (if --with-llm)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

from agents.earnings_agent import EarningsAgent  # noqa: E402
from pipeline.earnings_pipeline import build_report_from_filing  # noqa: E402
from scoring.earnings_report_store import make_earnings_report_store  # noqa: E402
from scoring.memory_store import make_memory_service  # noqa: E402
from sources.sec_client import SecClient  # noqa: E402
from sources.sec_submissions import SecSubmissionsClient  # noqa: E402
from sources.sec_xbrl_fetcher import SecXbrlFetcher  # noqa: E402
from sources.ticker_cik_map import TickerCikMap  # noqa: E402
from sources.watchlist import EarningsWatchlist  # noqa: E402

logger = logging.getLogger(__name__)


def _parse_date_arg(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _in_range(dt: datetime, since: date, until: date) -> bool:
    d = dt.astimezone(timezone.utc).date()
    return since <= d <= until


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill earnings by SEC filed date range")
    parser.add_argument("--since", type=_parse_date_arg, default=_parse_date_arg("2026-05-01"))
    parser.add_argument("--until", type=_parse_date_arg, default=_parse_date_arg("2026-05-21"))
    parser.add_argument("--dry-run", action="store_true", help="List filings only, no writes")
    parser.add_argument("--with-llm", action="store_true", help="Run EarningsAgent for quotes (slow)")
    parser.add_argument(
        "--tickers",
        default="",
        help="Comma-separated tickers (default: full watchlist)",
    )
    parser.add_argument("--max-filings", type=int, default=0, help="Cap total filings (0=no cap)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    watchlist = EarningsWatchlist.load()
    cik_map = TickerCikMap.load(watchlist=watchlist)
    sec = SecClient()
    submissions = SecSubmissionsClient(sec)
    xbrl = SecXbrlFetcher(sec)

    tickers = (
        [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        if args.tickers
        else watchlist.tickers()
    )

    store = None if args.dry_run else make_earnings_report_store()
    memory = None if args.dry_run else make_memory_service()
    agent = EarningsAgent() if args.with_llm else None
    fetcher = None
    if args.with_llm:
        from sources.earnings_fetcher import EarningsFetcher  # noqa: E402

        fetcher = EarningsFetcher()

    seen_reports: set[str] = set()
    saved = 0
    skipped = 0
    filings_seen = 0

    for ticker in tickers:
        cik = cik_map.cik_for(ticker)
        if not cik:
            logger.warning("Skip %s: no CIK", ticker)
            continue

        sub_payload = submissions.get_submissions(cik)
        company = str(sub_payload.get("name") or ticker)
        filings = submissions.list_filings_in_range(
            ticker=ticker,
            company=company,
            cik=cik,
            since=args.since,
            until=args.until,
        )
        if not filings:
            logger.info("%s: no filings in range", ticker)
            continue

        logger.info("%s: %d filing(s) in %s..%s", ticker, len(filings), args.since, args.until)

        try:
            company_facts = xbrl.get_company_facts(cik)
        except Exception as exc:
            logger.error("%s: companyfacts failed: %s", ticker, exc)
            continue

        tier = watchlist.tier(ticker)

        for sub in filings:
            if args.max_filings and filings_seen >= args.max_filings:
                logger.info("max-filings cap reached")
                return 0
            filings_seen += 1

            filing = submissions.to_earnings_filing(sub)
            if args.dry_run:
                print(
                    f"  [dry-run] {ticker} {filing.form_type} filed={filing.filed_at.date()} "
                    f"acc={filing.accession} {filing.filing_url[:80]}"
                )
                continue

            report = build_report_from_filing(
                filing,
                ticker=ticker,
                cik=cik,
                tier=tier,
                company_facts=company_facts,
                xbrl=xbrl,
            )
            if not report:
                skipped += 1
                logger.warning("%s %s: no XBRL report built", ticker, filing.accession)
                continue

            if not _in_range(report.published_at, args.since, args.until):
                skipped += 1
                continue

            if report.report_id in seen_reports:
                logger.debug("Skip duplicate report_id %s", report.report_id)
                continue
            seen_reports.add(report.report_id)

            if agent and fetcher:
                filing = fetcher.enrich_with_text(filing)
                llm_out = agent.extract(filing)
                if llm_out:
                    report.key_quotes = llm_out.key_quotes

            store.save(report)
            memory.archive_earnings_report(report, delivered_at=report.published_at)
            saved += 1
            logger.info(
                "Saved %s | %s | published=%s",
                report.report_id,
                report.quarter_label,
                report.published_at.date(),
            )

    if args.dry_run:
        print(f"\nDry-run: {filings_seen} filing(s) across {len(tickers)} ticker(s)")
        return 0

    print(f"\nDone: saved={saved} skipped={skipped} filings_seen={filings_seen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
