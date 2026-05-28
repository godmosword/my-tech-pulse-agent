"""Simple file cache for slow external data sources (json + mtime TTL)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

DEFAULT_CACHE_DIR = Path(os.getenv("OUTPUT_DIR", "output")) / "cache"


def cache_path(key: str, *, cache_dir: Path | None = None) -> Path:
    root = cache_dir or DEFAULT_CACHE_DIR
    safe = key.replace("/", "_").replace(" ", "_")
    return root / f"{safe}.json"


def read_cached_json(key: str, *, ttl_sec: int, cache_dir: Path | None = None) -> Any | None:
    path = cache_path(key, cache_dir=cache_dir)
    if not path.is_file():
        return None
    age = __import__("time").time() - path.stat().st_mtime
    if age > ttl_sec:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def write_cached_json(key: str, data: Any, *, cache_dir: Path | None = None) -> None:
    path = cache_path(key, cache_dir=cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cached_call(
    key: str,
    ttl_sec: int,
    fetch_fn: Callable[[], T],
    *,
    cache_dir: Path | None = None,
) -> T:
    """Return cached value when fresh; otherwise fetch, store, and return."""
    hit = read_cached_json(key, ttl_sec=ttl_sec, cache_dir=cache_dir)
    if hit is not None:
        return hit  # type: ignore[return-value]
    data = fetch_fn()
    if data is not None:
        write_cached_json(key, data, cache_dir=cache_dir)
    return data
