from pipeline.crew import TechPulseCrew
from sources.rss_fetcher import Article
from delivery.message_formatter import format_items_digest
from scoring.memory_store import MemorySearchResult


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

    # When RSS summary is empty, fallback uses the title as last resort
    assert "Thin RSS item" in msg
    assert len(summaries) == 1
    assert summaries[0].what_happened  # should never be empty


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

    summaries = crew._ensure_minimum_summaries([], articles, articles)
    msg = format_items_digest(summaries, total_fetched=10, total_after_filter=4)

    assert len(summaries) == 3
    assert "Fallback 0" in msg
    assert "Fallback 1" in msg
    assert "Fallback 2" in msg
    assert "Fallback 3" not in msg
    # Footer now shows "快訊 N 則" instead of "全部待確認" for cleaner UX
    assert "快訊" in msg


def test_ensure_minimum_summaries_uses_scored_pool_when_instant_is_thin(monkeypatch):
    """Regression: thin instant pool used to block MIN_DIGEST padding (plan digest investigation)."""
    monkeypatch.setattr("pipeline.crew.MIN_DIGEST_ITEMS", 3)
    crew = TechPulseCrew.__new__(TechPulseCrew)
    instant = [
        Article(
            title="Instant only",
            url="https://example.com/a",
            source="News",
            summary="One instant story.",
            score=8.6,
            score_status="scored",
        )
    ]
    scored = instant + [
        Article(
            title="Extra scored B",
            url="https://example.com/b",
            source="News",
            summary="Second story body.",
            score=8.0,
            score_status="scored",
        ),
        Article(
            title="Extra scored C",
            url="https://example.com/c",
            source="News",
            summary="Third story body.",
            score=7.5,
            score_status="scored",
        ),
    ]
    existing = crew._fallback_summaries([instant[0]])
    existing[0].score_status = "scored"

    out = crew._ensure_minimum_summaries(existing, instant, scored)

    assert len(out) == 3
    assert {s.source_url for s in out} == {
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    }


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


class _FakeMemory:
    def __init__(self, matches=None):
        self.matches = matches or []
        self.archived = []

    def search_similar(self, title, summary, *, top_k, exclude_url):
        del title, summary, top_k, exclude_url
        return self.matches

    def archive_summaries(self, summaries):
        self.archived.extend(summaries)


class _FakeTelegram:
    def __init__(self, sent):
        self.sent = sent
        self.calls = 0

    def send_items_digest(self, *args, **kwargs):
        del args, kwargs
        self.calls += 1
        return self.sent


def test_memory_context_near_match_is_retained_and_displayed():
    crew = TechPulseCrew.__new__(TechPulseCrew)
    crew.memory = _FakeMemory(matches=[
        MemorySearchResult(
            item_id="old",
            title="Earlier NVIDIA GPU supply story",
            summary="Earlier context",
            source_url="https://example.com/old",
            source_name="Example",
            distance=0.24,
        )
    ])
    summary = crew._fallback_summaries([
        Article(
            title="NVIDIA expands GPU supply",
            url="https://example.com/new",
            source="Example News",
            summary="NVIDIA expanded GPU supply for AI data centers.",
            score=8.0,
        )
    ])[0]

    retained = crew._apply_memory_context([summary])
    msg = format_items_digest(retained, total_fetched=3, total_after_filter=1)

    assert retained == [summary]
    assert "Earlier NVIDIA GPU supply story" in summary.history_context
    assert "相關歷史" in msg


def test_memory_context_distant_match_is_suppressed(monkeypatch):
    monkeypatch.setattr("pipeline.crew.MEMORY_CONTEXT_MAX_DISTANCE", 0.35)
    crew = TechPulseCrew.__new__(TechPulseCrew)
    crew.memory = _FakeMemory(matches=[
        MemorySearchResult(
            item_id="old",
            title="Loosely related story",
            summary="Some other context",
            source_url="https://example.com/old",
            source_name="Example",
            distance=0.44,
        )
    ])
    summary = crew._fallback_summaries([
        Article(
            title="Caterpillar stock rises on AI power demand",
            url="https://example.com/cat",
            source="Bloomberg",
            summary="Caterpillar shares rose as AI power demand boosted generator sales.",
            score=7.5,
        )
    ])[0]

    retained = crew._apply_memory_context([summary])
    msg = format_items_digest(retained, total_fetched=3, total_after_filter=1)

    assert retained == [summary]
    assert not getattr(summary, "history_context", "")
    assert "相關歷史" not in msg


