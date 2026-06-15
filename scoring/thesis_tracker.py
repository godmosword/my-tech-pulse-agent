"""P3 — link evidence to a holding's thesis. Evidence only, never a verdict.

Given a holding's graded signal history (from Phase-0 grading) and upcoming
catalysts, surface which signals *support* or *contradict* the thesis and what
is *coming up*. It deliberately produces no single "thesis playing out" score —
that would manufacture false precision from a tiny sample.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

BULLISH_RATINGS = frozenset({"強力看多", "看多"})
BEARISH_RATINGS = frozenset({"強力看空", "看空"})


class ThesisEvidence(BaseModel):
    ticker: str
    thesis: str = ""
    supporting: list[str] = Field(default_factory=list)
    contradicting: list[str] = Field(default_factory=list)
    upcoming: list[str] = Field(default_factory=list)


def _direction_realized(rating: str, excess: float) -> str | None:
    """Did the realized excess return agree with the rating's direction?"""
    if rating in BULLISH_RATINGS:
        return "support" if excess > 0 else "contradict"
    if rating in BEARISH_RATINGS:
        return "support" if excess < 0 else "contradict"
    return None


def link_thesis_evidence(
    *,
    ticker: str,
    thesis: str,
    graded_records: list[dict[str, Any]],
    upcoming_catalysts: list[Any] | None = None,
    horizon_key: str = "excess_20d",
) -> ThesisEvidence:
    """Bucket graded signals into supporting/contradicting; list upcoming catalysts."""
    sym = ticker.upper()
    supporting: list[str] = []
    contradicting: list[str] = []

    for rec in graded_records:
        if str(rec.get("ticker") or "").upper() != sym:
            continue
        excess = (rec.get("returns") or {}).get(horizon_key)
        rating = str(rec.get("rating") or "")
        if excess is None:
            continue
        verdict = _direction_realized(rating, float(excess))
        if verdict is None:
            continue
        period = rec.get("period") or rec.get("decision_date") or "?"
        line = f"{period}：{rating}，後續超額 {float(excess) * 100:.1f}%"
        (supporting if verdict == "support" else contradicting).append(line)

    upcoming: list[str] = []
    for cat in upcoming_catalysts or []:
        c_ticker = str(getattr(cat, "ticker", "") or "").upper()
        if c_ticker in {sym, "MACRO"}:
            note = getattr(cat, "note", "") or getattr(cat, "type", "")
            upcoming.append(f"{getattr(cat, 'date', '?')} · {note}")

    return ThesisEvidence(
        ticker=sym,
        thesis=thesis,
        supporting=supporting,
        contradicting=contradicting,
        upcoming=upcoming,
    )
