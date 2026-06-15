"""Conservative invest alert formatting."""

from __future__ import annotations

from datetime import date

from delivery.invest_alert import format_invest_alert

AS_OF = date(2026, 6, 15)


class _Item:
    def __init__(self, title, posture, affected):
        self.title = title
        self.posture = posture
        self.affected_tickers = affected


class _Brief:
    def __init__(self, material_items, catalyst_watch):
        self.material_items = material_items
        self.catalyst_watch = catalyst_watch


def test_no_alert_when_nothing_material():
    brief = _Brief(
        material_items=[_Item("x", "monitor", ["NVDA"])],
        catalyst_watch=[{"date": "2026-07-30", "ticker": "NVDA", "note": "遠期"}],
    )
    assert format_invest_alert(brief, as_of=AS_OF) is None


def test_alert_on_risk_up():
    brief = _Brief(
        material_items=[_Item("出口管制升級", "risk_up", ["NVDA", "AMD"])],
        catalyst_watch=[],
    )
    text = format_invest_alert(brief, as_of=AS_OF)
    assert text and "風險升高" in text
    assert "NVDA" in text


def test_alert_on_imminent_catalyst_only():
    brief = _Brief(
        material_items=[],
        catalyst_watch=[{"date": "2026-06-16", "ticker": "MACRO", "note": "FOMC"}],
    )
    text = format_invest_alert(brief, as_of=AS_OF)
    assert text and "近日催化劑" in text
    assert "FOMC" in text


def test_far_catalyst_excluded():
    brief = _Brief(
        material_items=[],
        catalyst_watch=[{"date": "2026-06-25", "ticker": "TSM", "note": "月營收"}],
    )
    assert format_invest_alert(brief, as_of=AS_OF) is None
