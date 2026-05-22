"""Extract business segment revenue lines from filing text."""

from __future__ import annotations

import re
from typing import Optional

from agents.earnings_v3_models import SegmentRow

_SEGMENT_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9 &\-]{2,40}?)\s+revenue\s+(?:was|of|totaled)\s+"
    r"\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(billion|million|B|M)\b",
    re.IGNORECASE,
)

_B = 1_000_000_000.0
_M = 1_000_000.0


def _to_usd(val: float, unit: str) -> float:
    u = unit.lower()
    if u in {"billion", "b"}:
        return val * _B
    if u in {"million", "m"}:
        return val * _M
    return val


def extract_segments(filing_text: str, *, limit: int = 4) -> list[SegmentRow]:
    if not filing_text:
        return []
    rows: list[SegmentRow] = []
    seen: set[str] = set()
    for m in _SEGMENT_RE.finditer(filing_text):
        name = m.group(1).strip()
        if name.lower() in {"total", "net", "consolidated"}:
            continue
        key = name.lower()
        if key in seen:
            continue
        if str(m.group(2)) not in filing_text:
            continue
        revenue = _to_usd(float(m.group(2)), m.group(3))
        seen.add(key)
        rows.append(
            SegmentRow(
                name_zh=name,
                revenue=revenue,
                driver_zh="",
            )
        )
        if len(rows) >= limit:
            break
    return rows
