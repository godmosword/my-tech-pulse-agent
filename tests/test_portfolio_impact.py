"""P1 — position-aware news impact scoring."""

from __future__ import annotations

from datetime import date

import scoring.portfolio_impact as pi
from scoring.portfolio_impact import resolve_tickers, score_impact

TODAY = date(2026, 6, 15)


def _score(tickers, *, positions, theme="", held_themes=None, entity="", score=8.0):
    return score_impact(
        tickers=tickers,
        entity=entity,
        theme=theme,
        confidence="high",
        news_score=score,
        cross_ref=True,
        published_at=TODAY.isoformat(),
        positions=positions,
        held_themes=held_themes or set(),
        as_of=TODAY,
    )


def test_direct_hit_scores_and_labels():
    out = _score(["NVDA"], positions=[("NVDA", 10000.0)])
    assert out.score > 0
    assert out.affected_positions[0].kind == "direct"
    assert out.components.relation_weight == 1.0


def test_supply_chain_indirect_hit():
    # News about TSM affects an NVDA holding (TSM is in NVDA's 10-K relationships).
    out = _score(["TSM"], positions=[("NVDA", 10000.0)])
    assert out.score > 0
    kinds = {a.kind for a in out.affected_positions}
    assert "supply_chain" in kinds
    assert "direct" not in kinds


def test_cluster_indirect_hit():
    # News about NVDA affects an AMD holding via the correlation cluster.
    out = _score(["NVDA"], positions=[("AMD", 10000.0)])
    assert out.score > 0
    assert out.affected_positions[0].kind == "cluster"


def test_no_relation_is_zero():
    out = _score(["XYZ"], positions=[("AAPL", 10000.0)], entity="Unknown Co")
    assert out.score == 0.0
    assert out.affected_positions == []


def test_theme_only_hit_is_weak():
    out = _score(
        [], positions=[("MRVL", 10000.0)], theme="ai_silicon", held_themes={"ai_silicon"}
    )
    assert out.affected_positions
    assert out.affected_positions[0].kind == "theme"
    assert 0 < out.score < 0.5  # theme relation is intentionally weak


def test_strongest_relation_wins_no_double_count():
    # Holding NVDA, news about NVDA: direct only, never also counted as cluster.
    out = _score(["NVDA"], positions=[("NVDA", 10000.0)])
    assert [a.ticker for a in out.affected_positions] == ["NVDA"]
    assert out.affected_positions[0].kind == "direct"


def test_entity_resolution_uses_aliases(monkeypatch):
    monkeypatch.setattr(pi, "_load_aliases", lambda: {"taiwan semiconductor": "TSM"})
    resolved = resolve_tickers([], "Taiwan Semiconductor")
    assert "TSM" in resolved


def test_components_are_emitted():
    out = _score(["NVDA"], positions=[("NVDA", 10000.0)])
    c = out.components
    assert 0 < c.relevance <= 1
    assert 0 < c.exposure_weight <= 1
    assert 0 < c.freshness <= 1
    assert c.confidence == 1.0
