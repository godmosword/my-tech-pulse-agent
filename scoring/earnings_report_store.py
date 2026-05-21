"""Firestore store for tech_pulse_earnings_reports (earnings_v2)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Protocol

from agents.earnings_models import EarningsReport

logger = logging.getLogger(__name__)

EARNINGS_REPORTS_SUFFIX = "earnings_reports"


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


class FirestoreEarningsReportStore:
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
        self._collection = client.collection(f"{prefix}_{EARNINGS_REPORTS_SUFFIX}")

    def save(self, report: EarningsReport) -> str | None:
        payload = report.model_dump(mode="json")
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._collection.document(report.report_id).set(payload, merge=True)
        logger.info("Saved earnings report %s", report.report_id)
        return report.report_id

    def get(self, report_id: str) -> dict | None:
        doc = self._collection.document(report_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        data.setdefault("report_id", doc.id)
        return data


def make_earnings_report_store() -> EarningsReportStore:
    if os.getenv("EARNINGS_REPORTS_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        return DisabledEarningsReportStore()
    try:
        return FirestoreEarningsReportStore()
    except Exception as exc:
        logger.warning("Earnings report store disabled: %s", exc)
        return DisabledEarningsReportStore()
