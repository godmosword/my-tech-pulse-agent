"""P3 — forward catalyst calendar (read-only, dependency-light).

Merges manually-curated events (config/catalysts.yaml) with any earnings-calendar
rows passed in by the caller, then returns the upcoming events within a window,
optionally filtered to a set of tickers (plus MACRO, which is always relevant).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional

import yaml
from pydantic import BaseModel

CATALYSTS_PATH = Path(__file__).resolve().parents[1] / "config" / "catalysts.yaml"
MACRO_TICKER = "MACRO"


class Catalyst(BaseModel):
    ticker: str
    date: str
    type: str
    note: str = ""


def _load_manual(path: Optional[Path] = None) -> list[Catalyst]:
    p = path or CATALYSTS_PATH
    if not p.is_file():
        return []
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return []
    out: list[Catalyst] = []
    for row in raw.get("events") or []:
        if not isinstance(row, dict) or not row.get("ticker") or not row.get("date"):
            continue
        out.append(
            Catalyst(
                ticker=str(row["ticker"]).upper(),
                date=str(row["date"])[:10],
                type=str(row.get("type") or "event"),
                note=str(row.get("note") or ""),
            )
        )
    return out


def upcoming_catalysts(
    *,
    as_of: Optional[date] = None,
    window_days: int = 14,
    tickers: Optional[Iterable[str]] = None,
    earnings_dates: Optional[Iterable[tuple[str, str]]] = None,
    path: Optional[Path] = None,
) -> list[Catalyst]:
    """Sorted upcoming catalysts within ``window_days``.

    ``earnings_dates`` is an optional iterable of (ticker, YYYY-MM-DD) merged in
    as ``type=earnings``. ``tickers`` filters by holding (MACRO always kept).
    """
    as_of = as_of or date.today()
    horizon = as_of + timedelta(days=window_days)
    wanted = {t.upper() for t in tickers} if tickers is not None else None

    events = list(_load_manual(path))
    for tkr, day in earnings_dates or []:
        if tkr and day:
            events.append(
                Catalyst(ticker=str(tkr).upper(), date=str(day)[:10], type="earnings")
            )

    out: list[Catalyst] = []
    for ev in events:
        try:
            ev_day = date.fromisoformat(ev.date)
        except ValueError:
            continue
        if ev_day < as_of or ev_day > horizon:
            continue
        if wanted is not None and ev.ticker != MACRO_TICKER and ev.ticker not in wanted:
            continue
        out.append(ev)

    return sorted(out, key=lambda e: (e.date, e.ticker))
