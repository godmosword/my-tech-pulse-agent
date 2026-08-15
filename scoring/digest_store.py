"""Canonical digest snapshots in dashboard/data/digests.json."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Protocol

from agents.deep_insight_agent import InsightBrief
from agents.extractor_agent import ArticleSummary
from agents.synthesizer_agent import DigestOutput
from delivery.message_formatter import _select_by_theme
from scoring.json_io import (
    digests_path,
    json_safe,
    prune_by_timestamp,
    read_json_list,
    upsert_by_id,
    write_json,
)
from scoring.memory_store import _item_id

logger = logging.getLogger(__name__)


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


class JsonDigestStore:
    def __init__(self, *, data_dir: Any = None):
        self._data_dir = data_dir

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

        payload = json_safe({
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
        })
        if not isinstance(payload, dict):
            return None
        path = digests_path(self._data_dir)
        rows = upsert_by_id(read_json_list(path), payload, id_key="digest_id")
        write_json(path, prune_by_timestamp(rows))
        logger.info("Saved digest snapshot %s (%d theme groups)", digest_id, len(theme_groups))
        return digest_id

    def get_latest(self) -> dict | None:
        rows = read_json_list(digests_path(self._data_dir))
        if not rows:
            return None
        rows.sort(key=lambda row: str(row.get("delivered_at") or ""), reverse=True)
        return rows[0]


def make_digest_store() -> DigestStore:
    if os.getenv("DIGEST_SNAPSHOT_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        return DisabledDigestStore()
    return JsonDigestStore()
