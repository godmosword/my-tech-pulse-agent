"""Thin what_happened triggers one grounded extraction retry (MIN_WHAT_HAPPENED_CHARS)."""

import pytest

from agents.extractor_agent import ArticleSummary
from agents.reviewer_agent import ReviewResult, ReviewerAgent


@pytest.fixture
def long_source() -> str:
    return (
        "Acme Corp announced a $100 million Series B led by Example Ventures in January 2026."
    )


def test_reviewer_retries_when_what_happened_too_short(monkeypatch, long_source: str) -> None:
    monkeypatch.setenv("MIN_WHAT_HAPPENED_CHARS", "40")
    calls: list[str] = []

    def fake_extract(title: str, text: str, source_name: str = "", source_url: str = "") -> ArticleSummary:
        calls.append(text)
        return ArticleSummary(
            entity="Acme",
            summary="Acme announced funding.",
            what_happened=(
                "Acme Corp announced a $100 million Series B led by Example Ventures in January 2026."
            ),
            why_it_matters="Increases competitive pressure in the sector.",
            category="funding",
            sentiment="neutral",
            confidence="medium",
            title=title,
            source_url=source_url,
            source_name=source_name,
        )

    agent = ReviewerAgent()
    monkeypatch.setattr(agent._extractor, "extract", fake_extract)
    monkeypatch.setattr(ReviewerAgent, "_call_reviewer", lambda self, s, st: ReviewResult())

    summary = ArticleSummary(
        entity="Acme",
        summary="x",
        what_happened="short",
        why_it_matters="",
        category="other",
        sentiment="neutral",
        confidence="high",
        title="Funding news",
        source_url="https://example.com/a",
        source_name="Ex",
    )
    summary.source_text = long_source

    out = agent.review(summary)

    assert len(calls) == 1
    assert out.extract_retry_used is True
    assert "[Reviewer feedback" in calls[0]
    assert len((out.final_output.what_happened or "").strip()) >= 40
