"""Persistent state backends for deduplication and lightweight user state."""

from __future__ import annotations

import importlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from scoring.json_io import state_sqlite_path

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Local cosine similarity — numpy if available, pure Python fallback."""
    if not a or not b or len(a) != len(b):
        return 0.0
    try:
        np = importlib.import_module("numpy")
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

    def list_recent_embeddings(
        self, window_days: int = 90
    ) -> list[tuple[str, str, list[float]]]:
        ...


class SQLiteStateStore:
    """sqlite-backed state for local development and tests."""

    def __init__(self, db_path: Path | None = None):
        self._db_path = state_sqlite_path(db_path)
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

    def list_recent_embeddings(
        self, window_days: int = 90
    ) -> list[tuple[str, str, list[float]]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT article_id, url, embedding FROM article_embeddings "
                "WHERE stored_at >= ?",
                (cutoff,),
            ).fetchall()
        out: list[tuple[str, str, list[float]]] = []
        for article_id, url, emb_json in rows:
            try:
                stored = json.loads(emb_json)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(stored, list) and stored:
                out.append((str(article_id), str(url or ""), stored))
        return out


def make_state_store(db_path: Path | None = None) -> StateStore:
    """Create the sqlite state backend (STATE_BACKEND=firestore is ignored)."""
    if db_path is not None:
        return SQLiteStateStore(db_path)

    backend = os.getenv("STATE_BACKEND", "sqlite").strip().lower()
    if backend not in {"sqlite", "sqlite3", "auto", ""}:
        logger.warning("Unknown STATE_BACKEND=%r; using sqlite", backend)
    return SQLiteStateStore()
