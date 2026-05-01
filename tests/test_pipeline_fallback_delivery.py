from pipeline.crew import TechPulseCrew
from sources.rss_fetcher import Article
from delivery.message_formatter import format_items_digest


def test_fallback_summaries_keep_single_item_digest_non_empty():
    crew = TechPulseCrew.__new__(TechPulseCrew)
    article = Article(
        title="OpenAI launches a new enterprise AI product",
        url="https://example.com/openai-enterprise",
        source="Example News",
        summary="OpenAI launched a new enterprise AI product for business customers.",
        score=8.2,
        score_status="scored",
    )

    summaries = crew._fallback_summaries([article])
    msg = format_items_digest(summaries, total_fetched=316, total_after_filter=1)

    assert len(summaries) == 1
    assert "OpenAI launches a new enterprise AI product" in msg
    assert "OpenAI launched a new enterprise AI product" in msg
    assert "Example News" in msg
    assert "今日 316 篇" not in msg


def test_fallback_summaries_handle_missing_rss_summary():
    crew = TechPulseCrew.__new__(TechPulseCrew)
    article = Article(
        title="Thin RSS item",
        url="https://example.com/thin",
        source="Example News",
        score=0.0,
        score_status="fallback",
    )

    summaries = crew._fallback_summaries([article])
    msg = format_items_digest(summaries, total_fetched=316, total_after_filter=1)

    assert "Thin RSS item" in msg
    assert "原文摘要暫時無法取得" in msg


def test_ensure_minimum_summaries_adds_three_fallback_items(monkeypatch):
    monkeypatch.setattr("pipeline.crew.MIN_DIGEST_ITEMS", 3)
    crew = TechPulseCrew.__new__(TechPulseCrew)
    articles = [
        Article(
            title=f"Fallback {idx}",
            url=f"https://example.com/{idx}",
            source="Example News",
            summary=f"Fallback summary {idx}",
            score=0.0,
            score_status="fallback",
        )
        for idx in range(4)
    ]

    summaries = crew._ensure_minimum_summaries([], articles)
    msg = format_items_digest(summaries, total_fetched=10, total_after_filter=4)

    assert len(summaries) == 3
    assert "Fallback 0" in msg
    assert "Fallback 1" in msg
    assert "Fallback 2" in msg
    assert "Fallback 3" not in msg
    assert "全部待確認" in msg


def test_final_claim_only_marks_deliverable_summaries():
    class FakeDedup:
        def __init__(self):
            self.claimed = []

        def claim_article(self, article):
            self.claimed.append(article.url)
            return True

    crew = TechPulseCrew.__new__(TechPulseCrew)
    crew.deduplicator = FakeDedup()
    articles = [
        Article(title="Delivered", url="https://example.com/delivered", source="Example News"),
        Article(title="Filtered", url="https://example.com/filtered", source="Example News"),
    ]
    summaries = crew._fallback_summaries([articles[0]])

    claimed = crew._claim_deliverable_summaries(summaries, articles)

    assert claimed == summaries
    assert crew.deduplicator.claimed == ["https://example.com/delivered"]
