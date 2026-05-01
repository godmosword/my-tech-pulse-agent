"""Smoke tests: validate pipeline stages without hitting live APIs."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import pipeline.crew as crew_module
from agents.earnings_agent import EarningsAgent, EarningsOutput, EPSData, RevenueData
from agents.deep_insight_agent import ArgumentMap, InsightBrief
from agents.extractor_agent import ArticleSummary, ExtractorAgent
from agents.synthesizer_agent import DigestOutput, SynthesizerAgent
from delivery.message_formatter import format_insight_brief
from delivery.telegram_bot import TelegramBot
from scoring.deduplicator import Deduplicator
from scoring.scorer import ScoreResult, Scorer
from sources.deep_scraper import DeepScraper
from sources.rss_fetcher import Article, RSSFetcher, clean_feed_text
from scripts.preflight import _failures as preflight_failures
from llm.gemini_client import _extract_json_object
from pipeline.crew import TechPulseCrew


def _gemini_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


def _mock_gemini_client(response_text: str | list[str] | None = None, raise_error: bool = False):
    """可靠的 Gemini mock，直接 patch make_client()，解決 lazy import 問題"""
    from contextlib import ExitStack

    mock_client = MagicMock()

    if raise_error:
        mock_client.models.generate_content.side_effect = Exception("Simulated API error")
    elif isinstance(response_text, str):
        mock_client.models.generate_content.return_value = _gemini_response(response_text)
    elif isinstance(response_text, list):
        mock_client.models.generate_content.side_effect = [
            _gemini_response(t) for t in response_text
        ]
    else:
        mock_client.models.generate_content.return_value = _gemini_response("{}")

    def _mock_make_client():
        return mock_client

    class _Patcher:
        def __enter__(self):
            self._stack = ExitStack()
            self._stack.enter_context(patch("agents.extractor_agent.make_client", new=_mock_make_client))
            self._stack.enter_context(patch("agents.deep_insight_agent.make_client", new=_mock_make_client))
            self._stack.enter_context(patch("agents.synthesizer_agent.make_client", new=_mock_make_client))
            self._stack.enter_context(patch("scoring.scorer.make_client", new=_mock_make_client))
            return mock_client

        def __exit__(self, exc_type, exc, tb):
            return self._stack.__exit__(exc_type, exc, tb)

    return _Patcher()

@pytest.fixture(autouse=True)
def _set_test_gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")


# ---------- Configuration ----------

def test_env_example_uses_gemini_keys_only():
    env_example = Path(".env.example").read_text()
    assert "GEMINI_API_KEY" in env_example
    assert "GEMINI_MODEL=gemini-3.1-pro-preview" in env_example
    assert "GEMINI_FLASH_MODEL=gemini-3-flash-preview" in env_example
    old_keys = [
        "".join(("ANTH", "ROPIC", "_API_KEY")),
        "".join(("CLA", "UDE", "_MODEL")),
        "".join(("HA", "IKU", "_MODEL")),
    ]
    assert all(key not in env_example for key in old_keys)


def test_preflight_passes_with_required_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-telegram-token")
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", "@test")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")
    assert preflight_failures() == []


def test_extract_json_object_from_wrapped_text():
    text = 'Here is the JSON requested:\n```json\n{"score": 1, "nested": {"ok": true}}\n```'
    assert _extract_json_object(text) == '{"score": 1, "nested": {"ok": true}}'


# ---------- RSS Fetcher ----------

def test_rss_fetcher_loads_registry():
    fetcher = RSSFetcher()
    assert len(fetcher._registry) > 0, "Source registry should have at least one news source"


def test_clean_feed_text_removes_html_entities_and_feed_footers():
    html = (
        "<p><em>Welcome to Web3 Water Cooler</em> with participants and NFTs...</p>"
        '<p><a href="https://example.com">Read More</a></p>'
        '<p>The post <a href="https://example.com">Thinking Through CC0</a> '
        'appeared first on <a href="https://future.com">Future</a>.</p>'
        "It&#8217;s useful."
    )

    text = clean_feed_text(html)

    assert "<p>" not in text
    assert "&#8217;" not in text
    assert "Read More" not in text
    assert "appeared first" not in text
    assert "It’s useful" in text


def test_article_model_validates():
    article = Article(title="Test", url="https://example.com", source="test_rss")
    assert article.cross_ref is False
    assert article.tier == "instant"
    assert article.domain == []


def test_article_model_rejects_missing_url():
    with pytest.raises(Exception):
        Article(title="Test", source="test_rss")  # url is required


def test_deep_scraper_requires_apify_key(monkeypatch):
    monkeypatch.delenv("APIFY_API_KEY", raising=False)

    result = DeepScraper().fetch("https://example.com/post")

    assert result.status == "missing_apify_key"


def test_deep_scraper_fetches_text_from_apify_dataset():
    run_response = MagicMock()
    run_response.json.return_value = {"data": {"id": "run-1"}}
    run_response.raise_for_status.return_value = None

    status_response = MagicMock()
    status_response.json.return_value = {"data": {"status": "SUCCEEDED"}}
    status_response.raise_for_status.return_value = None

    dataset_response = MagicMock()
    dataset_response.json.return_value = [{"text": "KV cache " * 20}]
    dataset_response.raise_for_status.return_value = None

    with patch("httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.post.return_value = run_response
        client.get.side_effect = [status_response, dataset_response]
        result = DeepScraper(min_words=10, apify_key="key").fetch("https://example.com/post")

    assert result.status == "ok"
    assert result.word_count >= 10
    assert "KV cache" in result.text


def test_deep_scraper_fetch_marks_too_short():
    run_response = MagicMock()
    run_response.json.return_value = {"data": {"id": "run-1"}}
    run_response.raise_for_status.return_value = None

    status_response = MagicMock()
    status_response.json.return_value = {"data": {"status": "SUCCEEDED"}}
    status_response.raise_for_status.return_value = None

    dataset_response = MagicMock()
    dataset_response.json.return_value = [{"text": "Short public post."}]
    dataset_response.raise_for_status.return_value = None

    with patch("httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.post.return_value = run_response
        client.get.side_effect = [status_response, dataset_response]
        result = DeepScraper(min_words=10, apify_key="key").fetch("https://example.com/post")

    assert result.status == "too_short"
    assert result.word_count < 10


def test_deep_scraper_fetch_handles_failure():
    with patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.side_effect = RuntimeError("network")
        result = DeepScraper(apify_key="key").fetch("https://example.com/post")

    assert result.status == "fetch_failed"


def test_deep_scraper_handles_apify_rate_limit():
    import httpx

    request = httpx.Request("POST", "https://api.apify.com")
    response = httpx.Response(429, request=request)

    with patch("httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.side_effect = httpx.HTTPStatusError(
            "rate limited",
            request=request,
            response=response,
        )
        result = DeepScraper(apify_key="key").fetch("https://example.com/post")

    assert result.status == "rate_limited"


def test_tier_detection_marks_kol_and_paper_deep():
    assert TechPulseCrew._is_deep_candidate(
        Article(title="KOL", url="https://example.com/kol", source="x", label="kol")
    )
    assert TechPulseCrew._is_deep_candidate(
        Article(title="Paper", url="https://example.com/paper", source="x", label="paper")
    )
    assert not TechPulseCrew._is_deep_candidate(
        Article(title="News", url="https://example.com/news", source="x")
    )


def test_deep_pipeline_respects_cap_and_fallback(monkeypatch):
    class FakeScraper:
        def fetch(self, url, min_words=None):
            from sources.deep_scraper import DeepScrapeResult
            return DeepScrapeResult(url=url, text="技術" * 500, word_count=1000, status="ok")

    class FakeDeepAgent:
        def create_brief(self, **kwargs):
            return _valid_brief(title=kwargs["title"], url=kwargs["url"], item_id=kwargs["item_id"])

    monkeypatch.setattr(crew_module, "MAX_DEEP_ARTICLES", 1)
    crew = TechPulseCrew.__new__(TechPulseCrew)
    crew.deep_scraper = FakeScraper()
    crew.deep_agent = FakeDeepAgent()
    crew._save_json = lambda *args, **kwargs: None
    articles = [
        Article(title="Deep 1", url="https://example.com/1", source="kol", tier="deep", score=9.0),
        Article(title="Deep 2", url="https://example.com/2", source="kol", tier="deep", score=8.0),
    ]

    briefs, fallbacks, consumed = crew._run_deep_pipeline(articles, "20260101")

    assert len(briefs) == 1
    assert len(fallbacks) == 1
    assert fallbacks[0].deep_status == "over_deep_cap"
    assert consumed == {"https://example.com/1"}


def test_short_deep_article_downgrades_to_instant(monkeypatch):
    class FakeScraper:
        def fetch(self, url, min_words=None):
            from sources.deep_scraper import DeepScrapeResult
            return DeepScrapeResult(url=url, text="short", word_count=1, status="too_short")

    monkeypatch.setattr(crew_module, "MAX_DEEP_ARTICLES", 3)
    crew = TechPulseCrew.__new__(TechPulseCrew)
    crew.deep_scraper = FakeScraper()
    crew.deep_agent = MagicMock()
    crew._save_json = lambda *args, **kwargs: None
    article = Article(title="Short KOL", url="https://example.com/short", source="kol", tier="deep")

    briefs, fallbacks, consumed = crew._run_deep_pipeline([article], "20260101")

    assert briefs == []
    assert fallbacks == [article]
    assert consumed == set()
    assert article.deep_status == "too_short"
    crew.deep_agent.create_brief.assert_not_called()


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
    with _mock_gemini_client(MOCK_EXTRACTOR_RESPONSE):
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


def test_extractor_batch_respects_runtime_cap(monkeypatch):
    monkeypatch.setenv("MAX_EXTRACTION_ARTICLES", "2")
    articles = [
        {"title": f"Story {idx}", "summary": "OpenAI announced a product.", "source": "test"}
        for idx in range(4)
    ]

    with _mock_gemini_client([MOCK_EXTRACTOR_RESPONSE, MOCK_EXTRACTOR_RESPONSE]) as mock_client:
        agent = ExtractorAgent()
        result = agent.extract_batch(articles)

    assert len(result) == 2
    assert mock_client.models.generate_content.call_count == 2


def test_extractor_returns_none_on_invalid_json():
    with patch("google.genai.Client") as mock_gemini:
        mock_client = MagicMock()
        mock_gemini.return_value = mock_client
        mock_client.models.generate_content.return_value = _gemini_response("not valid json")

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


# ---------- Deep Insight Agent Schemas ----------

def _valid_brief(**kwargs) -> InsightBrief:
    defaults = {
        "item_id": "abc12345",
        "title": "KV cache changes inference economics",
        "author": "Analyst",
        "source_name": "test_source",
        "url": "https://example.com/deep",
        "domain": "ai",
        "insight": "洞見" * 25,
        "tech_rationale": "技術底層" * 20,
        "implication": "產業影響" * 15,
        "confidence": "high",
    }
    defaults.update(kwargs)
    return InsightBrief(**defaults)


def test_argument_map_schema_validates():
    output = ArgumentMap(
        title="MoE routing analysis",
        author="Researcher",
        source_name="arxiv_cs_ai",
        url="https://example.com/paper",
        domain="ai",
        core_thesis="Routing capacity, not parameter count, drives the result.",
        evidence=["The paper reports a KV cache bottleneck."],
        assumption="Inference workloads remain memory-bound.",
        counter_ignored="Hardware scheduler overhead may dominate.",
        score=8.1,
        confidence="high",
        item_id="deadbeef",
    )

    assert output.tier == "deep"
    assert output.evidence


def test_deep_agent_downgrades_low_lexicon_density():
    with _mock_gemini_client():
        agent = __import__("agents.deep_insight_agent", fromlist=["DeepInsightAgent"]).DeepInsightAgent()

    argument = ArgumentMap(
        title="Generic AI strategy",
        author="Analyst",
        source_name="test_source",
        url="https://example.com/deep",
        domain="ai",
        core_thesis="The author believes the market will change.",
        evidence=["The article says adoption is increasing."],
        assumption="Customers keep buying.",
        counter_ignored="Competition could respond.",
        score=8.0,
        confidence="high",
        item_id="abc12345",
    )

    reviewed = agent.review_argument_map(argument)

    assert reviewed is not None
    assert reviewed.confidence == "low"


def test_deep_agent_keeps_confidence_with_domain_lexicon_signal():
    with _mock_gemini_client():
        agent = __import__("agents.deep_insight_agent", fromlist=["DeepInsightAgent"]).DeepInsightAgent()

    argument = ArgumentMap(
        title="KV cache economics",
        author="Analyst",
        source_name="test_source",
        url="https://example.com/deep",
        domain="ai",
        core_thesis="KV cache pressure changes inference economics.",
        evidence=["The source says KV cache and memory bandwidth constrain inference latency."],
        assumption="Inference workloads remain memory-bound.",
        counter_ignored="Compiler optimizations may reduce pressure.",
        score=8.0,
        confidence="high",
        item_id="abc12345",
    )

    reviewed = agent.review_argument_map(argument)

    assert reviewed is not None
    assert reviewed.confidence == "high"


def test_insight_brief_enforces_100_to_200_chars():
    brief = _valid_brief()
    assert 100 <= brief.word_count <= 200

    with pytest.raises(ValueError):
        _valid_brief(insight="太短", tech_rationale="不足", implication="不足")


def test_format_insight_brief_markdownv2():
    brief = _valid_brief(confidence="low", cross_ref=True)

    text = format_insight_brief(brief)

    assert "🧠" in text
    assert "低信心度" in text
    assert "洞見" in text
    assert "[原文](https://example.com/deep)" in text
    assert "投資日報" in text


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

    with _mock_gemini_client(MOCK_DIGEST_RESPONSE):
        agent = SynthesizerAgent()
        result = agent.synthesize(summaries)

    assert result is not None
    assert result.headline == "AI dominates the week"
    assert len(result.themes) == 1
    assert result.themes[0].confidence == "high"


def test_synthesizer_returns_none_on_empty_input():
    with patch("google.genai.Client") as mock_gemini:
        mock_gemini.return_value = MagicMock()
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

    with patch("google.genai.Client"):
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
    with patch("google.genai.Client"):
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
    with patch("google.genai.Client"):
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
    with patch("google.genai.Client"):
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
    from delivery.message_formatter import format_earnings as _fmt_e
    earnings = _make_earnings()
    text = _fmt_e(earnings)

    assert "Apple Inc" in text
    assert "124" in text   # revenue
    assert "2" in text     # EPS (escaped as 2\.40 in MarkdownV2)
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


def test_deduplicator_filter_new_claims_atomically(tmp_path):
    dedup = _tmp_dedup(tmp_path)
    article = Article(title="Same", url="https://example.com/same", source="test", summary="Body")

    first = dedup.filter_new([article])
    second = dedup.filter_new([article])

    assert first == [article]
    assert second == []


def test_deduplicator_filter_unseen_does_not_mark_seen(tmp_path):
    dedup = _tmp_dedup(tmp_path)
    article = Article(title="Fresh", url="https://example.com/fresh", source="test", summary="Body")

    first = dedup.filter_unseen([article])
    second = dedup.filter_unseen([article])

    assert first == [article]
    assert second == [article]


# ---------- Scorer ----------

MOCK_SCORE_RESPONSE = json.dumps({"relevance": 9.0, "novelty": 8.0, "depth": 8.0, "score": 8.5})
MOCK_LOW_SCORE_RESPONSE = json.dumps({"relevance": 3.0, "novelty": 2.0, "depth": 2.0, "score": 2.3})


def test_scorer_parses_valid_response():
    with _mock_gemini_client(MOCK_SCORE_RESPONSE):
        scorer = Scorer()
        result = scorer.score_item("OpenAI launches GPT-5", "Full article text here")

    assert result is not None
    assert result.score == pytest.approx(8.5)
    assert result.relevance == 9.0


def test_scorer_returns_none_on_invalid_json():
    with patch("google.genai.Client") as mock_gemini:
        mock_client = MagicMock()
        mock_gemini.return_value = mock_client
        mock_client.models.generate_content.return_value = _gemini_response("not json")
        scorer = Scorer()
        result = scorer.score_item("title", "text")
    assert result is None


def test_scorer_lexicon_match_scores_title_and_lede():
    with _mock_gemini_client(MOCK_SCORE_RESPONSE):
        scorer = Scorer()
        result = scorer.match_lexicon(
            "KV cache and memory bandwidth bottlenecks",
            "This is not just a powerful AI breakthrough story.",
        )

    assert result.lexicon_score == pytest.approx(5.2)
    assert "ai.high:KV cache" in result.matched_signals
    assert "ai.high:memory bandwidth" in result.matched_signals
    assert "ai.low:powerful AI" in result.matched_signals
    assert "ai.low:breakthrough" in result.matched_signals


def test_scorer_filter_articles_passes_above_threshold():
    articles = [
        Article(
            title="OpenAI launches new enterprise AI model",
            url="https://example.com/1",
            source="test",
            summary="OpenAI announced a new enterprise AI model with benchmark details.",
        ),
        Article(
            title="Google cloud AI update",
            url="https://example.com/2",
            source="test",
            summary="Google reported a cloud AI product update with pricing details.",
        ),
    ]
    with _mock_gemini_client([MOCK_SCORE_RESPONSE, MOCK_LOW_SCORE_RESPONSE]):
        scorer = Scorer()
        # default threshold is 7.2; score 8.5 passes, 2.3 fails
        result = scorer.filter_articles(articles)

    assert len(result) == 1
    assert result[0].title == "OpenAI launches new enterprise AI model"
    assert result[0].score == pytest.approx(8.5)


def test_scorer_filter_articles_respects_runtime_cap(monkeypatch):
    monkeypatch.setenv("MAX_SCORING_ARTICLES", "2")
    articles = [
        Article(
            title=f"Nvidia AI chip story {idx}",
            url=f"https://example.com/{idx}",
            source="test",
            summary="Nvidia announced an AI chip for data center infrastructure.",
        )
        for idx in range(4)
    ]

    with _mock_gemini_client([MOCK_SCORE_RESPONSE, MOCK_SCORE_RESPONSE]) as mock_client:
        scorer = Scorer()
        result = scorer.filter_articles(articles)

    assert len(result) == 2
    assert mock_client.models.generate_content.call_count == 2


def test_scorer_prefilter_drops_obvious_low_signal_article():
    articles = [
        Article(
            title="Best streaming deals",
            url="https://example.com/deals",
            source="test",
            summary="Coupon promo code discount gift guide.",
        ),
        Article(
            title="Nvidia launches new AI data center GPU",
            url="https://example.com/gpu",
            source="test",
            summary="Nvidia announced a new AI data center GPU with 30% faster inference.",
        ),
    ]

    with _mock_gemini_client(MOCK_SCORE_RESPONSE) as mock_client:
        scorer = Scorer()
        result = scorer.filter_articles(articles)

    assert len(result) == 1
    assert result[0].title == "Nvidia launches new AI data center GPU"
    assert articles[0].score_status == "prefiltered_out"
    assert mock_client.models.generate_content.call_count == 1


def test_scorer_annotates_lexicon_match_before_prefilter_drop():
    articles = [
        Article(
            title="Powerful AI breakthrough deal",
            url="https://example.com/ai-deal",
            source="test",
            summary="Coupon promo code discount gift guide.",
        )
    ]

    with _mock_gemini_client(MOCK_SCORE_RESPONSE):
        scorer = Scorer()
        result = scorer.filter_articles(articles)

    assert result == []
    assert articles[0].score_status == "prefiltered_out"
    assert articles[0].lexicon_score == pytest.approx(4.4)
    assert articles[0].matched_signals == [
        "ai.low:powerful AI",
        "ai.low:breakthrough",
    ]


def test_scorer_prefilter_bypasses_kol_articles():
    kol_article = Article(
        title="Platform strategy",
        url="https://example.com/kol",
        source="stratechery",
        summary="Essay.",
        label="kol",
        author="Ben Thompson",
    )

    with _mock_gemini_client(MOCK_SCORE_RESPONSE) as mock_client:
        scorer = Scorer()
        result = scorer.filter_articles([kol_article])

    assert len(result) == 1
    assert result[0].base_score == 1.0
    assert result[0].base_score_status == "kol_bypass"
    assert mock_client.models.generate_content.call_count == 1


def test_scorer_fail_open_on_api_error():
    """If scoring fails, include the article (fail-open to avoid over-filtering)."""
    articles = [
        Article(
            title="Microsoft launches AI cloud security service",
            url="https://example.com/1",
            source="test",
            summary="Microsoft announced an AI security service for enterprise cloud customers.",
        )
    ]
    with _mock_gemini_client(raise_error=True):
        scorer = Scorer()
        result = scorer.filter_articles(articles)

    assert len(result) == 1
    assert result[0].score == 0.0
    assert result[0].score_status == "fallback"


def test_scorer_retries_once_on_non_json_response():
    article = Article(
        title="Microsoft launches AI cloud security service",
        url="https://example.com/1",
        source="test",
        summary="Microsoft announced an AI security service for enterprise cloud customers.",
    )
    responses = [
        "Here is the",
        '{"relevance": 8, "novelty": 7, "depth": 7, "score": 7.4}',
    ]
    with _mock_gemini_client(responses) as mock_client:
        scorer = Scorer()
        result = scorer.filter_articles([article])

    assert mock_client.models.generate_content.call_count == 2
    assert len(result) == 1
    assert result[0].score_status == "scored"
    assert result[0].score == 7.4


def test_scorer_parse_failure_uses_fallback_item():
    article = Article(
        title="Microsoft launches AI cloud security service",
        url="https://example.com/1",
        source="test",
        summary="Microsoft announced an AI security service for enterprise cloud customers.",
    )
    responses = ["Here is the JSON requested:", "Here is the JSON requested:"]
    with _mock_gemini_client(responses) as mock_client:
        scorer = Scorer()
        result = scorer.filter_articles([article])

    assert mock_client.models.generate_content.call_count == 2
    assert len(result) == 1
    assert result[0].score == 0.0
    assert result[0].score_status == "fallback"


def test_article_score_field_default():
    article = Article(title="Test", url="https://example.com", source="test")
    assert article.score == 0.0
    assert article.score_status == "ok"
    assert article.lexicon_score == 5.0
    assert article.matched_signals == []


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


def test_article_summary_has_title_field():
    summary = ArticleSummary(
        entity="Test",
        summary="Test summary.",
        category="other",
        sentiment="neutral",
        confidence="high",
        title="My Article Title",
    )
    assert summary.title == "My Article Title"


# ---------- MessageFormatter ----------

from delivery.message_formatter import escape, format_items_digest, format_earnings as fmt_earnings


def test_escape_markdownv2_special_chars():
    special = r"\_*[]()~`>#+-=|{}.!"
    for ch in special:
        assert escape(ch) == f"\\{ch}", f"char {ch!r} not escaped"


def test_format_items_digest_structure():
    summaries = [
        ArticleSummary(
            entity="OpenAI",
            summary="OpenAI released a new model with advanced capabilities.",
            category="product_launch",
            sentiment="positive",
            confidence="high",
            title="OpenAI Launches New Model",
            source_name="TechCrunch",
            source_url="https://techcrunch.com/1",
            score=8.5,
            cross_ref=True,
        ),
        ArticleSummary(
            entity="Google",
            summary="Google announced cloud services expansion across Asia.",
            category="other",
            sentiment="neutral",
            confidence="medium",
            title="Google Expands Cloud",
            source_name="Wired",
            source_url="https://wired.com/2",
            score=6.0,
        ),
    ]
    from datetime import datetime, timezone
    now = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)
    text = format_items_digest(summaries, total_fetched=50, total_after_filter=2, now=now)

    assert "科技脈搆" in text or "科技脈搏" in text
    assert "2026/04/28" in text
    assert "8" in text          # score
    assert "OpenAI" in text
    assert "投資日報" in text   # cross_ref indicator
    assert "精選" in text       # new quality-signal footer
    assert "平均評分" in text


def test_format_items_digest_sorted_by_score():
    low = ArticleSummary(
        entity="Low", summary="Low score item.", category="other",
        sentiment="neutral", confidence="low", score=3.0,
    )
    high = ArticleSummary(
        entity="High", summary="High score item.", category="other",
        sentiment="positive", confidence="high", score=9.0,
    )
    text = format_items_digest([low, high], 10, 2)
    assert text.index("High") < text.index("Low")


def test_format_items_digest_hides_zero_score_when_enough_valid_items():
    valid_items = [
        ArticleSummary(
            entity=f"Valid{i}",
            summary="Valid scored item.",
            category="other",
            sentiment="neutral",
            confidence="high",
            score=7.0 - i * 0.1,
            score_status="ok",
        )
        for i in range(5)
    ]
    zero_item = ArticleSummary(
        entity="ZeroScore",
        summary="Should normally be hidden.",
        category="other",
        sentiment="neutral",
        confidence="low",
        score=0.0,
        score_status="ok",
    )
    text = format_items_digest(valid_items + [zero_item], 12, 6)
    assert "⭐ 0.0" not in text
    assert "ZeroScore" not in text


def test_format_earnings_markdownv2():
    earnings = _make_earnings()
    text = fmt_earnings(earnings)
    assert "Apple Inc" in text
    assert "124" in text
    assert "2" in text and "40" in text   # EPS: escaped as 2\.40 in MarkdownV2
    assert "cross" in text.lower()


# ---------- FeedbackHandler ----------

from delivery.feedback_handler import build_keyboard, parse_callback, handle_callback


def test_build_keyboard_structure():
    kb = build_keyboard("item-123", "techcrunch_rss")
    assert "inline_keyboard" in kb
    buttons = kb["inline_keyboard"][0]
    actions = [b["callback_data"].split(":")[0] for b in buttons]
    assert "useful" in actions
    assert "save" in actions
    assert "block_source" in actions


def test_parse_callback_valid():
    action, payload = parse_callback("useful:techcrunch_rss")
    assert action == "useful"
    assert payload == "techcrunch_rss"


def test_parse_callback_unknown():
    action, payload = parse_callback("nocolon")
    assert action == "unknown"


def test_handle_save_callback(tmp_path):
    result = handle_callback("save:item-abc", db_path=tmp_path / "dedup.sqlite")
    assert "item-abc" in result
    # saved_items table should have a row
    import sqlite3
    with sqlite3.connect(tmp_path / "dedup.sqlite") as conn:
        row = conn.execute("SELECT item_id FROM saved_items WHERE item_id='item-abc'").fetchone()
    assert row is not None


# ---------- Reviewer Agent ----------

from agents.reviewer_agent import ReviewerAgent, ReviewerOutput

MOCK_REVIEWER_CLEAN = json.dumps({
    "fact_error": False,
    "inferred": False,
    "needs_retry": False,
    "review_comment": None,
})

MOCK_REVIEWER_INFERRED = json.dumps({
    "fact_error": False,
    "inferred": True,
    "needs_retry": False,
    "review_comment": None,
})

MOCK_REVIEWER_NEEDS_RETRY = json.dumps({
    "fact_error": False,
    "inferred": False,
    "needs_retry": True,
    "review_comment": "Signal is generic — no specific company or mechanism named.",
})

MOCK_REVIEWER_FACT_ERROR = json.dumps({
    "fact_error": True,
    "inferred": False,
    "needs_retry": False,
    "review_comment": None,
})


def _make_summary(**kwargs) -> ArticleSummary:
    defaults = dict(
        entity="OpenAI",
        summary="OpenAI raised $100M.",
        what_happened="OpenAI raised $100M in Series B funding.",
        why_it_matters="This positions OpenAI to compete with Google DeepMind.",
        category="funding",
        sentiment="positive",
        confidence="high",
        source_url="https://techcrunch.com/openai",
        source_name="techcrunch_rss",
        title="OpenAI Raises $100M",
        score=8.0,
        source_text="OpenAI today announced a $100M Series B round led by a16z.",
    )
    defaults.update(kwargs)
    return ArticleSummary(**defaults)


def _mock_reviewer_client(response_text: str | list[str] | None = None, raise_error: bool = False):
    """Mock that patches both reviewer and extractor make_client."""
    from contextlib import ExitStack

    mock_client = MagicMock()
    if raise_error:
        mock_client.models.generate_content.side_effect = Exception("API error")
    elif isinstance(response_text, list):
        mock_client.models.generate_content.side_effect = [
            _gemini_response(t) for t in response_text
        ]
    else:
        mock_client.models.generate_content.return_value = _gemini_response(
            response_text or "{}"
        )

    def _mock_make_client():
        return mock_client

    class _Patcher:
        def __enter__(self):
            self._stack = ExitStack()
            self._stack.enter_context(patch("agents.reviewer_agent.make_client", new=_mock_make_client))
            self._stack.enter_context(patch("agents.extractor_agent.make_client", new=_mock_make_client))
            return mock_client

        def __exit__(self, exc_type, exc, tb):
            return self._stack.__exit__(exc_type, exc, tb)

    return _Patcher()


def test_reviewer_approves_clean_summary():
    summary = _make_summary()
    with _mock_reviewer_client(MOCK_REVIEWER_CLEAN):
        agent = ReviewerAgent()
        result = agent.review(summary)

    assert isinstance(result, ReviewerOutput)
    assert result.approved is True
    assert result.fact_error is False
    assert result.inferred is False
    assert result.needs_retry is False
    assert result.final_output is not None
    assert result.final_output.confidence == "high"


def test_reviewer_prepends_inferred_to_signal():
    summary = _make_summary()
    with _mock_reviewer_client(MOCK_REVIEWER_INFERRED):
        agent = ReviewerAgent()
        result = agent.review(summary)

    assert result.approved is True
    assert result.inferred is True
    assert result.final_output is not None
    assert result.final_output.why_it_matters.startswith("[INFERRED]")


def test_reviewer_flags_fact_error_and_still_approves():
    summary = _make_summary()
    with _mock_reviewer_client(MOCK_REVIEWER_FACT_ERROR):
        agent = ReviewerAgent()
        result = agent.review(summary)

    assert result.fact_error is True
    assert result.approved is True  # fact_error still delivers, doesn't block


def test_reviewer_retry_degrades_confidence():
    """On needs_retry=True and failed retry, confidence must be 'low'."""
    # First call → needs_retry; second call (retry extraction) → extractor response
    responses = [MOCK_REVIEWER_NEEDS_RETRY, MOCK_EXTRACTOR_RESPONSE]
    summary = _make_summary()
    with _mock_reviewer_client(responses):
        agent = ReviewerAgent()
        result = agent.review(summary)

    assert result.approved is True
    assert result.final_output is not None
    assert result.final_output.confidence == "low"


def test_reviewer_fails_open_on_api_error():
    """If LLM call fails, reviewer must pass through the summary unchanged."""
    summary = _make_summary()
    with _mock_reviewer_client(raise_error=True):
        agent = ReviewerAgent()
        result = agent.review(summary)

    assert result.approved is True
    assert result.final_output is not None
    assert result.final_output.entity == "OpenAI"


def test_reviewer_batch_processes_all_items():
    summaries = [_make_summary(), _make_summary(entity="Google", title="Google News")]
    responses = [MOCK_REVIEWER_CLEAN, MOCK_REVIEWER_CLEAN]
    with _mock_reviewer_client(responses):
        agent = ReviewerAgent()
        results = agent.review_batch(summaries)

    assert len(results) == 2
    assert all(r.approved for r in results)


def test_reviewer_output_model_fields():
    output = ReviewerOutput(
        item_id="abc12345",
        approved=True,
        needs_retry=False,
        fact_error=False,
        inferred=False,
        review_comment=None,
        final_output=None,
    )
    assert output.item_id == "abc12345"
    assert output.final_output is None


# ---------- KOL Source Registry ----------

def test_kol_registry_loads():
    from sources.rss_fetcher import KOL_REGISTRY_PATH
    assert KOL_REGISTRY_PATH.exists(), "kol_registry.yaml must exist"
    import yaml
    with open(KOL_REGISTRY_PATH) as f:
        data = yaml.safe_load(f)
    assert "kol_sources" in data
    assert len(data["kol_sources"]) >= 5


def test_a16z_archive_feed_is_disabled():
    from sources.rss_fetcher import KOL_REGISTRY_PATH
    import yaml
    with open(KOL_REGISTRY_PATH) as f:
        data = yaml.safe_load(f)

    a16z = next(item for item in data["kol_sources"] if item["name"] == "a16z_blog")
    assert a16z["enabled"] is False
    assert a16z["url"] != "https://future.com/feed"


def test_rss_fetcher_loads_kol_registry():
    fetcher = RSSFetcher()
    assert len(fetcher._kol_registry) >= 5, "Should have at least 5 KOL sources"


def test_article_label_defaults_to_news():
    article = Article(title="Test", url="https://example.com", source="rss")
    assert article.label == "news"
    assert article.author == ""


def test_article_kol_label_and_author():
    article = Article(title="Analysis", url="https://stratechery.com/1", source="stratechery", label="kol", author="Ben Thompson")
    assert article.label == "kol"
    assert article.author == "Ben Thompson"


def test_scorer_uses_kol_weights_for_kol_articles():
    """KOL articles should use the kol_weights prompt, not the default weights prompt."""
    kol_article = Article(
        title="Platform Theory in 2026",
        url="https://stratechery.com/2",
        source="stratechery",
        label="kol",
        author="Ben Thompson",
    )
    with _mock_gemini_client(MOCK_SCORE_RESPONSE) as mock_client:
        scorer = Scorer()
        scorer.filter_articles([kol_article])

    call_args = mock_client.models.generate_content.call_args
    prompt_text = str(call_args)
    # KOL prompt includes "Author:" field
    assert "Author:" in prompt_text or "Ben Thompson" in prompt_text
