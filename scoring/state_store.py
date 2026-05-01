"""Persistent state backends for deduplication and lightweight user state."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Local cosine similarity — numpy if available, pure Python fallback."""
    if not a or not b or len(a) != len(b):
        return 0.0
    try:
        import numpy as np  # noqa: PLC0415
        va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
        denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
        return float(np.dot(va, vb) / denom) if denom > 0 else 0.0
    except ImportError:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        return dot / (mag_a * mag_b) if mag_a * mag_b > 0 else 0.0

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    url_hash     TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    seen_at      TEXT NOT NULL,
    url          TEXT
);
CREATE INDEX IF NOT EXISTS idx_content_hash ON seen_items (content_hash);
CREATE INDEX IF NOT EXISTS idx_seen_at      ON seen_items (seen_at);
CREATE TABLE IF NOT EXISTS saved_items (
    item_id  TEXT PRIMARY KEY,
    saved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS processed_articles (
    article_id  TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS article_embeddings (
    article_id  TEXT PRIMARY KEY,
    url         TEXT,
    embedding   TEXT NOT NULL,
    stored_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emb_stored_at ON article_embeddings (stored_at);
"""

DEFAULT_PROCESSED_TTL_DAYS = int(os.getenv("STATE_TTL_DAYS", "30"))


class StateStore(Protocol):
    """Storage contract for deduplication and feedback state."""

    def has_seen(self, url_hash: str, content_hash: str, cutoff_iso: str) -> bool:
        ...

    def mark_seen(
        self,
        url_hash: str,
        content_hash: str,
        seen_at: datetime,
        url: str,
        expires_at: datetime,
    ) -> None:
        ...

    def claim_seen(
        self,
        url_hash: str,
        content_hash: str,
        cutoff_iso: str,
        seen_at: datetime,
        url: str,
        expires_at: datetime,
    ) -> bool:
        ...

    def cleanup_seen(self, cutoff_iso: str) -> int:
        ...

    def is_processed_and_store(self, article_id: str) -> bool:
        ...

    def save_item(self, item_id: str, saved_at: datetime) -> None:
        ...

    def store_embedding(self, article_id: str, url: str, embedding: list[float]) -> None:
        ...

    def is_semantically_duplicate(
        self,
        new_embedding: list[float],
        threshold: float = 0.85,
        window_days: int = 7,
    ) -> tuple[bool, float]:
        ...


class SQLiteStateStore:
    """sqlite-backed state for local development and tests."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = Path(os.getenv("OUTPUT_DIR", "output")) / "dedup.sqlite"
        self._db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(_SQLITE_SCHEMA)
            conn.commit()

    def has_seen(self, url_hash: str, content_hash: str, cutoff_iso: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_items "
                "WHERE (url_hash = ? OR content_hash = ?) AND seen_at > ?",
                (url_hash, content_hash, cutoff_iso),
            ).fetchone()
        return row is not None

    def mark_seen(
        self,
        url_hash: str,
        content_hash: str,
        seen_at: datetime,
        url: str,
        expires_at: datetime,
    ) -> None:
        del expires_at
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO seen_items "
                "(url_hash, content_hash, seen_at, url) VALUES (?, ?, ?, ?)",
                (url_hash, content_hash, seen_at.isoformat(), url),
            )
            conn.commit()

    def claim_seen(
        self,
        url_hash: str,
        content_hash: str,
        cutoff_iso: str,
        seen_at: datetime,
        url: str,
        expires_at: datetime,
    ) -> bool:
        del expires_at
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT 1 FROM seen_items "
                "WHERE (url_hash = ? OR content_hash = ?) AND seen_at > ?",
                (url_hash, content_hash, cutoff_iso),
            ).fetchone()
            if row is not None:
                conn.commit()
                return False
            conn.execute(
                "INSERT OR REPLACE INTO seen_items "
                "(url_hash, content_hash, seen_at, url) VALUES (?, ?, ?, ?)",
                (url_hash, content_hash, seen_at.isoformat(), url),
            )
            conn.commit()
            return True

    def cleanup_seen(self, cutoff_iso: str) -> int:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM seen_items WHERE seen_at <= ?", (cutoff_iso,))
            conn.commit()
        return cursor.rowcount

    def is_processed_and_store(self, article_id: str) -> bool:
        processed_at = datetime.now(timezone.utc)
        expires_at = processed_at + timedelta(days=DEFAULT_PROCESSED_TTL_DAYS)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT 1 FROM processed_articles WHERE article_id = ?",
                (article_id,),
            ).fetchone()
            if row is not None:
                conn.commit()
                return True
            conn.execute(
                "INSERT INTO processed_articles (article_id, processed_at, expires_at) VALUES (?, ?, ?)",
                (article_id, processed_at.isoformat(), expires_at.isoformat()),
            )
            conn.commit()
            return False

    def save_item(self, item_id: str, saved_at: datetime) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO saved_items (item_id, saved_at) VALUES (?, ?)",
                (item_id, saved_at.isoformat()),
            )
            conn.commit()

    def store_embedding(self, article_id: str, url: str, embedding: list[float]) -> None:
        if not embedding:
            return
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO article_embeddings (article_id, url, embedding, stored_at) "
                "VALUES (?, ?, ?, ?)",
                (article_id, url, json.dumps(embedding), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def is_semantically_duplicate(
        self,
        new_embedding: list[float],
        threshold: float = 0.85,
        window_days: int = 7,
    ) -> tuple[bool, float]:
        if not new_embedding:
            return False, 0.0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT embedding FROM article_embeddings WHERE stored_at >= ?",
                (cutoff,),
            ).fetchall()
        best = 0.0
        for (emb_json,) in rows:
            try:
                stored = json.loads(emb_json)
            except (json.JSONDecodeError, TypeError):
                continue
            sim = _cosine_similarity(new_embedding, stored)
            if sim > best:
                best = sim
            if sim >= threshold:
                return True, sim
        return False, best


