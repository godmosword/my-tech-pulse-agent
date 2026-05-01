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
