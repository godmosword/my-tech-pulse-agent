"""End-to-end regression for the 2026-05-10 digest incident:

A single Lenny's Newsletter "Community Wisdom" roundup with score 5.6 shipped
alone, was misclassified as 「AI 基礎設施」, and produced a degenerate digest.
"""

from delivery.message_formatter import format_items_digest
from pipeline.crew import TechPulseCrew
from sources.rss_fetcher import Article


class _FakeMemory:
    def __init__(self):
        self.archived = []

    def archive_summaries(self, summaries):
        self.archived.extend(summaries)


class _FakeTelegram:
    def __init__(self, sent: bool):
        self.sent = sent
        self.calls = 0

    def send_items_digest(self, *args, **kwargs):
        self.calls += 1
        return self.sent


def _lennys_roundup_article() -> Article:
    return Article(
        title=(
            "Community Wisdom: What to do when non-PMs start shipping directly to "
            "production, thoughts on Claude Code's pricing A/B test, the use of gen ai in games"
        ),
        url="https://www.lennysnewsletter.com/p/community-wisdom-2026-05-10",
        source="lenny_newsletter",
        summary=(
            "Saturday subscriber-only roundup of Slack community discussions covering "
            "non-PM shipping, Claude Code pricing experiments, and gen ai topics."
        ),
        score=5.6,
        score_status="low_score_fallback",
        allowed_themes=["產品與策略", "其他焦點"],
    )


def test_lenny_community_wisdom_does_not_become_ai_infrastructure():
    article = _lennys_roundup_article()
    summaries = TechPulseCrew.__new__(TechPulseCrew)._fallback_summaries([article])

    # Theme guard: must NOT classify as AI 基礎設施 even though title mentions "gen ai".
    # Fallback-only items render under 「其他快訊」 with the low-signal banner.
    msg = format_items_digest(summaries, total_fetched=300, total_after_filter=1)
    assert "🧠 AI 基礎設施" not in msg
    assert "其他快訊" in msg
    assert "今日無" in msg and "高信心頭條" in msg


def test_lenny_with_scored_status_redirects_to_allowed_theme():
    """When a Lenny article is fully scored (not fallback), theme guard kicks in via _select_by_theme."""
    article = _lennys_roundup_article()
    article.score = 8.0
    article.score_status = "scored"
    summaries = TechPulseCrew.__new__(TechPulseCrew)._fallback_summaries([article])
    summaries[0].score_status = "scored"
    msg = format_items_digest(summaries, total_fetched=10, total_after_filter=1)
    assert "🧠 AI 基礎設施" not in msg
    # category="other" → cat_map default "其他焦點", which is already in allowed_themes
    assert ("🚀 產品與策略" in msg) or ("其他焦點" in msg)


def test_single_lenny_fallback_is_not_delivered():
    article = _lennys_roundup_article()
    summaries = TechPulseCrew.__new__(TechPulseCrew)._fallback_summaries([article])

    crew = TechPulseCrew.__new__(TechPulseCrew)
    crew.telegram = _FakeTelegram(sent=True)
    crew.memory = _FakeMemory()

    delivered = crew._send_items_digest_with_memory(
        summaries, total_fetched=300, total_after_filter=1
    )
    assert delivered is False
    assert crew.telegram.calls == 0
    assert crew.memory.archived == []


def test_allowed_themes_propagates_through_fallback_summaries():
    article = _lennys_roundup_article()
    summaries = TechPulseCrew.__new__(TechPulseCrew)._fallback_summaries([article])
    assert summaries[0].allowed_themes == ["產品與策略", "其他焦點"]
