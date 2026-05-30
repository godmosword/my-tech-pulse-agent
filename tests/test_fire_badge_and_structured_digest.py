"""TLDR-style: 🔥 fire badge tiers + structured digest with inline buttons."""

from datetime import datetime, timezone

from agents.extractor_agent import ArticleSummary
from delivery.message_formatter import (
    _fire_badge,
    build_items_digest_messages,
)


def _summary(idx=0, *, score=7.0, tldr_tier="standard", url="https://example.com",
             hook="", title=None, category="product_launch") -> ArticleSummary:
    return ArticleSummary(
        entity=f"Entity{idx}",
        summary=f"Summary {idx}",
        what_happened=f"Fact {idx}.",
        why_it_matters=f"Implication {idx}.",
        category=category,
        key_facts=[],
        sentiment="neutral",
        confidence="high",
        cross_ref=False,
        source_url=url,
        source_name="example",
        title=title or f"Title {idx}",
        score=score,
        score_status="scored",
        tldr_tier=tldr_tier,
        hook=hook,
    )


def test_fire_badge_boundaries():
    assert _fire_badge(8.5) == "🔥🔥🔥"
    assert _fire_badge(8.49) == "🔥🔥"
    assert _fire_badge(6.5) == "🔥🔥"
    assert _fire_badge(6.49) == "🔥"
    assert _fire_badge(0.1) == "🔥"
    assert _fire_badge(0.0) == "⚪"
    assert _fire_badge(-1.0) == "⚪"


def test_structured_digest_separates_intro_cards_footer():
    msgs = build_items_digest_messages(
        [_summary(0, score=8.0), _summary(1, score=7.0)],
        total_fetched=2,
        total_after_filter=2,
        headline="今日焦點",
        now=datetime(2026, 5, 19, 1, 0, tzinfo=timezone.utc),
    )
    # First message is the intro with header + headline.
    assert "📡" in msgs[0].text
    assert "今日焦點" in msgs[0].text
    assert msgs[0].url is None
    # At least one card carries the source URL for the inline button.
    card_urls = [m.url for m in msgs if m.url]
    assert "https://example.com" in card_urls
    # Footer is last message with the count summary.
    assert "本期共" in msgs[-1].text


def test_headline_tier_promoted_to_headlines_section():
    msgs = build_items_digest_messages(
        [
            _summary(0, score=6.0, tldr_tier="headline", title="Headline pick"),
            _summary(1, score=9.0, tldr_tier="standard", title="High score standard"),
        ],
        total_fetched=2,
        total_after_filter=2,
    )
    # The headline-tagged item should land in the HEADLINES section even
    # though another item has a higher score.
    joined = "\n\n=====\n\n".join(m.text for m in msgs)
    headlines_idx = joined.index("HEADLINES")
    headline_pick_idx = joined.index("Headline pick")
    assert headlines_idx < headline_pick_idx


def test_tools_and_numbers_sections_only_render_when_present():
    msgs = build_items_digest_messages(
        [_summary(0, score=8.0, tldr_tier="standard")],
        total_fetched=1,
        total_after_filter=1,
    )
    joined = "\n".join(m.text for m in msgs)
    assert "TOOLS" not in joined
    assert "NUMBERS" not in joined

    msgs2 = build_items_digest_messages(
        [
            _summary(0, score=8.0, tldr_tier="tool_or_repo",
                     url="https://example.com/repo", title="OpenRepo"),
            _summary(1, score=7.5, tldr_tier="number",
                     url="https://example.com/num", title="Benchmark 76.4%"),
        ],
        total_fetched=2,
        total_after_filter=2,
    )
    joined2 = "\n\n".join(m.text for m in msgs2)
    # `&` is HTML-escaped inside the section header.
    assert "TOOLS &amp; REPOS" in joined2
    assert "NUMBERS TO KNOW" in joined2


def test_hook_falls_back_to_zh_summary_first_sentence():
    s = _summary(0, score=8.0, hook="")
    s.zh_summary = "輝達上修 H200 出貨。供應鏈價量齊揚。"
    msgs = build_items_digest_messages(
        [s], total_fetched=1, total_after_filter=1
    )
    joined = "\n".join(m.text for m in msgs)
    assert "輝達上修 H200 出貨" in joined


def test_no_inline_anchor_in_card_text():
    """URL must travel via DigestMessage.url for the inline button — never inline."""
    msgs = build_items_digest_messages(
        [_summary(0, score=8.0, url="https://example.com/x")],
        total_fetched=1,
        total_after_filter=1,
    )
    for m in msgs:
        assert "原文連結</a>" not in m.text