class FirestoreStateStore:
    """Firestore-backed state for Cloud Run production deployments."""

    def __init__(
        self,
        project_id: str | None = None,
        database: str | None = None,
        collection_prefix: str | None = None,
    ):
        try:
            from google.cloud import firestore
            from google.api_core import exceptions as google_exceptions
            from google.cloud.firestore_v1 import transactional
        except ImportError as exc:
            raise RuntimeError(
                "STATE_BACKEND=firestore requires google-cloud-firestore to be installed."
            ) from exc

        project_id = project_id or os.getenv("FIRESTORE_PROJECT_ID") or None
        database = database or os.getenv("FIRESTORE_DATABASE") or None
        self._prefix = (collection_prefix or os.getenv("FIRESTORE_COLLECTION_PREFIX", "tech_pulse")).strip("_")
        if database:
            self._client = firestore.Client(project=project_id, database=database)
        else:
            self._client = firestore.Client(project=project_id)
        self._transactional = transactional
        self._failed_precondition_error = google_exceptions.FailedPrecondition

    def _is_missing_index_error(self, exc: Exception) -> bool:
        return isinstance(exc, self._failed_precondition_error) and "requires an index" in str(exc)

    def _content_hash_seen(self, content_hash: str, cutoff: datetime, transaction=None) -> bool:
        query = (
            self._collection("seen_items")
            .where("content_hash", "==", content_hash)
            .where("seen_at", ">", cutoff)
            .limit(1)
        )
        try:
            return any(query.stream(transaction=transaction))
        except Exception as exc:
            if not self._is_missing_index_error(exc):
                raise
            logger.warning(
                "Firestore content-hash dedup query skipped because the required composite "
                "index is missing. URL-based dedup will continue; create the index for "
                "collection group %s_seen_items on content_hash ASC and seen_at ASC. Error: %s",
                self._prefix,
                exc,
            )
            return False

    def _collection(self, name: str):
        return self._client.collection(f"{self._prefix}_{name}")

    def _processed_articles_collection(self):
        collection_name = os.getenv("FIRESTORE_PROCESSED_COLLECTION", "processed_articles")
        return self._client.collection(collection_name)

    def has_seen(self, url_hash: str, content_hash: str, cutoff_iso: str) -> bool:
        cutoff = datetime.fromisoformat(cutoff_iso)
        doc = self._collection("seen_items").document(url_hash).get()
        if doc.exists:
            data = doc.to_dict() or {}
            seen_at = data.get("seen_at")
            if isinstance(seen_at, datetime) and seen_at > cutoff:
                return True

        return self._content_hash_seen(content_hash, cutoff)

    def mark_seen(
        self,
        url_hash: str,
        content_hash: str,
        seen_at: datetime,
        url: str,
        expires_at: datetime,
    ) -> None:
        self._collection("seen_items").document(url_hash).set(
            {
                "content_hash": content_hash,
                "seen_at": seen_at,
                "expires_at": expires_at,
                "url": url,
            },
            merge=True,
        )

    def claim_seen(
        self,
        url_hash: str,
        content_hash: str,
        cutoff_iso: str,
        seen_at: datetime,
        url: str,
        expires_at: datetime,
    ) -> bool:
        cutoff = datetime.fromisoformat(cutoff_iso)
        doc_ref = self._collection("seen_items").document(url_hash)
        transaction = self._client.transaction()

        @self._transactional
        def _claim(txn) -> bool:
            doc = doc_ref.get(transaction=txn)
            if doc.exists:
                data = doc.to_dict() or {}
                existing_seen_at = data.get("seen_at")
                if isinstance(existing_seen_at, datetime) and existing_seen_at > cutoff:
                    return False

            if self._content_hash_seen(content_hash, cutoff, transaction=txn):
                return False

            txn.set(
                doc_ref,
                {
                    "content_hash": content_hash,
                    "seen_at": seen_at,
                    "expires_at": expires_at,
                    "url": url,
                },
                merge=True,
            )
            return True

        return _claim(transaction)

    def cleanup_seen(self, cutoff_iso: str) -> int:
        del cutoff_iso
        return 0

    def is_processed_and_store(self, article_id: str) -> bool:
        """Atomically claim a processed article id.

        Returns True when the article was already processed, False when this
        call created the registry document. Enable Firestore TTL in GCP Console
        for the `expires_at` field on the `processed_articles` collection.
        """
        processed_at = datetime.now(timezone.utc)
        expires_at = processed_at + timedelta(days=DEFAULT_PROCESSED_TTL_DAYS)
        doc_ref = self._processed_articles_collection().document(article_id)
        transaction = self._client.transaction()

        @self._transactional
        def _claim(txn) -> bool:
            doc = doc_ref.get(transaction=txn)
            if doc.exists:
                return True
            txn.set(
                doc_ref,
                {
                    "article_id": article_id,
                    "processed_at": processed_at,
                    "expires_at": expires_at,
                },
            )
            return False

        return _claim(transaction)

    def save_item(self, item_id: str, saved_at: datetime) -> None:
        self._collection("saved_items").document(item_id).set(
            {"item_id": item_id, "saved_at": saved_at},
            merge=True,
        )

    def store_embedding(self, article_id: str, url: str, embedding: list[float]) -> None:
        if not embedding:
            return
        now = datetime.now(timezone.utc)
        self._collection("article_embeddings").document(article_id).set(
            {
                "article_id": article_id,
                "url": url,
                "embedding": embedding,
                "stored_at": now,
                "expires_at": now + timedelta(days=DEFAULT_PROCESSED_TTL_DAYS),
            },
            merge=True,
        )

    def is_semantically_duplicate(
        self,
        new_embedding: list[float],
        threshold: float = 0.85,
        window_days: int = 7,
    ) -> tuple[bool, float]:
        if not new_embedding:
            return False, 0.0
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        try:
            query = self._collection("article_embeddings").where("stored_at", ">=", cutoff).stream()
            best = 0.0
            for doc in query:
                data = doc.to_dict() or {}
                stored = data.get("embedding") or []
                if not stored:
                    continue
                # Firestore may return a list or a google.cloud.firestore_v1.base_vector.Vector
                stored_list = list(stored) if not isinstance(stored, list) else stored
                sim = _cosine_similarity(new_embedding, stored_list)
                if sim > best:
                    best = sim
                if sim >= threshold:
                    return True, sim
            return False, best
        except Exception as exc:
            logger.warning("Firestore semantic dedup query failed; allowing article: %s", exc)
            return False, 0.0


def make_state_store(db_path: Path | None = None) -> StateStore:
    """Create the configured state backend."""
    if db_path is not None:
        return SQLiteStateStore(db_path)

    backend = os.getenv("STATE_BACKEND", "auto").strip().lower()
    if backend == "auto":
        backend = "firestore" if os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB") else "sqlite"

    if backend in {"sqlite", "sqlite3", ""}:
        return SQLiteStateStore()
    if backend == "firestore":
        try:
            return FirestoreStateStore()
        except Exception:
            logger.exception("Firestore state backend unavailable; falling back to sqlite")
            return SQLiteStateStore()

    logger.warning("Unknown STATE_BACKEND=%r; falling back to sqlite", backend)
    return SQLiteStateStore()
