"""P4 — posture guardrails (anti-overtrading)."""

from __future__ import annotations

from datetime import date

from scoring.posture import decide_posture

AS_OF = date(2026, 6, 15)


def _p(**kw):
    return decide_posture(as_of=AS_OF, **kw)


def test_low_impact_is_no_action():
    d = _p(impact_score=0.05, evidence_level="strong")
    assert d.posture == "no_action"
    assert d.label_zh == "無需動作"


def test_mid_impact_is_monitor():
    d = _p(impact_score=0.25, evidence_level="moderate")
    assert d.posture == "monitor"


def test_high_impact_with_evidence_is_review():
    d = _p(impact_score=0.5, evidence_level="moderate")
    assert d.posture == "review"


def test_weak_evidence_softens_strong_posture():
    d = _p(impact_score=0.5, evidence_level="insufficient")
    assert d.posture == "monitor"  # stepped down from review


def test_supply_chain_risk_flag():
    d = _p(impact_score=0.5, evidence_level="strong", affected_kinds={"supply_chain"})
    assert d.posture == "risk_up"
    assert d.label_zh == "風險升高"


def test_cooldown_suppresses_repeat_nudge():
    d = _p(impact_score=0.3, evidence_level="moderate", recent_alert_days=1)
    assert d.posture == "no_action"
    assert d.suppressed_by_cooldown is True


def test_cooldown_overridden_by_material_escalation():
    d = _p(impact_score=0.7, evidence_level="moderate", recent_alert_days=1)
    assert d.suppressed_by_cooldown is False


def test_always_has_falsification_and_next_check():
    d = _p(impact_score=0.5, evidence_level="moderate")
    assert d.falsification_zh
    assert d.next_check > AS_OF.isoformat()
    # never transactional vocabulary
    assert d.posture in {"no_action", "monitor", "review", "risk_up"}
