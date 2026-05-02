import re
from datetime import datetime, timezone

from agents.extractor_agent import ArticleSummary
from delivery.message_formatter import format_items_digest


def _sample_summary(
    i: int,
    *,
    category: str = "product_launch",
    entity: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    what_happened: str = "",
    why_it_matters: str = "",
    score: float | None = None,
) -> ArticleSummary:
    return ArticleSummary(
        entity=entity or f"Entity {i}",
        title=title or f"Title {i}",
        summary=summary or f"Summary {i}",
        what_happened=what_happened,
        why_it_matters=why_it_matters,
        category=category,
        sentiment="neutral",
        confidence="high",
        score=score if score is not None else 10 - i,
        source_name="example",
        source_url="https://example.com",
    )


def test_digest_groups_by_theme_and_uses_quality_footer():
    summaries = [
        _sample_summary(0, category="product_launch", title="Stripe AI Payments",
                        summary="Stripe ships AI payments tooling.", score=8.4),
        _sample_summary(1, category="product_launch", title="OpenAI New Model",
                        summary="OpenAI releases a frontier AI model.", score=8.1),
        _sample_summary(2, category="earnings", entity="Meta",
                        title="Meta raises spend outlook",
                        summary="Meta raised capex guidance.", score=7.8),
        _sample_summary(3, category="earnings", entity="Alphabet",
                        title="Alphabet beats consensus",
                        summary="Alphabet posts beat on cloud.", score=7.5),
        _sample_summary(4, category="regulation", title="EU rules tightened",
                        summary="EU tightens AI compliance rules.", score=7.4),
        _sample_summary(5, category="regulation", title="US House probe",
                        summary="US House opens probe on AI vendors.", score=7.3),
    ]
    msg = format_items_digest(
        summaries,
        total_fetched=12,
        total_after_filter=9,
        themes=["AI 資本支出", "晶片供應鏈重排"],
        market_takeaway="大型平台持續加碼算力，短線有利上游設備與雲端供應商。",
        now=datetime(2026, 4, 29, 8, 0, tzinfo=timezone.utc),
    )

    # Theme heading (one of the curated Chinese labels) appears.
    assert any(label in msg for label in ("財報焦點", "AI 基礎設施", "政策與監管", "產品與策略"))

    # New quality footer present, old throughput footer absent.
    assert re.search(r"_精選 \d+ 則 · 平均評分 \d+\\\.\d+ · 涵蓋 \d+ 個主題_", msg)
    assert "今日 12 篇" not in msg
    assert "過濾後 9 篇" not in msg

    # Theme bullets still appear before any item line.
    idx_themes = msg.index("*🧭 今日主線*")
    idx_first_item = msg.index("⭐")
    assert idx_themes < idx_first_item


def test_earnings_line_has_no_midcut_summary():
    summary = _sample_summary(
        0,
        category="earnings",
        entity="Meta Platforms Inc.",
        title="Meta raises spend outlook",
        summary=(
            "Meta Platforms Inc. shares fell after CEO Mark Zuckerberg "
            "raised the company's spending outlook for the year."
        ),
        score=7.6,
    )
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    # Locate the title line (starts with 📊) — this is where the mid-cut bug used to live.
    title_line = next(line for line in msg.splitlines() if line.startswith("📊"))
    # The old format produced "📊 *Meta Platforms Inc. — Meta Platforms Inc. shares fell after CEO Mark Zuckerberg ra*"
    # — the title line must no longer contain any of the body summary content.
    assert "Mark Zuckerberg" not in title_line
    assert "shares fell" not in title_line
    assert "Meta raises spend outlook" in title_line
    # The earnings line should now show the score next to the 📊 prefix.
    assert title_line.startswith("📊 7")


def test_structured_summary_used_in_body():
    summary = _sample_summary(
        0,
        category="product_launch",
        title="OpenAI New Model",
        summary="LEGACY-FALLBACK-TEXT-SHOULD-NOT-APPEAR",
        what_happened="OpenAI released frontier model GPT-X with 5x throughput.",
        why_it_matters="Pressures rivals to match cost-per-token economics.",
        score=8.5,
    )
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert "OpenAI released frontier model" in msg
    assert "Pressures rivals to match" in msg
    assert "LEGACY-FALLBACK-TEXT-SHOULD-NOT-APPEAR" not in msg


def test_headline_and_narrative_lead_appear_above_items():
    summary = _sample_summary(0, category="product_launch", score=8.3,
                              what_happened="A landmark launch occurred today.")
    msg = format_items_digest(
        [summary],
        total_fetched=1,
        total_after_filter=1,
        headline="AI 資本支出全面上修",
        narrative_excerpt="Meta、Microsoft、Alphabet 同日上調算力資本支出指引。",
        themes=["AI 資本支出"],
        now=datetime(2026, 4, 29, 8, 0, tzinfo=timezone.utc),
    )

    idx_headline = msg.index("AI 資本支出全面上修")
    idx_narrative = msg.index("Meta")
    idx_themes = msg.index("*🧭 今日主線*")
    idx_first_item = msg.index("⭐")
    assert idx_headline < idx_narrative < idx_themes < idx_first_item


def test_theme_keyword_ai_does_not_match_inside_participants():
    summary = _sample_summary(
        0,
        category="other",
        title="Thinking Through CC0 and IP for NFT Communities",
        summary="This week's participants discuss NFT intellectual property frameworks.",
        score=7.7,
    )
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)

    assert "AI 基礎設施" not in msg
    assert "其他焦點" in msg


def test_theme_keyword_ai_matches_standalone_ai_phrase():
    summary = _sample_summary(
        0,
        category="other",
        title="AI infrastructure demand grows",
        summary="GPU and data center capacity remain constrained.",
        score=7.7,
    )
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)

    assert "AI 基礎設施" in msg


def test_fallback_items_are_not_duplicated_or_averaged():
    fallback = _sample_summary(
        0,
        category="other",
        title="Fallback item",
        summary="Fallback summary.",
        score=0.0,
    )
    fallback.score_status = "fallback"

    msg = format_items_digest([fallback], total_fetched=1, total_after_filter=1)

    assert msg.count("Fallback item") == 1
    assert "未評分" in msg
    assert "平均評分" not in msg
    # Footer now shows "快訊 N 則" instead of "全部待確認" for cleaner UX
    assert "快訊" in msg


def test_item_contains_verification_and_published_time_lines():
    summary = _sample_summary(
        0,
        category="product_launch",
        title="OpenAI New Model",
        what_happened="OpenAI released a new model.",
        why_it_matters="Model supply may tighten GPU demand.",
        score=8.9,
    )
    summary.confidence = "high"
    summary.published_at = "2026-05-01T06:49:00+00:00"

    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert "✅ 已驗證：高信心" in msg
    assert "🕒 發布時間：2026\\-05\\-01 06:49:00 UTC" in msg
