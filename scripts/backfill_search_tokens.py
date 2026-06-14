#!/usr/bin/env python3
"""Backfill the additive ``search_tokens`` field on tech_pulse_memory_items.

New deliveries get ``search_tokens`` written automatically by the pipeline
(scoring/memory_store.py). This script populates the field on documents that
predate that change, so the dashboard keyword search can find them.

Idempotent: by default it skips documents whose stored tokens already match the
freshly computed tokens, so re-running only writes what actually changed.

Usage:
  python scripts/backfill_search_tokens.py --dry-run
  python scripts/backfill_search_tokens.py --limit 500
  python scripts/backfill_search_tokens.py --force      # recompute every doc

Requires Firestore credentials (ADC or FIRESTORE_PROJECT_ID / FIRESTORE_DATABASE).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv()

from scoring.search_tokens import search_tokens_for_payload  # noqa: E402

logger = logging.getLogger(__name__)

COLLECTION_SUFFIX = "memory_items"
PAGE_SIZE = 500


def _collection_name() -> str:
    prefix = os.getenv("FIRESTORE_COLLECTION_PREFIX", "tech_pulse").strip("_")
    override = os.getenv("TECH_PULSE_FIRESTORE_COLLECTION", "").strip()
    if override:
        return override
    return f"{prefix}_{COLLECTION_SUFFIX}"


def run_backfill(*, limit: int | None, dry_run: bool, force: bool) -> int:
    from google.cloud import firestore  # noqa: PLC0415

    db = firestore.Client(
        project=os.getenv("FIRESTORE_PROJECT_ID") or None,
        database=os.getenv("FIRESTORE_DATABASE") or None,
    )
    collection = db.collection(_collection_name())

    scanned = 0
    updated = 0
    skipped = 0
    cursor = None

    while True:
        query = collection.order_by("__name__").limit(PAGE_SIZE)
        if cursor is not None:
            query = query.start_after({"__name__": cursor})
        page = list(query.stream())
        if not page:
            break

        batch = db.batch()
        pending = 0
        for doc in page:
            scanned += 1
            cursor = doc.id
            data = doc.to_dict() or {}
            tokens = search_tokens_for_payload(data)
            existing = list(data.get("search_tokens") or [])
            if not force and existing == tokens:
                skipped += 1
                continue
            if dry_run:
                updated += 1
                continue
            batch.set(doc.reference, {"search_tokens": tokens}, merge=True)
            pending += 1
            updated += 1
            if pending >= PAGE_SIZE:
                batch.commit()
                batch = db.batch()
                pending = 0

        if pending and not dry_run:
            batch.commit()

        if limit is not None and scanned >= limit:
            break
        if len(page) < PAGE_SIZE:
            break

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
    parser.add_argument("--limit", type=int, default=None, help="Max docs to scan")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    parser.add_argument(
        "--force", action="store_true", help="Rewrite tokens even if unchanged"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run_backfill(limit=args.limit, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
