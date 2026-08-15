"""JSON store for earnings reports under dashboard/data/earnings/."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Protocol

from agents.earnings_models import EarningsReport
from scoring.json_io import (
    earnings_index_path,
    earnings_report_path,
    json_safe,
    read_json_list,
    read_json_object,
    upsert_by_id,
    write_json,
)

logger = logging.getLogger(__name__)

_INDEX_SKIP = frozenset({"rendered_markdown_zh", "trend", "embedding"})


class EarningsReportStore(Protocol):
    def save(self, report: EarningsReport) -> str | None:
        ...

    def get(self, report_id: str) -> dict | None:
        ...


class DisabledEarningsReportStore:
    def save(self, report: EarningsReport) -> str | None:
        del report
        return None

    def get(self, report_id: str) -> dict | None:
        del report_id
        return None


class JsonEarningsReportStore:
    def __init__(self, *, data_dir: Any = None):
        self._data_dir = data_dir

    def save(self, report: EarningsReport) -> str | None:
        payload = json_safe(report.model_dump(mode="json"))
        if not isinstance(payload, dict):
            return None
        payload["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload.setdefault("report_id", report.report_id)
        write_json(earnings_report_path(report.report_id, self._data_dir), payload)

        lean = {k: v for k, v in payload.items() if k not in _INDEX_SKIP}
        index_path = earnings_index_path(self._data_dir)
        rows = upsert_by_id(read_json_list(index_path), lean, id_key="report_id")
        write_json(index_path, rows)
        logger.info("Saved earnings report %s", report.report_id)
        return report.report_id

    def get(self, report_id: str) -> dict | None:
        data = read_json_object(earnings_report_path(report_id, self._data_dir))
        if data is None:
            return None
        data.setdefault("report_id", report_id)
        return data


def make_earnings_report_store() -> EarningsReportStore:
    if os.getenv("EARNINGS_REPORTS_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        return DisabledEarningsReportStore()
    return JsonEarningsReportStore()
