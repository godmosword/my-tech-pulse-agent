#!/usr/bin/env python3
"""Backfill the additive ``search_tokens`` field on memory_items.json.

Usage:
  python scripts/backfill_search_tokens.py --dry-run
  python scripts/backfill_search_tokens.py --limit 500
  python scripts/backfill_search_tokens.py --force
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

from scoring.json_io import memory_items_path, read_json_list, write_json  # noqa: E402
from scoring.search_tokens import search_tokens_for_payload  # noqa: E402

logger = logging.getLogger(__name__)


def run_backfill(*, limit: int | None, dry_run: bool, force: bool) -> int:
    path = memory_items_path()
    rows = read_json_list(path)
    scanned = 0
    updated = 0
    skipped = 0
    for data in rows:
        scanned += 1
        if limit is not None and scanned > limit:
            break
        tokens = search_tokens_for_payload(data)
        existing = list(data.get("search_tokens") or [])
        if not force and existing == tokens:
            skipped += 1
            continue
        updated += 1
        if not dry_run:
            data["search_tokens"] = tokens

    if not dry_run and updated:
        write_json(path, rows)

    logger.info(
        "search_tokens backfill: scanned=%d updated=%d skipped=%d%s",
        scanned,
        updated,
        skipped,
        " (dry-run)" if dry_run else "",
    )
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_backfill(limit=args.limit, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
