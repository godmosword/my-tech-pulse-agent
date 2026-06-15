"""Point-in-time investable universe snapshots — survivorship disclosure.

The backtest replays signals over the *current* watchlist, which biases results
optimistically if failed/removed names were dropped over time. We cannot fully
reconstruct history retroactively, so this module records dated snapshots of the
investable universe going forward and exposes an honest disclosure about how much
of an evaluated period is actually covered by a point-in-time snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "config" / "historical_universe.json"


def _load(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_PATH
    if not p.is_file():
        return {"snapshots": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"snapshots": []}
    if not isinstance(data, dict):
        return {"snapshots": []}
    return data


def _snapshots(path: Path | None = None) -> list[dict[str, Any]]:
    snaps = _load(path).get("snapshots") or []
    return sorted(
        (s for s in snaps if isinstance(s, dict) and s.get("as_of")),
        key=lambda s: str(s["as_of"]),
    )


def investable_universe_asof(day: str, *, path: Path | None = None) -> list[str] | None:
    """Tickers investable as of ``day`` (YYYY-MM-DD), from the latest prior snapshot.

    Returns None when no snapshot predates ``day`` (caller should fall back to the
    current watchlist and treat the result as survivorship-biased).
    """
    day = str(day)[:10]
    chosen: list[str] | None = None
    for snap in _snapshots(path):
        if str(snap["as_of"])[:10] <= day:
            members = snap.get("tickers") or []
            chosen = [str(t).upper() for t in members if t]
        else:
            break
    return chosen


def survivorship_status(
    evaluated_dates: list[str], *, path: Path | None = None
) -> dict[str, Any]:
    """Disclosure: how many evaluated decision dates have a point-in-time universe."""
    days = sorted({str(d)[:10] for d in evaluated_dates if d})
    if not days:
        return {"covered": 0, "total": 0, "coverage_pct": None, "biased": False}
    covered = sum(1 for d in days if investable_universe_asof(d, path=path) is not None)
    total = len(days)
    return {
        "covered": covered,
        "total": total,
        "coverage_pct": round(covered / total, 4) if total else None,
        "biased": covered < total,
        "note_zh": (
            "部分評估期間無 point-in-time universe 快照，結果可能含 survivorship "
            "偏誤（偏樂觀）。快照自建立日起向前累積。"
        ),
    }
