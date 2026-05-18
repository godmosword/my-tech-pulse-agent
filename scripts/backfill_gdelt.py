"""Backfill historical AI / semiconductor / crypto news from GDELT 2.0 Doc API.

RSS feeds only retain the latest ~20 items, so anything older than 2-3 days
is permanently unreachable from the live source registry. GDELT is a free,
no-key archive of global news with full-text search and a date filter — good
enough to seed the Firestore archive for dates we missed.

Usage:
  # Dry run (default) — just shows what would be fetched, no LLM, no Firestore.
  python -m scripts.backfill_gdelt --start 2026-05-01 --end 2026-05-18

  # Commit run — actually scores, extracts, and writes to Firestore.
  python -m scripts.backfill_gdelt --start 2026-05-01 --end 2026-05-18 --commit

  # Single theme:
  python -m scripts.backfill_gdelt --start 2026-05-10 --end 2026-05-10 --theme crypto --commit

Notes:
  * delivered_at is set to the article's published_at converted to UTC+8 day
    boundary (so /archive day buckets match Taipei calendar).
  * Run with --commit only after the dry run looks sane. Expect Gemini cost.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import httpx

from sources.rss_fetcher import Article


GDELT_DOC_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
UTC8 = timezone(timedelta(hours=8))
TRANSIENT_GDELT_STATUS_CODES = {429, 500, 502, 503, 504}
GDELT_RETRY_DELAYS_SECONDS = (30, 60, 120)
GDELT_REQUEST_PAUSE_SECONDS = 90.0

# Per-theme query strings. GDELT supports OR / phrase quoting and `sourcelang:eng`.
# Keep queries tight: we want investment-relevant tech coverage, not academic papers.
THEME_QUERIES = {
    "ai": (
        '("artificial intelligence" OR "large language model" OR OpenAI '
        'OR Anthropic OR "AI agent" OR "generative AI" OR Nvidia OR Gemini '
        'OR Claude OR ChatGPT OR Copilot) sourcelang:eng'
    ),
    "semi": (
        '(semiconductor OR TSMC OR Nvidia OR AMD OR Intel OR ASML '
        'OR "Samsung Electronics" OR "SK Hynix" OR foundry OR "AI chip" '
        'OR "AI accelerator" OR HBM) sourcelang:eng'
    ),
    "crypto": (
        '(bitcoin OR ethereum OR "crypto market" OR stablecoin OR "spot ETF" '
        'OR Coinbase OR Binance OR DeFi OR blockchain OR Solana) sourcelang:eng'
    ),
    "combined": (
        '("artificial intelligence" OR OpenAI OR Anthropic OR Nvidia '
        'OR semiconductor OR TSMC OR ASML OR HBM OR bitcoin OR ethereum '
        'OR crypto OR stablecoin OR Coinbase) sourcelang:eng'
    ),
}

# Source allow-list. GDELT pulls from thousands of outlets; we want the same
# class of publishers as the live RSS registry (no SEO farms / press-release
# republishers / paper aggregators).
ALLOWED_DOMAINS = {
    "bloomberg.com", "reuters.com", "wsj.com", "ft.com", "nytimes.com",
    "cnbc.com", "techcrunch.com", "theverge.com", "wired.com",
    "arstechnica.com", "theinformation.com", "coindesk.com", "decrypt.co",
    "theblock.co", "axios.com", "semafor.com", "fortune.com",
    "businessinsider.com", "marketwatch.com", "barrons.com",
    "anandtech.com", "tomshardware.com", "semianalysis.com",
}


def _gdelt_window(day: datetime) -> tuple[str, str]:
    """Return (startdatetime, enddatetime) GDELT strings for a UTC+8 calendar day."""
    start_local = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC8)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    fmt = "%Y%m%d%H%M%S"
    return start_utc.strftime(fmt), end_utc.strftime(fmt)


def _domain_of(url: str) -> str:
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def fetch_gdelt_day(
    *,
    day: datetime,
    theme: str,
    max_records: int = 75,
    client: Optional[httpx.Client] = None,
) -> list[dict]:
    """Hit GDELT Doc API for one (UTC+8) day and one theme, return raw articles."""
    query = THEME_QUERIES[theme]
    start, end = _gdelt_window(day)
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "JSON",
        "maxrecords": str(max_records),
        "startdatetime": start,
        "enddatetime": end,
        "sort": "HybridRel",
    }
    owns_client = client is None
    c = client or httpx.Client(timeout=30.0)
    try:
        for attempt in range(len(GDELT_RETRY_DELAYS_SECONDS) + 1):
            try:
                resp = c.get(GDELT_DOC_ENDPOINT, params=params)
                if resp.status_code in TRANSIENT_GDELT_STATUS_CODES:
                    if attempt >= len(GDELT_RETRY_DELAYS_SECONDS):
                        resp.raise_for_status()
                    delay = GDELT_RETRY_DELAYS_SECONDS[attempt]
                    logging.warning(
                        "GDELT transient status %s; retrying in %ss",
                        resp.status_code,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                resp.raise_for_status()
                try:
                    payload = resp.json()
                except json.JSONDecodeError:
                    if attempt >= len(GDELT_RETRY_DELAYS_SECONDS):
                        raise
                    delay = GDELT_RETRY_DELAYS_SECONDS[attempt]
                    logging.warning("GDELT returned non-JSON response; retrying in %ss", delay)
                    time.sleep(delay)
                    continue
                return payload.get("articles", []) or []
            except httpx.RequestError as exc:
                if attempt >= len(GDELT_RETRY_DELAYS_SECONDS):
                    raise
                delay = GDELT_RETRY_DELAYS_SECONDS[attempt]
                logging.warning(
                    "GDELT request error %s; retrying in %ss",
                    exc.__class__.__name__,
                    delay,
                )
                time.sleep(delay)
        return []
    finally:
        if owns_client:
            c.close()


def gdelt_to_article(raw: dict, *, theme: str) -> Optional[Article]:
    """Map a GDELT ArtList record to an Article model; drop disallowed domains."""
    url = (raw.get("url") or "").strip()
    title = (raw.get("title") or "").strip()
    if not url or not title:
        return None
    domain = _domain_of(url)
    if domain not in ALLOWED_DOMAINS:
        return None
    seen_raw = raw.get("seendate") or ""
    published_at: Optional[datetime] = None
    if len(seen_raw) >= 14:
        try:
            published_at = datetime.strptime(seen_raw[:14], "%Y%m%d%H%M%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            published_at = None
    return Article(
        title=title,
        url=url,
        source=f"gdelt_{theme}",
        source_display_name=raw.get("domain") or domain,
        source_language="en",
        published_at=published_at,
        summary="",
        content="",
        label="news",
    )


def iter_days(start: datetime, end: datetime) -> Iterable[datetime]:
    cur = start
    while cur <= end:
        yield cur
        cur = cur + timedelta(days=1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="GDELT historical backfill.")
    p.add_argument("--start", required=True, help="UTC+8 start date YYYY-MM-DD.")
    p.add_argument("--end", required=True, help="UTC+8 end date YYYY-MM-DD (inclusive).")
    p.add_argument(
        "--theme",
        choices=["ai", "semi", "crypto", "combined", "all"],
        default="all",
    )
    p.add_argument("--max-per-day", type=int, default=75)
    p.add_argument(
        "--commit",
        action="store_true",
        help="Run the full pipeline (LLM extractor + Firestore archive). Default is dry-run.",
    )
    return p.parse_args()


def _dry_run_summary(articles: list[Article]) -> None:
    by_day: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    for a in articles:
        day = (a.published_at or datetime.now(timezone.utc)).astimezone(UTC8).strftime("%Y-%m-%d")
        by_day[day] = by_day.get(day, 0) + 1
        dom = _domain_of(a.url)
        by_domain[dom] = by_domain.get(dom, 0) + 1
    print(f"\n  fetched {len(articles)} candidates after domain allow-list")
    print("  by day:")
    for day in sorted(by_day):
        print(f"    {day}: {by_day[day]}")
    print("  by domain (top 15):")
    for dom, n in sorted(by_domain.items(), key=lambda kv: -kv[1])[:15]:
        print(f"    {dom}: {n}")


def _commit_pipeline(articles: list[Article]) -> None:
    """Run scorer + extractor + Firestore archive. Imports happen lazily so dry
    runs don't need google-cloud credentials."""
    from scoring.heuristic_filter import HeuristicFilter
    from scoring.scorer import Scorer
    from agents.extractor_agent import ExtractorAgent
    from scoring.memory_store import make_memory_service

    heuristic = HeuristicFilter()
    passed, dropped = heuristic.filter_articles(articles)
    print(f"  heuristic: {len(passed)} passed / {len(dropped)} dropped")

    scorer = Scorer()
    scored = scorer.filter_articles(passed)
    print(f"  scorer: {len(scored)} above threshold")

    if not scored:
        return

    extractor = ExtractorAgent()
    summaries = extractor.extract_batch([a.model_dump() for a in scored])
    print(f"  extractor: {len(summaries)} summaries")

    memory = make_memory_service()
    # Archive per-article so each row's delivered_at matches its UTC+8 publish day.
    by_day: dict[str, list] = {}
    for art, summary in zip(scored, summaries):
        pub = art.published_at or datetime.now(timezone.utc)
        key = pub.astimezone(UTC8).strftime("%Y-%m-%d")
        by_day.setdefault(key, []).append(summary)
    for day, day_summaries in sorted(by_day.items()):
        delivered_at = datetime.strptime(day, "%Y-%m-%d").replace(
            hour=8, tzinfo=UTC8
        ).astimezone(timezone.utc)
        memory.archive_summaries(day_summaries, delivered_at=delivered_at)
        print(f"  archived {len(day_summaries)} → {day}")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args()
    start = datetime.strptime(args.start, "%Y-%m-%d")
    end = datetime.strptime(args.end, "%Y-%m-%d")
    if end < start:
        print("--end must be >= --start", file=sys.stderr)
        return 2

    themes = ["ai", "semi", "crypto"] if args.theme == "all" else [args.theme]

    collected: list[Article] = []
    seen_urls: set[str] = set()
    with httpx.Client(timeout=30.0) as client:
        for day in iter_days(start, end):
            for theme in themes:
                print(f"  GDELT fetch {day.strftime('%Y-%m-%d')} theme={theme}", flush=True)
                raw_list = fetch_gdelt_day(
                    day=day,
                    theme=theme,
                    max_records=args.max_per_day,
                    client=client,
                )
                for raw in raw_list:
                    art = gdelt_to_article(raw, theme=theme)
                    if not art:
                        continue
                    if art.url in seen_urls:
                        continue
                    seen_urls.add(art.url)
                    collected.append(art)
                time.sleep(GDELT_REQUEST_PAUSE_SECONDS)

    print(f"\ntotal unique candidates after allow-list: {len(collected)}")

    if not args.commit:
        _dry_run_summary(collected)
        print("\n(dry run — re-run with --commit to score, extract, and archive)")
        return 0

    _commit_pipeline(collected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
