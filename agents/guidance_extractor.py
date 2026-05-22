"""Extract structured guidance / CapEx from earnings press-release text."""

from __future__ import annotations

import re
from typing import Any, Optional

from agents.earnings_v3_models import GuidanceCapex

_B_TO_USD = 1_000_000_000.0
_M_TO_USD = 1_000_000.0

_CAPEX_RE = re.compile(
    r"(?:capital\s+expenditures?|capex)[^.]{0,120}?"
    r"\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(billion|million|B|M)\b",
    re.IGNORECASE,
)
_REV_RANGE_RE = re.compile(
    r"(?:revenue\s+guidance|outlook|expects\s+revenue)[^.]{0,160}?"
    r"\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(billion|million|B|M)?"
    r"\s*(?:to|-|–|and)\s*"
    r"\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(billion|million|B|M)\b",
    re.IGNORECASE,
)
_TONE_POS = re.compile(r"\b(optimistic|strong demand|accelerat|growth)\b", re.I)
_TONE_NEG = re.compile(r"\b(cautious|headwind|uncertain|slowdown|weak)\b", re.I)


def _money_to_usd(value: float, unit: str) -> float:
    u = unit.lower()
    if u in {"billion", "b"}:
        return value * _B_TO_USD
    if u in {"million", "m"}:
        return value * _M_TO_USD
    return value


def _verified_amount(text: str, value: float, unit: str) -> Optional[float]:
    """Require raw value string to appear in source text."""
    if str(value) not in text:
        return None
    return _money_to_usd(value, unit)


def extract_guidance_capex(
    filing_text: str,
    *,
    narrative_guidance: dict[str, Any] | None = None,
    next_q_revenue_consensus: float | None = None,
) -> GuidanceCapex:
    text = filing_text or ""
    narrative_guidance = narrative_guidance or {}
    low = high = capex = None
    capex_focus = ""
    vs_note = ""

    m = _REV_RANGE_RE.search(text)
    if m:
        v1, u1, v2, u2 = m.group(1), m.group(2) or "billion", m.group(3), m.group(4)
        low = _verified_amount(text, float(v1), u1)
        high = _verified_amount(text, float(v2), u2)

    cm = _CAPEX_RE.search(text)
    if cm:
        capex = _verified_amount(text, float(cm.group(1)), cm.group(2))
        snippet = cm.group(0)[:200]
        if "ai" in snippet.lower() or "data center" in snippet.lower():
            capex_focus = "AI 基礎設施"
        elif "fab" in snippet.lower() or "manufacturing" in snippet.lower():
            capex_focus = "製造產能"

    if next_q_revenue_consensus and low and high:
        mid = (low + high) / 2
        if mid > next_q_revenue_consensus * 1.02:
            vs_note = "指引中位數高於市場共識"
        elif mid < next_q_revenue_consensus * 0.98:
            vs_note = "指引中位數低於市場共識"
        else:
            vs_note = "指引中位數接近市場共識"

    wording = str(narrative_guidance.get("wording") or "")
    combined = f"{text[:8000]} {wording}"
    if _TONE_NEG.search(combined):
        outlook = "謹慎"
    elif _TONE_POS.search(combined):
        outlook = "樂觀"
    else:
        outlook = "未知"

    return GuidanceCapex(
        next_q_revenue_low=low,
        next_q_revenue_high=high,
        vs_consensus_note=vs_note,
        capex_amount=capex,
        capex_focus_zh=capex_focus,
        outlook_tone=outlook,  # type: ignore[arg-type]
    )
