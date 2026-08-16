"""Shared JSON snapshot I/O for dashboard/data (no Firestore)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def dashboard_data_dir(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    raw = os.getenv("DASHBOARD_DATA_DIR", "").strip()
    if raw:
        return Path(raw)
    return repo_root() / "dashboard" / "data"


def state_sqlite_path(db_path: Path | None = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    raw = os.getenv("STATE_SQLITE_PATH", "").strip()
    if raw:
        return Path(raw)
    return Path(os.getenv("OUTPUT_DIR", "output")) / "dedup.sqlite"


def json_retention_days() -> int:
    raw = os.getenv("JSON_RETENTION_DAYS", "90").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 90


def memory_items_path(data_dir: Path | None = None) -> Path:
    return dashboard_data_dir(data_dir) / "memory_items.json"


def digests_path(data_dir: Path | None = None) -> Path:
    return dashboard_data_dir(data_dir) / "digests.json"


def earnings_dir(data_dir: Path | None = None) -> Path:
    return dashboard_data_dir(data_dir) / "earnings"


def earnings_index_path(data_dir: Path | None = None) -> Path:
    return earnings_dir(data_dir) / "index.json"


def earnings_report_path(report_id: str, data_dir: Path | None = None) -> Path:
    safe = report_id.replace("/", "_").replace("..", "_")
    return earnings_dir(data_dir) / f"{safe}.json"


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    tmp.replace(path)


def parse_iso(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def to_iso(value: object) -> str | None:
    parsed = parse_iso(value)
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def json_safe(value: Any) -> Any:
    """Recursively convert datetimes; drop non-JSON values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return to_iso(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items() if k != "embedding"}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "model_dump"):
        return json_safe(value.model_dump(mode="json"))
    return str(value)


_RETAIN_KINDS = frozenset({"earnings"})


def prune_by_timestamp(
    rows: list[dict[str, Any]],
    *,
    field: str = "delivered_at",
    retention_days: int | None = None,
    retain_kinds: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    days = json_retention_days() if retention_days is None else retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    kinds = _RETAIN_KINDS if retain_kinds is None else retain_kinds
    kept: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("kind") or "") in kinds:
            kept.append(row)
            continue
        ts = parse_iso(row.get(field))
        if ts is None or ts >= cutoff:
            kept.append(row)
    return kept


def upsert_by_id(
    rows: list[dict[str, Any]],
    item: dict[str, Any],
    *,
    id_key: str = "item_id",
) -> list[dict[str, Any]]:
    item_id = str(item.get(id_key) or "")
    if not item_id:
        return rows + [item]
    out = [row for row in rows if str(row.get(id_key) or "") != item_id]
    out.append(item)
    return out
