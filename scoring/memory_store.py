"""Firestore-backed retrieval memory for delivered tech-pulse items."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import parse_qs, urlencode, urlparse

from agents.deep_insight_agent import InsightBrief
from agents.earnings_agent import EarningsOutput
from agents.extractor_agent import ArticleSummary
from llm.embedding_client import GeminiEmbedder, MEMORY_EMBEDDING_DIM

logger = logging.getLogger(__name__)

MEMORY_COLLECTION_SUFFIX = "memory_items"
MEMORY_TTL_DAYS = int(os.getenv("MEMORY_TTL_DAYS", "365"))
MEMORY_TOP_K = int(os.getenv("MEMORY_TOP_K", "3"))
SEMANTIC_DUP_DISTANCE_THRESHOLD = float(os.getenv("SEMANTIC_DUP_DISTANCE_THRESHOLD", "0.12"))
VECTOR_DISTANCE_FIELD = "vector_distance"

_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "fbclid", "gclid", "ref", "referral", "source",
    "mc_cid", "mc_eid", "yclid", "twclid", "li_fat_id",
})


@dataclass
class MemorySearchResult:
    item_id: str
    title: str
    summary: str
    source_url: str
    source_name: str
    published_at: Any = None
    delivered_at: Any = None
    category: str = ""
    entity: str = ""
    score: float = 0.0
    score_status: str = ""
    kind: str = "instant_summary"
    distance: float | None = None


class MemoryService(Protocol):
    def archive_summaries(self, summaries: list[ArticleSummary], *, delivered_at: datetime | None = None) -> None:
        ...

    def archive_deep_brief(self, brief: InsightBrief, *, delivered_at: datetime | None = None) -> None:
        ...

    def archive_earnings(self, earnings: EarningsOutput, *, delivered_at: datetime | None = None) -> None:
        ...

    def search_similar(
        self,
        title: str,
        summary: str,
        *,
        top_k: int = MEMORY_TOP_K,
        exclude_url: str = "",
    ) -> list[MemorySearchResult]:
        ...

    def is_semantic_duplicate(
        self,
        title: str,
        summary: str,
        *,
        threshold: float = SEMANTIC_DUP_DISTANCE_THRESHOLD,
    ) -> bool:
        ...


class DisabledMemoryService:
    """No-op memory implementation used when memory is disabled or unavailable."""

    def archive_summaries(self, summaries: list[ArticleSummary], *, delivered_at: datetime | None = None) -> None:
        del summaries, delivered_at

    def archive_deep_brief(self, brief: InsightBrief, *, delivered_at: datetime | None = None) -> None:
        del brief, delivered_at

    def archive_earnings(self, earnings: EarningsOutput, *, delivered_at: datetime | None = None) -> None:
        del earnings, delivered_at

    def search_similar(
        self,
        title: str,
        summary: str,
        *,
        top_k: int = MEMORY_TOP_K,
        exclude_url: str = "",
    ) -> list[MemorySearchResult]:
        del title, summary, top_k, exclude_url
        return []

    def is_semantic_duplicate(
        self,
        title: str,
        summary: str,
        *,
        threshold: float = SEMANTIC_DUP_DISTANCE_THRESHOLD,
    ) -> bool:
        del title, summary, threshold
        return False


class FirestoreMemoryService:
    """Archive delivered items and search them with Firestore vector search."""

    def __init__(
        self,
        *,
        embedder: GeminiEmbedder | None = None,
        client: Any | None = None,
        project_id: str | None = None,
        database: str | None = None,
        collection_prefix: str | None = None,
        vector_cls: Any | None = None,
        distance_measure: Any | None = None,
        failed_precondition_error: type[Exception] | tuple[type[Exception], ...] | None = None,
    ):
        self._embedder = embedder or GeminiEmbedder()
        self._prefix = (collection_prefix or os.getenv("FIRESTORE_COLLECTION_PREFIX", "tech_pulse")).strip("_")
        self._ttl = timedelta(days=MEMORY_TTL_DAYS)

        if client is None:
            from google.cloud import firestore  # noqa: PLC0415

            project_id = project_id or os.getenv("FIRESTORE_PROJECT_ID") or None
            database = database or os.getenv("FIRESTORE_DATABASE") or None
            client = firestore.Client(project=project_id, database=database) if database else firestore.Client(project=project_id)

        if vector_cls is None or distance_measure is None:
            from google.cloud.firestore_v1.base_vector_query import DistanceMeasure  # noqa: PLC0415
            from google.cloud.firestore_v1.vector import Vector  # noqa: PLC0415

            vector_cls = vector_cls or Vector
            distance_measure = distance_measure or DistanceMeasure.COSINE

        if failed_precondition_error is None:
            try:
                from google.api_core import exceptions as google_exceptions  # noqa: PLC0415

                failed_precondition_error = google_exceptions.FailedPrecondition
            except Exception:
                failed_precondition_error = RuntimeError

        self._client = client
        self._vector_cls = vector_cls
        self._distance_measure = distance_measure
        self._failed_precondition_error = failed_precondition_error

    def archive_summaries(self, summaries: list[ArticleSummary], *, delivered_at: datetime | None = None) -> None:
        delivered_at = delivered_at or datetime.now(timezone.utc)
        for summary in summaries:
            text = _summary_text(summary)
            embedding = self._embedder.embed_document(title=summary.title or summary.entity, text=text)
            if not embedding:
                continue

            item_id = _item_id(summary.source_url or f"{summary.source_name}:{summary.title}")
            payload = {
                "item_id": item_id,
                "title": summary.title or summary.entity,
                "summary": text,
                "source_url": summary.source_url,
                "source_name": summary.source_name,
                "published_at": _parse_datetime(getattr(summary, "published_at", "")),
                "delivered_at": delivered_at,
                "category": summary.category,
                "entity": summary.entity,
                "score": float(summary.score or 0.0),
                "score_status": summary.score_status,
                "kind": "instant_summary",
                "embedding": self._vector_cls(embedding),
                "expires_at": delivered_at + self._ttl,
            }
            self._write_payload(item_id, payload)

    def archive_deep_brief(self, brief: InsightBrief, *, delivered_at: datetime | None = None) -> None:
        delivered_at = delivered_at or datetime.now(timezone.utc)
        text = " ".join([brief.insight, brief.tech_rationale, brief.implication]).strip()
        embedding = self._embedder.embed_document(title=brief.title, text=text)
        if not embedding:
            return

        item_id = _item_id(brief.url or brief.item_id or brief.title)
        payload = {
            "item_id": item_id,
            "title": brief.title,
            "summary": text,
            "source_url": brief.url,
            "source_name": brief.source_name,
            "published_at": None,
            "delivered_at": delivered_at,
            "category": brief.domain,
            "entity": brief.title,
            "score": 0.0,
            "score_status": brief.confidence,
            "kind": "deep_brief",
            "embedding": self._vector_cls(embedding),
            "expires_at": delivered_at + self._ttl,
        }
        self._write_payload(item_id, payload)

    def archive_earnings(self, earnings: EarningsOutput, *, delivered_at: datetime | None = None) -> None:
        delivered_at = delivered_at or datetime.now(timezone.utc)
        text = _earnings_text(earnings)
        embedding = self._embedder.embed_document(title=f"{earnings.company} {earnings.quarter}", text=text)
        if not embedding:
            return

        item_id = _item_id(f"earnings:{earnings.company}:{earnings.quarter}:{earnings.source}")
        payload = {
            "item_id": item_id,
            "title": f"{earnings.company} {earnings.quarter}",
            "summary": text,
            "source_url": "",
            "source_name": earnings.source,
            "published_at": None,
            "delivered_at": delivered_at,
            "category": "earnings",
            "entity": earnings.company,
            "score": 0.0,
            "score_status": earnings.confidence,
            "kind": "earnings",
            "embedding": self._vector_cls(embedding),
            "expires_at": delivered_at + self._ttl,
        }
        self._write_payload(item_id, payload)

    def search_similar(
        self,
        title: str,
        summary: str,
        *,
        top_k: int = MEMORY_TOP_K,
        exclude_url: str = "",
    ) -> list[MemorySearchResult]:
        query_text = "\n\n".join(part for part in [title.strip(), summary.strip()] if part)
        embedding = self._embedder.embed_query(query_text)
        if not embedding:
            return []

        try:
            vector_query = self._collection().find_nearest(
                vector_field="embedding",
                query_vector=self._vector_cls(embedding),
                distance_measure=self._distance_measure,
                limit=max(1, top_k),
                distance_result_field=VECTOR_DISTANCE_FIELD,
            )
            results = []
            normalized_exclude = _normalize_url(exclude_url) if exclude_url else ""
            for doc in vector_query.stream():
                result = _doc_to_memory_result(doc)
                if normalized_exclude and _normalize_url(result.source_url) == normalized_exclude:
                    continue
                results.append(result)
            return results
        except Exception as exc:
            if self._is_missing_index_error(exc):
                logger.warning(
                    "Firestore memory vector search skipped because the required vector index "
                    "is missing or building. Create collection group %s_%s embedding dimension %d. Error: %s",
                    self._prefix,
                    MEMORY_COLLECTION_SUFFIX,
                    MEMORY_EMBEDDING_DIM,
                    exc,
                )
                return []
            logger.warning("Firestore memory vector search failed; continuing without memory: %s", exc)
            return []

    def is_semantic_duplicate(
        self,
        title: str,
        summary: str,
        *,
        threshold: float = SEMANTIC_DUP_DISTANCE_THRESHOLD,
    ) -> bool:
        matches = self.search_similar(title, summary, top_k=1)
        return bool(matches and matches[0].distance is not None and matches[0].distance <= threshold)

    def _collection(self):
        return self._client.collection(f"{self._prefix}_{MEMORY_COLLECTION_SUFFIX}")

    def _write_payload(self, item_id: str, payload: dict[str, Any]) -> None:
        try:
            self._collection().document(item_id).set(payload, merge=True)
        except Exception as exc:
            logger.warning("Firestore memory archive skipped for %s: %s", item_id, exc)

    def _is_missing_index_error(self, exc: Exception) -> bool:
        return isinstance(exc, self._failed_precondition_error) and "index" in str(exc).lower()


def make_memory_service() -> MemoryService:
    enabled = os.getenv("MEMORY_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return DisabledMemoryService()

    backend = os.getenv("MEMORY_BACKEND", "firestore").strip().lower()
    if backend != "firestore":
        logger.warning("Unknown MEMORY_BACKEND=%r; memory disabled", backend)
        return DisabledMemoryService()

    try:
        return FirestoreMemoryService()
    except Exception as exc:
        logger.warning("Firestore memory unavailable; continuing without memory: %s", exc)
        return DisabledMemoryService()


def _summary_text(summary: ArticleSummary) -> str:
    fact = (summary.what_happened or "").strip()
    impact = (summary.why_it_matters or "").strip()
    if fact and impact:
        return f"{fact} {impact}"
    if fact:
        return fact
    return (summary.summary or "").strip()


def _earnings_text(earnings: EarningsOutput) -> str:
    parts = [
        earnings.company,
        earnings.quarter,
        f"revenue actual {earnings.revenue.actual}" if earnings.revenue.actual is not None else "",
        f"revenue estimate {earnings.revenue.estimate}" if earnings.revenue.estimate is not None else "",
        f"eps actual {earnings.eps.actual}" if earnings.eps.actual is not None else "",
        f"eps estimate {earnings.eps.estimate}" if earnings.eps.estimate is not None else "",
        f"guidance {earnings.guidance_next_q}" if earnings.guidance_next_q is not None else "",
        " ".join(earnings.key_quotes[:2]),
    ]
    return " ".join(part for part in parts if part).strip()


def _doc_to_memory_result(doc: Any) -> MemorySearchResult:
    data = doc.to_dict() if hasattr(doc, "to_dict") else dict(doc)
    distance = None
    if hasattr(doc, "get"):
        try:
            distance = doc.get(VECTOR_DISTANCE_FIELD)
        except Exception:
            distance = None
    if distance is None:
        distance = data.get(VECTOR_DISTANCE_FIELD)
    return MemorySearchResult(
        item_id=str(data.get("item_id") or getattr(doc, "id", "")),
        title=str(data.get("title") or ""),
        summary=str(data.get("summary") or ""),
        source_url=str(data.get("source_url") or ""),
        source_name=str(data.get("source_name") or ""),
        published_at=data.get("published_at"),
        delivered_at=data.get("delivered_at"),
        category=str(data.get("category") or ""),
        entity=str(data.get("entity") or ""),
        score=float(data.get("score") or 0.0),
        score_status=str(data.get("score_status") or ""),
        kind=str(data.get("kind") or "instant_summary"),
        distance=float(distance) if distance is not None else None,
    )


def _item_id(value: str) -> str:
    return hashlib.sha256(_normalize_url(value).encode()).hexdigest()


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        clean_params = {
            k: v
            for k, v in parse_qs(parsed.query).items()
            if k.lower() not in _TRACKING_PARAMS
        }
        clean_query = urlencode(sorted(clean_params.items()))
        return parsed._replace(query=clean_query, fragment="").geturl().rstrip("/")
    except Exception:
        return url.rstrip("/")


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None
    return None
