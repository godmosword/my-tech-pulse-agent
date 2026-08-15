from datetime import datetime, timezone

from agents.extractor_agent import ArticleSummary
from scoring.digest_store import JsonDigestStore


def test_digest_store_save_run_writes_theme_groups(tmp_path):
    store = JsonDigestStore(data_dir=tmp_path / "data")
    summary = ArticleSummary(
        entity="Google",
        title="Gemini Spark",
        summary="Google launched Gemini Spark.",
        what_happened="Google launched Gemini Spark.",
        why_it_matters="More AI assistants.",
        category="product_launch",
        key_facts=[],
        sentiment="neutral",
        confidence="high",
        source_url="https://example.com/gemini",
        source_name="Example",
        zh_summary="Google 推出 Gemini Spark。",
    )
    digest_id = store.save_run(
        digest=None,
        summaries=[summary],
        deep_briefs=[],
        delivered_at=datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
        funnel={"semantic_prefilter_dropped": 1},
    )
    assert digest_id == "20260520T120000Z"
    payload = store.get_latest()
    assert payload is not None
    assert payload["theme_groups"]
    assert payload["funnel"]["semantic_prefilter_dropped"] == 1
