"""zh_summary / zh_body handling: extractor softens; fallback stays honest."""

from agents.extractor_agent import ArticleSummary, ExtractorAgent
from pipeline.crew import TechPulseCrew
from sources.rss_fetcher import Article


def _summary_with_zh(zs: str, zb: str) -> ArticleSummary:
    return ArticleSummary(
        entity="NVIDIA",
        summary="NVIDIA expanded GPU supply.",
        what_happened="NVIDIA expanded GPU supply.",
        why_it_matters="More AI capacity for buyers.",
        category="product_launch",
        key_facts=[],
        sentiment="positive",
        confidence="medium",
        zh_summary=zs or None,
        zh_body=zb or None,
    )


def test_required_fields_no_longer_gates_on_zh_length():
    weak = _summary_with_zh("短", "短摘要")
    assert ExtractorAgent._has_required_fields(weak) is True


def test_enforce_zh_quality_nulls_short_zh_fields():
    s = _summary_with_zh("短", "短摘要")
    ExtractorAgent._enforce_zh_quality(s, "title")
    assert s.zh_summary is None
    assert s.zh_body is None


def test_enforce_zh_quality_preserves_long_zh_fields():
    zs = "NVIDIA 擴大 GPU 供應，AI 資料中心買家有望取得更多算力。"
    zb = "輝達在最新公告中宣布擴大 GPU 供應，重點針對 AI 資料中心。" * 2
    s = _summary_with_zh(zs, zb)
    ExtractorAgent._enforce_zh_quality(s, "title")
    assert s.zh_summary == zs
    assert s.zh_body == zb


def test_fallback_summary_omits_zh_body():
    """Mechanical character-conversion must not masquerade as a real zh translation."""
    crew = TechPulseCrew.__new__(TechPulseCrew)  # skip heavy __init__
    article = Article(
        title="NVIDIA expands GPU supply",
        url="https://example.com/n",
        source="Example",
        content="NVIDIA expanded GPU supply for AI data centers. Buyers may get more capacity.",
    )
    summaries = crew._fallback_summaries([article])

    assert len(summaries) == 1
    s = summaries[0]
    assert s.zh_body is None, "fallback zh_body must be empty so UI falls back to English"
    # zh_summary can stay (short, low-risk) but must not be a duplicate-concat artifact
    if s.zh_summary:
        assert "\n\n" not in s.zh_summary
