"""Persistent storage for Telegram digest/item feedback votes."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from scoring.json_io import state_sqlite_path

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
        self._db_path = state_sqlite_path(db_path)
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


def make_feedback_store(db_path: Path | None = None) -> FeedbackStore:
    """Create the sqlite feedback backend."""
    return SQLiteFeedbackStore(db_path)