def test_memory_semantic_duplicate_can_be_filtered(monkeypatch):
    monkeypatch.setattr("pipeline.crew.SEMANTIC_DUP_DROP_ENABLED", True)
    monkeypatch.setattr("pipeline.crew.SEMANTIC_DUP_DISTANCE_THRESHOLD", 0.12)
    crew = TechPulseCrew.__new__(TechPulseCrew)
    crew.memory = _FakeMemory(matches=[
        MemorySearchResult(
            item_id="old",
            title="Same story",
            summary="same",
            source_url="https://example.com/old",
            source_name="Example",
            distance=0.05,
        )
    ])
    summary = crew._fallback_summaries([
        Article(
            title="Same story rewritten",
            url="https://example.com/new",
            source="Example News",
            summary="Same story with a different URL.",
            score=8.0,
        )
    ])[0]

    assert crew._apply_memory_context([summary]) == []
    assert summary.semantic_duplicate is True
    assert summary.semantic_distance == 0.05


def test_items_digest_archives_memory_only_after_successful_delivery():
    summary_1 = TechPulseCrew.__new__(TechPulseCrew)._fallback_summaries([
        Article(
            title="Delivered",
            url="https://example.com/ok",
            source="Example",
            summary="Delivered summary",
            score=8.0,
            score_status="scored",
        )
    ])[0]
    crew = TechPulseCrew.__new__(TechPulseCrew)
    crew.telegram = _FakeTelegram(sent=True)
    crew.memory = _FakeMemory()

    assert crew._send_items_digest_with_memory([summary_1], total_fetched=1, total_after_filter=1) is True
    assert crew.memory.archived == [summary_1]

    summary_2 = TechPulseCrew.__new__(TechPulseCrew)._fallback_summaries([
        Article(
            title="Failed",
            url="https://example.com/fail",
            source="Example",
            summary="Failed summary",
            score=8.0,
            score_status="scored",
        )
    ])[0]
    crew.telegram = _FakeTelegram(sent=False)
    crew.memory = _FakeMemory()

    assert crew._send_items_digest_with_memory([summary_2], total_fetched=1, total_after_filter=1) is False
    assert crew.memory.archived == []


def test_items_digest_skips_unscored_fallback_only_delivery():
    summary = TechPulseCrew.__new__(TechPulseCrew)._fallback_summaries([
        Article(
            title="EBay Soars on Report GameStop Is Preparing Takeover Bid",
            url="https://example.com/ebay",
            source="bloomberg_rss",
            summary="EBay jumped after a reported GameStop bid.",
            score=0.0,
            score_status="fallback",
        )
    ])[0]
    crew = TechPulseCrew.__new__(TechPulseCrew)
    crew.telegram = _FakeTelegram(sent=True)
    crew.memory = _FakeMemory()

    assert crew._send_items_digest_with_memory([summary], total_fetched=316, total_after_filter=1) is False
    assert crew.telegram.calls == 0
    assert crew.memory.archived == []


def test_items_digest_allows_story_insight_without_scored_summary():
    summary = TechPulseCrew.__new__(TechPulseCrew)._fallback_summaries([
        Article(
            title="Thin fallback context",
            url="https://example.com/thin",
            source="example",
            summary="Thin fallback context.",
            score=0.0,
            score_status="fallback",
        )
    ])[0]
    crew = TechPulseCrew.__new__(TechPulseCrew)
    crew.telegram = _FakeTelegram(sent=True)
    crew.memory = _FakeMemory()

    assert crew._send_items_digest_with_memory(
        [summary],
        total_fetched=1,
        total_after_filter=1,
        story_insights=[object()],
    ) is True
    assert crew.telegram.calls == 1
    assert crew.memory.archived == [summary]
