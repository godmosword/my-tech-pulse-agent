"""Persistent storage for Telegram digest/item feedback votes."""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast

logger = logging.getLogger(__name__)

VoteValue = Literal["up", "down"]
TargetType = Literal["digest", "item"]

_FEEDBACK_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    doc_key      TEXT PRIMARY KEY,
    target_id    TEXT NOT NULL,
    target_type  TEXT NOT NULL,
    vote         TEXT NOT NULL,
    user_id_hash TEXT NOT NULL,
    timestamp    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS telegram_poll_offset (
    key   TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
"""


class FeedbackStore(Protocol):
    def save_vote(
        self,
        *,
        target_id: str,
        target_type: TargetType,
        vote: VoteValue,
        user_id_hash: str,
        voted_at: datetime,
    ) -> None:
        ...

    def get_update_offset(self) -> int:
        ...

    def set_update_offset(self, offset: int) -> None:
        ...


def hash_telegram_user_id(user_id: int) -> str:
    return hashlib.sha256(f"tg:{user_id}".encode()).hexdigest()[:16]


def feedback_doc_key(user_id_hash: str, target_type: TargetType, target_id: str) -> str:
    return f"{user_id_hash}_{target_type}_{target_id}"


class SQLiteFeedbackStore:
    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = Path(os.getenv("OUTPUT_DIR", "output")) / "dedup.sqlite"
        self._db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript(_FEEDBACK_SQLITE_SCHEMA)
            conn.commit()

    def save_vote(
        self,
        *,
        target_id: str,
        target_type: TargetType,
        vote: VoteValue,
        user_id_hash: str,
        voted_at: datetime,
    ) -> None:
        doc_key = feedback_doc_key(user_id_hash, target_type, target_id)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO feedback "
                "(doc_key, target_id, target_type, vote, user_id_hash, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    doc_key,
                    target_id,
                    target_type,
                    vote,
                    user_id_hash,
                    voted_at.isoformat(),
                ),
            )
            conn.commit()

    def get_update_offset(self) -> int:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT value FROM telegram_poll_offset WHERE key = 'callback_updates'"
            ).fetchone()
        return int(row[0]) if row else 0

    def set_update_offset(self, offset: int) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO telegram_poll_offset (key, value) VALUES (?, ?)",
                ("callback_updates", int(offset)),
            )
            conn.commit()


class FirestoreFeedbackStore:
    """Firestore-backed feedback for Cloud Run production deployments."""

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
                "Firestore feedback store requires google-cloud-firestore to be installed."
            ) from exc

        project_id = project_id or os.getenv("FIRESTORE_PROJECT_ID") or None
        database = database or os.getenv("FIRESTORE_DATABASE") or None
        self._prefix = (collection_prefix or os.getenv("FIRESTORE_COLLECTION_PREFIX", "tech_pulse")).strip("_")
        if database:
            self._client = firestore.Client(project=project_id, database=database)
        else:
            self._client = firestore.Client(project=project_id)

    def _feedback_collection(self):
        return self._client.collection(f"{self._prefix}_feedback")

    def _offset_doc(self):
        return self._client.collection(f"{self._prefix}_telegram_poll").document("callback_offset")

    def save_vote(
        self,
        *,
        target_id: str,
        target_type: TargetType,
        vote: VoteValue,
        user_id_hash: str,
        voted_at: datetime,
    ) -> None:
        doc_key = feedback_doc_key(user_id_hash, target_type, target_id)
        self._feedback_collection().document(doc_key).set(
            {
                "target_id": target_id,
                "target_type": target_type,
                "vote": vote,
                "user_id_hash": user_id_hash,
                "timestamp": voted_at,
            },
            merge=True,
        )

    def get_update_offset(self) -> int:
        doc = cast(Any, self._offset_doc().get())
        if not doc.exists:
            return 0
        data = doc.to_dict() or {}
        return int(data.get("offset") or 0)

    def set_update_offset(self, offset: int) -> None:
        self._offset_doc().set({"offset": int(offset)}, merge=True)


def make_feedback_store(db_path: Path | None = None) -> FeedbackStore:
    """Create the configured feedback backend."""
    if db_path is not None:
        return SQLiteFeedbackStore(db_path)

    backend = os.getenv("STATE_BACKEND", "auto").strip().lower()
    if backend == "auto":
        backend = "firestore" if os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB") else "sqlite"

    if backend in {"sqlite", "sqlite3", ""}:
        return SQLiteFeedbackStore()
    if backend == "firestore":
        try:
            return FirestoreFeedbackStore()
        except Exception:
            logger.exception("Firestore feedback backend unavailable; falling back to sqlite")
            return SQLiteFeedbackStore()

    logger.warning("Unknown STATE_BACKEND=%r for feedback; falling back to sqlite", backend)
    return SQLiteFeedbackStore()
