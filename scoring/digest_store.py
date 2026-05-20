"""Canonical digest snapshots in Firestore (`{prefix}_digests`)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Protocol

from agents.deep_insight_agent import InsightBrief
from agents.extractor_agent import ArticleSummary
from agents.synthesizer_agent import DigestOutput
from delivery.message_formatter import _select_by_theme
from scoring.memory_store import _item_id

logger = logging.getLogger(__name__)

DIGEST_COLLECTION_SUFFIX = "digests"


class DigestStore(Protocol):
    def save_run(
        self,
        *,
        digest: DigestOutput | None,
        summaries: list[ArticleSummary],
        deep_briefs: list[InsightBrief],
        delivered_at: datetime | None = None,
        funnel: dict | None = None,
    ) -> str | None:
        ...

    def get_latest(self) -> dict | None:
        ...


class DisabledDigestStore:
    def save_run(self, **kwargs) -> str | None:
        del kwargs
        return None

    def get_latest(self) -> dict | None:
        return None


class FirestoreDigestStore:
    def __init__(
        self,
        *,
        client: Any | None = None,
        project_id: str | None = None,
        database: str | None = None,
        collection_prefix: str | None = None,
    ):
        if client is None:
            from google.cloud import firestore  # noqa: PLC0415

            project_id = project_id or os.getenv("FIRESTORE_PROJECT_ID") or None
            database = database or os.getenv("FIRESTORE_DATABASE") or None
            client = firestore.Client(project=project_id, database=database) if database else firestore.Client(project=project_id)

        prefix = (collection_prefix or os.getenv("FIRESTORE_COLLECTION_PREFIX", "tech_pulse")).strip("_")
        self._collection = client.collection(f"{prefix}_{DIGEST_COLLECTION_SUFFIX}")

    def save_run(
        self,
        *,
        digest: DigestOutput | None,
        summaries: list[ArticleSummary],
        deep_briefs: list[InsightBrief],
        delivered_at: datetime | None = None,
        funnel: dict | None = None,
    ) -> str | None:
        delivered_at = delivered_at or datetime.now(timezone.utc)
        digest_id = delivered_at.strftime("%Y%m%dT%H%M%SZ")

        theme_groups = []
        for theme, items in _select_by_theme(summaries):
            theme_groups.append({
                "theme": theme,
                "item_ids": [
                    _item_id(s.source_url or f"{s.source_name}:{s.title}")
                    for s in items
                    if s.source_url or s.title
                ],
            })

        payload = {
            "digest_id": digest_id,
            "delivered_at": delivered_at,
            "digest": digest.model_dump() if digest else None,
            "theme_groups": theme_groups,
            "summary_item_ids": [
                _item_id(s.source_url or f"{s.source_name}:{s.title}")
                for s in summaries
                if s.source_url or s.title
            ],
            "deep_brief_ids": [
                brief.item_id or _item_id(brief.url or brief.title)
                for brief in deep_briefs
            ],
            "funnel": funnel or {},
        }
        self._collection.document(digest_id).set(payload)
        logger.info("Saved digest snapshot %s (%d theme groups)", digest_id, len(theme_groups))
        return digest_id

    def get_latest(self) -> dict | None:
        docs = (
            self._collection.order_by("delivered_at", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict() or {}
            data.setdefault("digest_id", doc.id)
            return data
        return None


def make_digest_store() -> DigestStore:
    if os.getenv("DIGEST_SNAPSHOT_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        return DisabledDigestStore()
    try:
        return FirestoreDigestStore()
    except Exception as exc:
        logger.warning("Digest store disabled: %s", exc)
        return DisabledDigestStore()
