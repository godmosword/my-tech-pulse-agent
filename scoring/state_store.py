"""Persistent state backends for deduplication and lightweight user state."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

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
"""


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

    def cleanup_seen(self, cutoff_iso: str) -> int:
        ...

    def save_item(self, item_id: str, saved_at: datetime) -> None:
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

    def cleanup_seen(self, cutoff_iso: str) -> int:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM seen_items WHERE seen_at <= ?", (cutoff_iso,))
            conn.commit()
        return cursor.rowcount

    def save_item(self, item_id: str, saved_at: datetime) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO saved_items (item_id, saved_at) VALUES (?, ?)",
                (item_id, saved_at.isoformat()),
            )
            conn.commit()


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

    def _collection(self, name: str):
        return self._client.collection(f"{self._prefix}_{name}")

    def has_seen(self, url_hash: str, content_hash: str, cutoff_iso: str) -> bool:
        cutoff = datetime.fromisoformat(cutoff_iso)
        doc = self._collection("seen_items").document(url_hash).get()
        if doc.exists:
            data = doc.to_dict() or {}
            seen_at = data.get("seen_at")
            if isinstance(seen_at, datetime) and seen_at > cutoff:
                return True

        query = (
            self._collection("seen_items")
            .where("content_hash", "==", content_hash)
            .where("seen_at", ">", cutoff)
            .limit(1)
        )
        return any(query.stream())

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

    def cleanup_seen(self, cutoff_iso: str) -> int:
        del cutoff_iso
        return 0

    def save_item(self, item_id: str, saved_at: datetime) -> None:
        self._collection("saved_items").document(item_id).set(
            {"item_id": item_id, "saved_at": saved_at},
            merge=True,
        )


def make_state_store(db_path: Path | None = None) -> StateStore:
    """Create the configured state backend."""
    if db_path is not None:
        return SQLiteStateStore(db_path)

    backend = os.getenv("STATE_BACKEND", "sqlite").strip().lower()
    if backend in {"sqlite", "sqlite3", ""}:
        return SQLiteStateStore()
    if backend == "firestore":
        return FirestoreStateStore()

    logger.warning("Unknown STATE_BACKEND=%r; falling back to sqlite", backend)
    return SQLiteStateStore()
