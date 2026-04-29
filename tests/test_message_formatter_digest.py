from datetime import datetime, timezone

from agents.extractor_agent import ArticleSummary
from delivery.message_formatter import format_items_digest


def _sample_summary(i: int) -> ArticleSummary:
    return ArticleSummary(
        entity=f"Entity {i}",
        summary=f"Summary {i}",
        category="product_launch",
        sentiment="neutral",
        confidence="high",
        score=10 - i,
        source_name="example",
        source_url="https://example.com",
    )


def test_digest_order_with_themes_preamble():
    summaries = [_sample_summary(i) for i in range(2)]
    msg = format_items_digest(
        summaries,
        total_fetched=12,
        total_after_filter=9,
        themes=["AI 資本支出", "晶片供應鏈重排"],
        market_takeaway="大型平台持續加碼算力，短線有利上游設備與雲端供應商。",
        now=datetime(2026, 4, 29, 8, 0, tzinfo=timezone.utc),
    )

    idx_theme = msg.index("*🧭 今日主線*")
    idx_bullet = msg.index("⭐")
    idx_stats = msg.index("_今日")

    assert idx_theme < idx_bullet < idx_stats
