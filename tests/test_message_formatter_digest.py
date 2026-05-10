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

    # Quality footer: shows total count and average score.
    assert re.search(r"📊 本期共 \d+ 則  ·  平均分數 \d+\.\d+", msg)
    assert "今日 12 篇" not in msg
    assert "過濾後 9 篇" not in msg

    # Theme bullets still appear before any item line.
    idx_themes = msg.index("🧭 今日主線")
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
    # Locate the title line (contains 📊 score prefix followed by confidence badge).
    score_line = next(line for line in msg.splitlines() if line.startswith("📊"))
    # Score line must NOT contain title or body content — those are on separate lines now.
    assert "Meta Platforms" not in score_line
    assert "shares fell" not in score_line
    # The score line should start with 📊 and the score.
    assert score_line.startswith("📊 7")
    # Title must appear on its own bold line.
    assert "<b>Meta raises spend outlook</b>" in msg


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
    idx_themes = msg.index("🧭 今日主線")
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


def test_low_score_fallback_is_labeled_as_low_confidence_brief():
    low_score = _sample_summary(
        0,
        category="other",
        title="ByteDance AI infrastructure spending",
        summary="ByteDance targets higher AI infrastructure spending.",
        score=5.8,
    )
    low_score.score_status = "low_score_fallback"

    msg = format_items_digest([low_score], total_fetched=332, total_after_filter=1)

    assert "其他快訊" in msg
    assert "ByteDance AI infrastructure spending" in msg
    assert "低信心" in msg
    assert "低信心快訊 1 則" in msg


def test_item_contains_score_and_confidence_badge():
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
    assert "✅ 高信心" in msg
    assert "🕒 2026-05-01 06:49" in msg


def test_digest_footer_shows_total_and_average():
    """Regression: footer should show total shown and average over scored items only."""
    scored = _sample_summary(
        0,
        category="funding",
        entity="QuantWare",
        title="Intel VC Backs QuantWare",
        summary="Dutch startup raises funding.",
        score=8.2,
    )
    scored.score_status = "scored"
    fallback = _sample_summary(
        1,
        category="other",
        title="Super Micro Jumps",
        summary="Margins improved.",
        score=0.0,
    )
    fallback.score_status = "fallback"

    msg = format_items_digest(
        [scored, fallback],
        total_fetched=2,
        total_after_filter=2,
        now=datetime(2026, 5, 5, 23, 22, tzinfo=timezone.utc),
    )

    assert "精選" not in msg
    assert "📊 本期共 2 則" in msg
    assert "平均分數 8.2" in msg


def test_digest_header_shows_display_timezone_default_taipei(monkeypatch):
    monkeypatch.delenv("DIGEST_HEADER_TIMEZONE", raising=False)
    summary = _sample_summary(0, title="Only Story", score=8.0)
    msg = format_items_digest(
        [summary],
        total_fetched=1,
        total_after_filter=1,
        now=datetime(2026, 5, 9, 10, 53, tzinfo=timezone.utc),
    )
    assert "2026/05/09 18:53" in msg


def test_digest_header_respects_digest_header_timezone_utc(monkeypatch):
    monkeypatch.setenv("DIGEST_HEADER_TIMEZONE", "UTC")
    summary = _sample_summary(0, title="Only Story", score=8.0)
    msg = format_items_digest(
        [summary],
        total_fetched=1,
        total_after_filter=1,
        now=datetime(2026, 5, 9, 10, 53, tzinfo=timezone.utc),
    )
    assert "2026/05/09 10:53" in msg


def test_digest_format_unknown_env_falls_back_to_v1(monkeypatch):
    monkeypatch.setenv("DIGEST_FORMAT", "typo-layout")
    summary = _sample_summary(0, title="Only Story", score=8.0)
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert "Digest v2" not in msg
    assert "科技脈搏 ·" in msg


def test_digest_format_v2_opt_in(monkeypatch):
    monkeypatch.setenv("DIGEST_FORMAT", "v2")
    summary = _sample_summary(0, title="Only Story", score=8.0)
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert "Digest v2" in msg


def test_zh_summary_shown_in_card_when_present():
    summary = _sample_summary(
        0,
        category="product_launch",
        title="NVIDIA H200 Breakthrough",
        what_happened="NVIDIA shipped H200 GPUs to hyperscalers.",
        score=9.0,
    )
    summary.zh_summary = "NVIDIA H200 GPU 達成推理速度十倍提升，打破記憶體頻寬瓶頸。此突破將加速 AI 基礎設施部署，對上游設備供應商有利。"
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert "💡" in msg
    assert "NVIDIA H200 GPU" in msg


def test_zh_summary_omitted_when_none():
    summary = _sample_summary(
        0,
        category="product_launch",
        title="Some Article",
        score=8.0,
    )
    assert summary.zh_summary is None
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert "💡" not in msg


def test_source_link_is_html_anchor():
    summary = _sample_summary(0, score=8.0)
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert '<a href="https://example.com">原文連結</a>' in msg


def test_title_is_bold_html():
    summary = _sample_summary(0, title="My Test Title", score=8.0)
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert "<b>My Test Title</b>" in msg


def test_ai_keyword_does_not_match_gen_ai_casual():
    """Regression: 2026-05-10 digest classified Lenny's 'gen ai in games' note as AI 基礎設施."""
    summary = _sample_summary(
        0,
        category="other",
        title="Community Wisdom: thoughts on gen ai in games",
        summary="Slack community discussion about generative AI use in games and PM workflows.",
        score=7.5,
    )
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert "AI 基礎設施" not in msg


def test_ai_infrastructure_compound_keywords_match():
    """NVIDIA + datacenter must still classify as AI 基礎設施."""
    summary = _sample_summary(
        0,
        category="product_launch",
        title="NVIDIA H200 datacenter rollout begins",
        summary="NVIDIA shipped H200 GPUs to hyperscaler datacenters this week.",
        score=8.2,
    )
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert "AI 基礎設施" in msg


def test_allowed_themes_redirects_offtopic_kol():
    """KOL allowed_themes whitelist should override keyword match."""
    summary = _sample_summary(
        0,
        category="other",
        title="Notes on gpu shortages and PM hiring",
        summary="Quick PM-focused take on the gpu shortage and how teams should hire.",
        score=7.0,
    )
    summary.allowed_themes = ["產品與策略", "其他焦點"]
    msg = format_items_digest([summary], total_fetched=1, total_after_filter=1)
    assert "AI 基礎設施" not in msg
    assert "產品與策略" in msg


def test_fallback_only_digest_shows_warning_banner():
    """When no scored items pass, surface a banner so users know it's a low-signal day."""
    fallback = _sample_summary(
        0,
        category="other",
        title="Anthropic experiment",
        summary="An advisory note.",
        score=5.6,
    )
    fallback.score_status = "low_score_fallback"
    other = _sample_summary(
        1,
        category="other",
        title="Second low-confidence note",
        summary="Another advisory note.",
        score=5.7,
    )
    other.score_status = "low_score_fallback"

    msg = format_items_digest([fallback, other], total_fetched=300, total_after_filter=2)
    assert "今日無" in msg and "高信心頭條" in msg
