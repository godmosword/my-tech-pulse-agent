#!/usr/bin/env python3
"""Backfill Traditional Chinese fields on existing tech_pulse_memory_items.

Re-runs ExtractorAgent on stored English fields when zh_summary or zh_title
is missing. Requires GEMINI_API_KEY and Firestore credentials.

Usage:
  python scripts/backfill_zh_fields.py --dry-run --limit 8
  python scripts/backfill_zh_fields.py --limit 8 --max-updates 6

Fetches recent docs in one Firestore query (no long-lived stream during Gemini calls).
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

from agents.extractor_agent import ExtractorAgent  # noqa: E402
from llm.localization import derive_zh_title, has_cjk  # noqa: E402
from scoring.memory_store import _item_id  # noqa: E402

logger = logging.getLogger(__name__)

COLLECTION_SUFFIX = "memory_items"


def _collection_name() -> str:
    prefix = os.getenv("FIRESTORE_COLLECTION_PREFIX", "tech_pulse").strip("_")
    override = os.getenv("TECH_PULSE_FIRESTORE_COLLECTION", "").strip()
    if override:
        return override
    return f"{prefix}_{COLLECTION_SUFFIX}"


def _needs_backfill(data: dict) -> bool:
    zh_title = (data.get("zh_title") or "").strip()
    zh_summary = (data.get("zh_summary") or "").strip()
    zh_body = (data.get("zh_body") or "").strip()
    if zh_summary and zh_title and has_cjk(zh_title):
        return False
    if zh_summary and has_cjk(zh_summary) and not zh_title:
        return True
    if not zh_summary and not zh_body:
        return True
    return not has_cjk(zh_summary) and not has_cjk(zh_body)


def _should_replace_zh_field(existing: str, new_value: str | None) -> bool:
    new = (new_value or "").strip()
    if not new or not has_cjk(new):
        return False
    old = (existing or "").strip()
    return not old or not has_cjk(old)


def _patch_from_extraction(data: dict, extracted) -> dict:
    patch: dict = {}
    if _should_replace_zh_field(data.get("zh_summary") or "", extracted.zh_summary):
        patch["zh_summary"] = extracted.zh_summary
    if _should_replace_zh_field(data.get("zh_body") or "", extracted.zh_body):
        patch["zh_body"] = extracted.zh_body
    if _should_replace_zh_field(data.get("hook") or "", extracted.hook):
        patch["hook"] = extracted.hook

    zh_title = (data.get("zh_title") or "").strip()
    if not zh_title or not has_cjk(zh_title):
        new_title = (extracted.zh_title or "").strip()
        if not new_title or not has_cjk(new_title):
            for source in (extracted.zh_summary, extracted.zh_body, extracted.hook):
                if source:
                    new_title = derive_zh_title(source)
                    if new_title:
                        break
        if new_title and has_cjk(new_title):
            patch["zh_title"] = new_title
    return patch


def run_backfill(*, limit: int, max_updates: int | None, dry_run: bool) -> int:
    from google.cloud import firestore  # noqa: PLC0415

    db = firestore.Client(
        project=os.getenv("FIRESTORE_PROJECT_ID") or None,
        database=os.getenv("FIRESTORE_DATABASE") or None,
    )
    collection = db.collection(_collection_name())
    extractor = ExtractorAgent()

    # Fetch upfront: holding a stream open across slow Gemini calls can hit DEADLINE_EXCEEDED.
    query = (
        collection.order_by("delivered_at", direction=firestore.Query.DESCENDING).limit(limit)
    )
    docs = list(query.stream())
    logger.info("Fetched %d recent documents (limit=%d)", len(docs), limit)

    updated = 0
    skipped = 0
    failed = 0

    for doc in docs:
        if max_updates is not None and updated >= max_updates:
            logger.info("Reached --max-updates=%d, stopping", max_updates)
            break
        data = doc.to_dict() or {}
        if data.get("kind") not in {None, "", "instant_summary"}:
            skipped += 1
            continue
        if not _needs_backfill(data):
            skipped += 1
            continue

        title = (data.get("title") or "").strip()
        summary = (data.get("summary") or "").strip()
        if not title or not summary:
            skipped += 1
            continue

        text = summary
        if data.get("what_happened"):
            text = f"{data.get('what_happened')}\n\n{summary}"

        extracted = extractor.extract(
            title=title,
            text=text[:6000],
            source_name=data.get("source_name") or "",
            source_url=data.get("source_url") or "",
            relax_zh_quality=True,
        )
        if not extracted:
            logger.warning("Extractor failed for %s", doc.id)
            failed += 1
            continue

        patch = _patch_from_extraction(data, extracted)
        if not patch:
            logger.warning(
                "No zh patch for %s (existing zh_title=%r zh_summary_len=%d; "
                "extracted zh_title=%r zh_summary_len=%d hook_len=%d)",
                doc.id,
                (data.get("zh_title") or "")[:40],
                len((data.get("zh_summary") or "")),
                (extracted.zh_title or "")[:40],
                len((extracted.zh_summary or "")),
                len((extracted.hook or "")),
            )
            skipped += 1
            continue

        logger.info("%s %s: patch keys %s", "DRY-RUN" if dry_run else "UPDATE", doc.id, list(patch.keys()))
        if not dry_run:
            collection.document(doc.id).set(patch, merge=True)
        updated += 1

    logger.info(
        "Backfill complete: fetched=%d updated=%d skipped=%d failed=%d dry_run=%s",
        len(docs),
        updated,
        skipped,
        failed,
        dry_run,
    )
    return 1 if failed and not updated else 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Backfill zh_* fields on memory_items")
    parser.add_argument(
        "--limit",
        type=int,
        default=12,
        help="Max recent documents to fetch from Firestore (by delivered_at desc)",
    )
    parser.add_argument(
        "--max-updates",
        type=int,
        default=None,
        help="Stop after this many successful patches (default: no cap)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Log patches without writing")
    args = parser.parse_args()
    max_updates = args.max_updates if args.max_updates and args.max_updates > 0 else None
    return run_backfill(
        limit=max(1, args.limit),
        max_updates=max_updates,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
