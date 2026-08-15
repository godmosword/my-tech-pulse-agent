#!/usr/bin/env python3
"""Backfill Traditional Chinese fields on dashboard/data/memory_items.json.

Re-runs Flash zh backfill when zh_summary or zh_title is missing.

Usage:
  python scripts/backfill_zh_fields.py --dry-run --limit 8
  python scripts/backfill_zh_fields.py --limit 8 --max-updates 6
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

from llm.localization import has_cjk  # noqa: E402
from llm.zh_backfill import ZhBackfillResult, extract_zh_backfill  # noqa: E402
from scoring.json_io import memory_items_path, read_json_list, write_json  # noqa: E402

logger = logging.getLogger(__name__)


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


def _patch_from_zh(data: dict, zh: ZhBackfillResult) -> dict:
    patch: dict = {}
    if _should_replace_zh_field(data.get("zh_summary") or "", zh.zh_summary):
        patch["zh_summary"] = zh.zh_summary
    if _should_replace_zh_field(data.get("hook") or "", zh.hook):
        patch["hook"] = zh.hook

    zh_title = (data.get("zh_title") or "").strip()
    if (not zh_title or not has_cjk(zh_title)) and zh.zh_title and has_cjk(zh.zh_title):
        patch["zh_title"] = zh.zh_title
    return patch


def run_backfill(*, limit: int, max_updates: int | None, dry_run: bool) -> int:
    path = memory_items_path()
    rows = read_json_list(path)
    rows.sort(key=lambda row: str(row.get("delivered_at") or ""), reverse=True)
    docs = rows[:limit]
    logger.info("Fetched %d recent documents (limit=%d)", len(docs), limit)

    updated = 0
    skipped = 0
    failed = 0

    for data in docs:
        if max_updates is not None and updated >= max_updates:
            logger.info("Reached --max-updates=%d, stopping", max_updates)
            break
        item_id = str(data.get("item_id") or data.get("id") or "")
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

        zh = extract_zh_backfill(
            title=title,
            summary=summary,
            what_happened=str(data.get("what_happened") or ""),
        )
        if not zh:
            logger.warning("zh_backfill failed for %s (%s)", item_id, title[:60])
            failed += 1
            continue

        patch = _patch_from_zh(data, zh)
        if not patch:
            skipped += 1
            continue

        logger.info("%s %s: patch keys %s", "DRY-RUN" if dry_run else "UPDATE", item_id, list(patch.keys()))
        if not dry_run:
            data.update(patch)
        updated += 1

    if not dry_run and updated:
        write_json(path, rows)

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
    parser = argparse.ArgumentParser(description="Backfill zh_* fields on memory_items.json")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--max-updates", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    max_updates = args.max_updates if args.max_updates and args.max_updates > 0 else None
    return run_backfill(
        limit=max(1, args.limit),
        max_updates=max_updates,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
