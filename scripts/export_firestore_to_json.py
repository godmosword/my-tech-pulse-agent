#!/usr/bin/env python3
"""One-time export of existing Firestore collections into dashboard/data JSON.

Requires google-cloud-firestore and ADC while the GCP project still exists.
Safe to delete after cutover.

Usage:
  python scripts/export_firestore_to_json.py --dry-run
  python scripts/export_firestore_to_json.py
"""

from __future__ import annotations

import argparse
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

from scoring.json_io import (  # noqa: E402
    digests_path,
    earnings_index_path,
    earnings_report_path,
    json_safe,
    memory_items_path,
    prune_by_timestamp,
    write_json,
)

logger = logging.getLogger(__name__)


def _prefix() -> str:
    return os.getenv("FIRESTORE_COLLECTION_PREFIX", "tech_pulse").strip("_")


def _doc_payload(doc) -> dict:
    data = doc.to_dict() or {}
    data.setdefault("item_id", doc.id)
    data.setdefault("digest_id", doc.id)
    data.setdefault("report_id", doc.id)
    if "embedding" in data:
        del data["embedding"]
    return json_safe(data)  # type: ignore[return-value]


def _client():
    try:
        from google.cloud import firestore  # noqa: PLC0415
    except ImportError as exc:
        raise SystemExit(
            "google-cloud-firestore is not installed. "
            "pip install google-cloud-firestore and retry while GCP still exists."
        ) from exc
    return firestore.Client(
        project=os.getenv("FIRESTORE_PROJECT_ID") or None,
        database=os.getenv("FIRESTORE_DATABASE") or None,
    )


def export_memory(db, *, dry_run: bool) -> int:
    coll = os.getenv("TECH_PULSE_FIRESTORE_COLLECTION", "").strip() or f"{_prefix()}_memory_items"
    rows = []
    for doc in db.collection(coll).stream():
        payload = _doc_payload(doc)
        if isinstance(payload, dict):
            rows.append(payload)
    rows = prune_by_timestamp(rows)
    logger.info("memory_items exported=%d", len(rows))
    if not dry_run:
        write_json(memory_items_path(), rows)
    return len(rows)


def export_digests(db, *, dry_run: bool) -> int:
    rows = []
    for doc in db.collection(f"{_prefix()}_digests").stream():
        payload = _doc_payload(doc)
        if isinstance(payload, dict):
            rows.append(payload)
    rows = prune_by_timestamp(rows)
    logger.info("digests exported=%d", len(rows))
    if not dry_run:
        write_json(digests_path(), rows)
    return len(rows)


def export_earnings(db, *, dry_run: bool) -> int:
    index: list[dict] = []
    count = 0
    for doc in db.collection(f"{_prefix()}_earnings_reports").stream():
        payload = _doc_payload(doc)
        if not isinstance(payload, dict):
            continue
        report_id = str(payload.get("report_id") or doc.id)
        if not dry_run:
            write_json(earnings_report_path(report_id), payload)
        lean = {k: v for k, v in payload.items() if k not in {"rendered_markdown_zh", "trend", "embedding"}}
        index.append(lean)
        count += 1
    logger.info("earnings exported=%d", count)
    if not dry_run:
        write_json(earnings_index_path(), index)
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db = _client()
    n_mem = export_memory(db, dry_run=args.dry_run)
    n_dig = export_digests(db, dry_run=args.dry_run)
    n_earn = export_earnings(db, dry_run=args.dry_run)
    logger.info(
        "export complete dry_run=%s memory=%d digests=%d earnings=%d as_of=%s",
        args.dry_run,
        n_mem,
        n_dig,
        n_earn,
        datetime.now(timezone.utc).isoformat(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
