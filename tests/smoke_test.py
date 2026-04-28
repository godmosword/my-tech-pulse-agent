"""Smoke tests: validate pipeline stages without hitting live APIs."""

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.extractor_agent import ArticleSummary, ExtractorAgent
from agents.synthesizer_agent import DigestOutput, SynthesizerAgent
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
    from agents.earnings_agent import EarningsOutput, RevenueData, EPSData

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
