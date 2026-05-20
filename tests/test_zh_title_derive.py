"""zh_title derivation from Chinese summary/body."""

from agents.extractor_agent import ArticleSummary, ExtractorAgent
from llm.localization import derive_zh_title, has_cjk


def test_has_cjk_detects_chinese():
    assert has_cjk("Google 推出 Gemini Spark")
    assert not has_cjk("Google launches Gemini Spark")


def test_derive_zh_title_from_summary():
    zs = "Google 在 IO 2026 推出 Gemini Spark，整合 Gmail 成 24 小時代理助理。工程師可減少重複操作。"
    title = derive_zh_title(zs)
    assert title.startswith("Google 在 IO 2026")
    assert len(title) <= 40


def test_derive_zh_title_rejects_english_only():
    assert derive_zh_title("OpenAI expands model watermark checks.") == ""


def test_extractor_fills_zh_title_from_zh_summary():
    s = ArticleSummary(
        entity="Google",
        summary="Google launched Gemini Spark.",
        what_happened="Google launched Gemini Spark.",
        why_it_matters="More agentic assistants.",
        category="product_launch",
        key_facts=[],
        sentiment="neutral",
        confidence="high",
        zh_title=None,
        zh_summary="Google 在 IO 2026 推出 Gemini Spark，整合 Gmail 成全天候代理助理。投資人關注與 OpenAI 的競爭態勢。",
        zh_body=None,
    )
    ExtractorAgent._normalize_zh_fields(s)
    assert s.zh_title
    assert has_cjk(s.zh_title)
