"""P4 — suggested posture with anti-overtrading guardrails.

The decision brief must not induce trading. Posture defaults to the most passive
option, a cooldown suppresses repeat nudges on the same name, and every output
carries a falsification condition and a next-check date instead of an action.
``evidence_level`` may only *soften* tone — it never escalates into a buy/sell.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Optional

from pydantic import BaseModel

# Deliberately non-transactional vocabulary (no buy/sell/avoid).
Posture = Literal["no_action", "monitor", "review", "risk_up"]

POSTURE_LABEL_ZH: dict[Posture, str] = {
    "no_action": "無需動作",
    "monitor": "需要注意",
    "review": "需要複核",
    "risk_up": "風險升高",
}

_NEXT_CHECK_DAYS: dict[Posture, int] = {
    "no_action": 30,
    "monitor": 7,
    "review": 3,
    "risk_up": 2,
}

DEFAULT_COOLDOWN_DAYS = 4
# Impact strong enough to override a cooldown (a genuinely material escalation).
_COOLDOWN_OVERRIDE = 0.6
_RISK_KINDS = frozenset({"supply_chain", "cluster"})


class PostureDecision(BaseModel):
    posture: Posture
    label_zh: str
    reason_zh: str
    falsification_zh: str
    next_check: str
    suppressed_by_cooldown: bool = False


def decide_posture(
    *,
    impact_score: float,
    evidence_level: str = "insufficient",
    affected_kinds: Optional[set[str]] = None,
    recent_alert_days: Optional[int] = None,
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
    as_of: Optional[date] = None,
) -> PostureDecision:
    """Map impact + evidence into a conservative, non-transactional posture."""
    as_of = as_of or date.today()
    affected_kinds = affected_kinds or set()

    suppressed = (
        recent_alert_days is not None
        and recent_alert_days < cooldown_days
        and impact_score < _COOLDOWN_OVERRIDE
    )
    if suppressed:
        return _build(
            "no_action",
            as_of,
            reason="同標的近期已提醒，未達顯著升級門檻（cooldown）。",
            falsification="若出現新催化劑或衝擊顯著升高再行複核。",
            suppressed=True,
        )

    if impact_score < 0.15:
        posture: Posture = "no_action"
    elif impact_score < 0.40:
        posture = "monitor"
    else:
        posture = "review"

    # Concentration / supply-chain exposure at material impact -> flag risk, not action.
    if impact_score >= 0.40 and (affected_kinds & _RISK_KINDS):
        posture = "risk_up"

    # Evidence only softens: a strong posture on weak evidence steps down one notch.
    if posture in {"review", "risk_up"} and evidence_level in {"insufficient", "weak"}:
        posture = "monitor"

    reason = (
        f"部位衝擊 {impact_score:.2f}、證據等級 {evidence_level}。"
        "此為注意度分級，非投資建議。"
    )
    falsification = (
        "若後續無基本面跟進、或價格已反映且無新增曝險，下次檢查時應降級。"
    )
    return _build(posture, as_of, reason=reason, falsification=falsification)


def _build(
    posture: Posture,
    as_of: date,
    *,
    reason: str,
    falsification: str,
    suppressed: bool = False,
) -> PostureDecision:
    next_check = (as_of + timedelta(days=_NEXT_CHECK_DAYS[posture])).isoformat()
    return PostureDecision(
        posture=posture,
        label_zh=POSTURE_LABEL_ZH[posture],
        reason_zh=reason,
        falsification_zh=falsification,
        next_check=next_check,
        suppressed_by_cooldown=suppressed,
    )
