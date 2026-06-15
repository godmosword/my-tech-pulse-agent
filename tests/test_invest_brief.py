"""P4 — full brief assembly: pulse, posture+cooldown, catalysts, thesis."""

from __future__ import annotations

from datetime import date

from scoring.invest_brief import build_invest_brief
from sources.catalyst_calendar import upcoming_catalysts

AS_OF = date(2026, 6, 15)

# (ticker, value, thesis, watch)
POSITIONS = [
    ("NVDA", 50000.0, "AI 加速器領先", ["資料中心營收"]),
    ("AMD", 5000.0, "", []),
    ("AVGO", 30000.0, "客製 ASIC", []),
]


def _item(id_, score, affected, kinds=("direct",)):
    return {
        "id": id_,
        "title": id_,
        "impact_score": score,
        "affected_tickers": affected,
        "affected_kinds": list(kinds),
    }


def test_pulse_concentration_and_correlation_flag():
    brief = build_invest_brief(
        items=[],
        positions=POSITIONS,
        catalysts=[],
        graded_records=[],
        as_of=AS_OF,
    )
    pulse = brief.portfolio_pulse
    assert pulse.top_holdings[0].ticker == "NVDA"  # largest weight
    assert pulse.concentration_top_pct > 0.5
    # NVDA+AMD+AVGO share a correlation cluster (data/clusters.json)
    assert any(f.kind == "correlation_cluster" for f in pulse.risk_flags)


def test_material_items_ranked_with_posture():
    items = [
        _item("low", 0.1, ["NVDA"]),
        _item("high", 0.5, ["NVDA"]),
    ]
    brief = build_invest_brief(
        items=items,
        positions=POSITIONS,
        catalysts=[],
        graded_records=[],
        evidence_level="strong",
        as_of=AS_OF,
    )
    assert [m.id for m in brief.material_items] == ["high", "low"]
    assert brief.material_items[0].posture == "review"  # 0.5 + strong evidence
    assert brief.material_items[0].falsification_zh


def test_cooldown_suppresses_repeat_alert():
    items = [_item("x", 0.5, ["NVDA"])]
    brief = build_invest_brief(
        items=items,
        positions=POSITIONS,
        catalysts=[],
        graded_records=[],
        evidence_level="strong",
        prev_alerts={"NVDA": "2026-06-14"},  # alerted yesterday
        as_of=AS_OF,
    )
    assert brief.material_items[0].posture == "no_action"


def test_thesis_updates_only_for_held_with_thesis():
    brief = build_invest_brief(
        items=[],
        positions=POSITIONS,
        catalysts=[],
        graded_records=[
            {"ticker": "NVDA", "rating": "看多", "period": "Q1",
             "returns": {"excess_20d": 0.05}},
        ],
        as_of=AS_OF,
    )
    tickers = {t.ticker for t in brief.thesis_updates}
    assert tickers == {"NVDA", "AVGO"}  # AMD has no thesis
    nvda = next(t for t in brief.thesis_updates if t.ticker == "NVDA")
    assert len(nvda.supporting) == 1


def test_catalyst_watch_included():
    cats = upcoming_catalysts(as_of=AS_OF, window_days=30, tickers={"NVDA"})
    brief = build_invest_brief(
        items=[], positions=POSITIONS, catalysts=cats, graded_records=[], as_of=AS_OF
    )
    assert brief.catalyst_watch
    assert all("date" in c for c in brief.catalyst_watch)
