"""P3 — catalyst calendar + thesis evidence-linking."""

from __future__ import annotations

from datetime import date

from scoring.thesis_tracker import link_thesis_evidence
from sources.catalyst_calendar import upcoming_catalysts

AS_OF = date(2026, 6, 15)


def test_upcoming_within_window_sorted():
    cats = upcoming_catalysts(as_of=AS_OF, window_days=14)
    assert cats, "seed catalysts.yaml should yield events in-window"
    dates = [c.date for c in cats]
    assert dates == sorted(dates)
    assert all(c.date >= AS_OF.isoformat() for c in cats)


def test_ticker_filter_keeps_macro():
    cats = upcoming_catalysts(as_of=AS_OF, window_days=30, tickers={"NVDA"})
    tickers = {c.ticker for c in cats}
    assert tickers <= {"NVDA", "MACRO"}
    assert "AMD" not in tickers


def test_earnings_dates_merged():
    cats = upcoming_catalysts(
        as_of=AS_OF,
        window_days=10,
        tickers={"MU"},
        earnings_dates=[("MU", "2026-06-20")],
    )
    assert any(c.type == "earnings" and c.ticker == "MU" for c in cats)


def test_window_excludes_far_future():
    near = upcoming_catalysts(as_of=AS_OF, window_days=2)
    assert all(c.date <= "2026-06-17" for c in near)


def _rec(ticker, rating, excess, period="FY26 Q1"):
    return {"ticker": ticker, "rating": rating, "period": period,
            "returns": {"excess_20d": excess}}


def test_thesis_evidence_buckets_support_and_contradict():
    graded = [
        _rec("NVDA", "看多", 0.04),   # bullish + positive -> support
        _rec("NVDA", "看多", -0.03),  # bullish + negative -> contradict
        _rec("AMD", "看多", 0.10),    # other ticker -> ignored
    ]
    ev = link_thesis_evidence(
        ticker="NVDA", thesis="AI 加速器領先", graded_records=graded
    )
    assert len(ev.supporting) == 1
    assert len(ev.contradicting) == 1
    # evidence linking only — no single verdict/score field exists
    assert not hasattr(ev, "score")


def test_thesis_lists_upcoming_catalysts():
    cats = upcoming_catalysts(as_of=AS_OF, window_days=30, tickers={"NVDA"})
    ev = link_thesis_evidence(
        ticker="NVDA", thesis="x", graded_records=[], upcoming_catalysts=cats
    )
    assert ev.upcoming  # includes NVDA and MACRO events
