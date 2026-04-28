"""Smoke tests: validate pipeline stages without hitting live APIs."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.earnings_agent import EarningsAgent, EarningsOutput, EPSData, RevenueData
from agents.extractor_agent import ArticleSummary, ExtractorAgent
from agents.synthesizer_agent import DigestOutput, SynthesizerAgent
from delivery.telegram_bot import TelegramBot
from scoring.deduplicator import Deduplicator
from scoring.scorer import ScoreResult, Scorer
from sources.rss_fetcher import Article, RSSFetcher


# ---------- RSS Fetcher ----------

def test_rss_fetcher_loads_registry():
    fetcher = RSSFetcher()
    assert len(fetcher._registry) > 0, "Source registry should have at least one news source"


def test_article_model_validates():
    article = Article(title="Test", url="https://example.com", source="test_rss")
    assert article.cross_ref is False


def test_article_model_rejects_missing_url():
    with pytest.raises(Exception):
        Article(title="Test", source="test_rss")  # url is required


# ---------- Extractor Agent ----------

MOCK_EXTRACTOR_RESPONSE = json.dumps({
    "entity": "OpenAI",
    "summary": "OpenAI released GPT-5 with improved reasoning capabilities.",
    "category": "product_launch",
    "key_facts": ["GPT-5 released", "improved reasoning"],
    "sentiment": "positive",
    "confidence": "high",
    "cross_ref": False,
})


def test_extractor_parses_valid_response():
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=MOCK_EXTRACTOR_RESPONSE)]
        )

        agent = ExtractorAgent()
        result = agent.extract(
            title="OpenAI Releases GPT-5",
            text="OpenAI today announced GPT-5, featuring improved reasoning.",
            source_name="techcrunch_rss",
        )

    assert result is not None
    assert result.entity == "OpenAI"
    assert result.confidence == "high"
    assert result.category == "product_launch"


def test_extractor_returns_none_on_invalid_json():
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="not valid json")]
        )

        agent = ExtractorAgent()
        result = agent.extract(title="Test", text="Test text")

    assert result is None


def test_extractor_no_hallucination_field_present():
    """Ensure the confidence field is always present — required for anti-hallucination tracking."""
    summary = ArticleSummary(
        entity="Test",
        summary="Test summary.",
        category="other",
        sentiment="neutral",
        confidence="low",
    )
    assert summary.confidence in ("high", "medium", "low")


# ---------- Synthesizer Agent ----------

MOCK_DIGEST_RESPONSE = json.dumps({
    "date": "2026-04-28",
    "headline": "AI dominates the week",
    "themes": [
        {
            "theme": "AI expansion",
            "description": "Multiple companies announced AI products. The trend accelerates.",
            "supporting_entities": ["OpenAI", "Google"],
            "confidence": "high",
        }
    ],
    "contradictions": [],
    "narrative": "This week in tech, AI was the dominant theme across all major news sources.",
    "top_stories": [{"entity": "OpenAI", "summary": "GPT-5 released."}],
    "cross_ref_count": 1,
})


def test_synthesizer_parses_valid_response():
    summaries = [
        ArticleSummary(
            entity="OpenAI",
            summary="OpenAI released GPT-5.",
            category="product_launch",
            sentiment="positive",
            confidence="high",
        )
    ]

    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=MOCK_DIGEST_RESPONSE)]
        )

        agent = SynthesizerAgent()
        result = agent.synthesize(summaries)

    assert result is not None
    assert result.headline == "AI dominates the week"
    assert len(result.themes) == 1
    assert result.themes[0].confidence == "high"


def test_synthesizer_returns_none_on_empty_input():
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_anthropic.return_value = MagicMock()
        agent = SynthesizerAgent()
        result = agent.synthesize([])

    assert result is None


# ---------- Earnings Output Schema ----------

def test_earnings_output_schema_matches_contract():
    """Validate the earnings JSON contract fields are all present."""
    output = EarningsOutput(
        company="Apple Inc",
        quarter="Q1 FY2026",
        revenue=RevenueData(actual=124.3, estimate=122.0, beat_pct=1.9),
        eps=EPSData(actual=2.40, estimate=2.35),
        segments={"iPhone": 69.1, "Services": 26.3},
        guidance_next_q=89.0,
        key_quotes=["We had a record quarter.", "Services continue to grow."],
        source="SEC 10-Q",
        confidence="high",
    )

    dumped = output.model_dump()
    required_keys = {"company", "quarter", "revenue", "eps", "segments",
                     "guidance_next_q", "key_quotes", "source", "confidence"}
    assert required_keys.issubset(dumped.keys())
    assert dumped["revenue"]["actual"] == 124.3
    assert dumped["cross_ref"] is True  # always True for earnings


# ---------- fact_guard Enforcement ----------

def test_fact_guard_nulls_unverifiable_number():
    """Numbers not found in source text must be cleared."""
    output = EarningsOutput(
        company="Acme Corp",
        quarter="Q2 FY2026",
        revenue=RevenueData(actual=999.9),  # not in source text
        eps=EPSData(actual=1.23),
        source="SEC 8-K",
        confidence="high",
    )
    source_text = "Acme reported EPS of $1.23 per diluted share."

    with patch("anthropic.Anthropic"):
        agent = EarningsAgent()
    result = agent._fact_guard_apply(output, source_text)

    assert result.revenue.actual is None, "Unverifiable revenue.actual should be cleared"
    assert result.eps.actual == 1.23, "Verifiable eps.actual should be kept"


def test_fact_guard_downgrades_confidence_on_violation():
    """Confidence must drop to low when any field is cleared."""
    output = EarningsOutput(
        company="Acme Corp",
        quarter="Q2 FY2026",
        revenue=RevenueData(actual=999.9),
        eps=EPSData(),
        source="SEC 8-K",
        confidence="high",
    )
    with patch("anthropic.Anthropic"):
        agent = EarningsAgent()
    result = agent._fact_guard_apply(output, "No financial figures here.")

    assert result.confidence == "low"


def test_fact_guard_clears_beat_pct_when_estimate_missing():
    """beat_pct must be nulled if estimate is absent after fact_guard clears it."""
    output = EarningsOutput(
        company="Acme Corp",
        quarter="Q2 FY2026",
        revenue=RevenueData(actual=50.0, estimate=None, beat_pct=3.2),
        eps=EPSData(),
        source="SEC 8-K",
        confidence="high",
    )
    source_text = "Revenue was $50.0 billion."
    with patch("anthropic.Anthropic"):
        agent = EarningsAgent()
    result = agent._fact_guard_apply(output, source_text)

    assert result.revenue.beat_pct is None, "beat_pct requires both actual and estimate"
    assert result.revenue.actual == 50.0, "Verifiable actual should remain"


def test_fact_guard_passes_clean_output():
    """No violations when all numbers appear verbatim in source."""
    output = EarningsOutput(
        company="Apple Inc",
        quarter="Q1 FY2026",
        revenue=RevenueData(actual=124.3, estimate=122.0),
        eps=EPSData(actual=2.40),
        guidance_next_q=89.0,
        source="SEC 10-Q",
        confidence="high",
    )
    source_text = (
        "Revenue was $124.3 billion versus estimates of $122.0 billion. "
        "EPS of $2.40. Guidance for next quarter is $89.0 billion."
    )
    with patch("anthropic.Anthropic"):
        agent = EarningsAgent()
    result = agent._fact_guard_apply(output, source_text)

    assert result.confidence == "high", "Clean output should keep original confidence"
    assert result.revenue.actual == 124.3
    assert result.eps.actual == 2.40


# ---------- Telegram Delivery ----------

def _make_digest() -> DigestOutput:
    from agents.synthesizer_agent import Theme
    return DigestOutput(
        date="2026-04-28",
        headline="AI dominates the week",
        themes=[Theme(
            theme="AI expansion",
            description="Multiple AI launches. Trend accelerates.",
            supporting_entities=["OpenAI"],
            confidence="high",
        )],
        contradictions=["Source A says X, Source B says Y."],
        narrative="Tech news was busy this week.",
        top_stories=[],
        cross_ref_count=2,
    )


def _make_earnings() -> EarningsOutput:
    return EarningsOutput(
        company="Apple Inc",
        quarter="Q1 FY2026",
        revenue=RevenueData(actual=124.3, estimate=122.0, beat_pct=1.9),
        eps=EPSData(actual=2.40, estimate=2.35),
        guidance_next_q=89.0,
        key_quotes=["Revenue was $124.3 billion."],
        source="SEC 10-Q",
        confidence="high",
    )


def test_telegram_bot_disabled_without_env():
    """TelegramBot._bot is None when token/channel env vars are absent."""
    with patch.dict("os.environ", {}, clear=False):
        # Ensure the keys are unset
        import os
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("TELEGRAM_CHANNEL_ID", None)
        bot = TelegramBot()
    assert bot._bot is None


def test_telegram_send_digest_returns_false_when_disabled():
    """send_digest returns False gracefully when bot not configured."""
    with patch.dict("os.environ", {}, clear=False):
        import os
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("TELEGRAM_CHANNEL_ID", None)
        bot = TelegramBot()
    result = bot.send_digest(_make_digest())
    assert result is False


def test_telegram_escape_special_chars():
    """All MarkdownV2 special characters must be escaped."""
    bot = TelegramBot.__new__(TelegramBot)  # bypass __init__
    special = r"\_*[]()~`>#+-=|{}.!"
    for ch in special:
        escaped = bot._escape(ch)
        assert escaped == f"\\{ch}", f"Expected \\{ch}, got {escaped}"


def test_telegram_format_digest_contains_key_sections():
    """Formatted digest must contain headline, themes, narrative, and cross_ref hint."""
    bot = TelegramBot.__new__(TelegramBot)
    digest = _make_digest()
    text = bot._format_digest(digest)

    assert "AI dominates the week" in text
    assert "AI expansion" in text
    assert "Tech news was busy this week" in text
    assert "2" in text  # cross_ref_count


def test_telegram_format_earnings_contains_financials():
    """Formatted earnings must show revenue, EPS, guidance, and cross_ref flag."""
    bot = TelegramBot.__new__(TelegramBot)
    earnings = _make_earnings()
    text = bot._format_earnings(earnings)

    assert "Apple Inc" in text
    assert "124" in text   # revenue
    assert "2.40" in text  # EPS
    assert "89" in text    # guidance
    assert "cross" in text.lower()


def test_telegram_message_chunking():
    """Messages exceeding 4096 chars must be split into chunks."""
    bot = TelegramBot.__new__(TelegramBot)
    bot._bot = MagicMock()
    bot._channel_id = "@test"

    long_text = "A" * 9000  # 9000 chars → 3 chunks of ≤4096

    sent_chunks = []

    async def mock_send(**kwargs):
        sent_chunks.append(kwargs["text"])

    bot._bot.send_message = mock_send

    import asyncio
    asyncio.run(bot._async_send(long_text))

    assert len(sent_chunks) == 3
    assert all(len(c) <= 4096 for c in sent_chunks)
    assert "".join(sent_chunks) == long_text


# ---------- Deduplicator ----------

def _tmp_dedup(tmp_path: Path) -> Deduplicator:
    return Deduplicator(db_path=tmp_path / "dedup.sqlite", ttl_hours=72)


def test_deduplicator_allows_new_item(tmp_path):
    dedup = _tmp_dedup(tmp_path)
    assert not dedup.is_duplicate("https://example.com/story-1", "Some content")


def test_deduplicator_detects_same_url(tmp_path):
    dedup = _tmp_dedup(tmp_path)
    dedup.mark_seen("https://example.com/story-1", "Some content")
    assert dedup.is_duplicate("https://example.com/story-1", "Different content")


def test_deduplicator_detects_same_content_different_url(tmp_path):
    dedup = _tmp_dedup(tmp_path)
    dedup.mark_seen("https://example.com/a", "Identical body text here")
    assert dedup.is_duplicate("https://other.com/b", "Identical body text here")


def test_deduplicator_strips_tracking_params(tmp_path):
    dedup = _tmp_dedup(tmp_path)
    clean_url = "https://techcrunch.com/article"
    tracked_url = "https://techcrunch.com/article?utm_source=twitter&utm_medium=social"
    dedup.mark_seen(clean_url, "")
    assert dedup.is_duplicate(tracked_url, "")


def test_deduplicator_filter_new_returns_only_new(tmp_path):
    dedup = _tmp_dedup(tmp_path)
    articles = [
        Article(title="Old Story", url="https://example.com/old", source="test"),
        Article(title="New Story", url="https://example.com/new", source="test"),
    ]
    # Mark the first one as already seen
    dedup.mark_seen("https://example.com/old", "Old Story")

    result = dedup.filter_new(articles)
    assert len(result) == 1
    assert result[0].url == "https://example.com/new"


def test_deduplicator_filter_new_marks_seen(tmp_path):
    dedup = _tmp_dedup(tmp_path)
    articles = [Article(title="Fresh", url="https://example.com/fresh", source="test")]
    dedup.filter_new(articles)
    # Second call should return empty — already marked
    result = dedup.filter_new(articles)
    assert len(result) == 0


def test_deduplicator_cleanup_expired(tmp_path):
    """cleanup_expired() should remove nothing when all records are fresh."""
    dedup = _tmp_dedup(tmp_path)
    dedup.mark_seen("https://example.com/x", "body")
    removed = dedup.cleanup_expired()
    assert removed == 0  # record is within TTL


# ---------- Scorer ----------

MOCK_SCORE_RESPONSE = json.dumps({"relevance": 8.0, "novelty": 7.0, "depth": 6.0, "score": 7.1})
MOCK_LOW_SCORE_RESPONSE = json.dumps({"relevance": 3.0, "novelty": 2.0, "depth": 2.0, "score": 2.3})


def test_scorer_parses_valid_response():
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text=MOCK_SCORE_RESPONSE)]
        )
        scorer = Scorer()
        result = scorer.score_item("OpenAI launches GPT-5", "Full article text here")

    assert result is not None
    assert result.score == pytest.approx(7.1)
    assert result.relevance == 8.0


def test_scorer_returns_none_on_invalid_json():
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="not json")]
        )
        scorer = Scorer()
        result = scorer.score_item("title", "text")
    assert result is None


def test_scorer_filter_articles_passes_above_threshold():
    articles = [
        Article(title="High quality story", url="https://example.com/1", source="test"),
        Article(title="Low quality story", url="https://example.com/2", source="test"),
    ]
    responses = [MOCK_SCORE_RESPONSE, MOCK_LOW_SCORE_RESPONSE]

    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = [
            MagicMock(content=[MagicMock(text=r)]) for r in responses
        ]
        scorer = Scorer()
        # default threshold is 6.0; score 7.1 passes, 2.3 fails
        result = scorer.filter_articles(articles)

    assert len(result) == 1
    assert result[0].title == "High quality story"
    assert result[0].score == pytest.approx(7.1)


def test_scorer_fail_open_on_api_error():
    """If scoring fails, include the article (fail-open to avoid over-filtering)."""
    articles = [Article(title="Story", url="https://example.com/1", source="test")]
    with patch("anthropic.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API error")
        scorer = Scorer()
        result = scorer.filter_articles(articles)

    assert len(result) == 1
    assert result[0].score == 0.0


def test_article_score_field_default():
    article = Article(title="Test", url="https://example.com", source="test")
    assert article.score == 0.0


def test_article_summary_carries_score():
    summary = ArticleSummary(
        entity="Test",
        summary="Test summary.",
        category="other",
        sentiment="neutral",
        confidence="high",
        score=7.5,
    )
    assert summary.score == 7.5
