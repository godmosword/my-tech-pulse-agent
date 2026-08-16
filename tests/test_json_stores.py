from datetime import datetime, timedelta, timezone

from agents.earnings_models import EarningsReport
from agents.extractor_agent import ArticleSummary
from scoring.digest_store import JsonDigestStore
from scoring.earnings_report_store import JsonEarningsReportStore
from scoring.json_io import (
    earnings_index_path,
    earnings_report_path,
    memory_items_path,
    prune_by_timestamp,
    read_json_list,
    read_json_object,
)
from scoring.memory_store import JsonMemoryService
from scoring.state_store import SQLiteStateStore


class _FakeEmbedder:
    def __init__(self, vector=None):
        self.vector = vector or [0.1] * 8
        self.document_calls = []
        self.query_calls = []

    def embed_document(self, *, title, text):
        self.document_calls.append((title, text))
        return self.vector

    def embed_query(self, text):
        self.query_calls.append(text)
        return self.vector


def _summary(**overrides):
    data = dict(
        entity="NVIDIA",
        title="NVIDIA expands GPU supply",
        summary="NVIDIA expanded GPU supply for AI data centers.",
        what_happened="NVIDIA expanded GPU supply.",
        why_it_matters="AI data center buyers may get more capacity.",
        category="product_launch",
        key_facts=[],
        sentiment="positive",
        confidence="medium",
        source_url="https://example.com/nvidia?utm_source=x",
        source_name="Example",
        score=8.1,
        score_status="ok",
        published_at="2026-05-01T00:00:00+00:00",
    )
    data.update(overrides)
    return ArticleSummary(**data)


def _service(tmp_path, embedder=None):
    return JsonMemoryService(
        embedder=embedder or _FakeEmbedder(),
        state=SQLiteStateStore(tmp_path / "dedup.sqlite"),
        data_dir=tmp_path / "data",
        retention_days=90,
    )


def test_json_memory_archive_writes_payload_without_embedding(tmp_path):
    service = _service(tmp_path)
    delivered_at = datetime.now(timezone.utc) - timedelta(days=1)

    service.archive_summaries([_summary()], delivered_at=delivered_at)

    rows = read_json_list(memory_items_path(tmp_path / "data"))
    assert len(rows) == 1
    payload = rows[0]
    assert payload["kind"] == "instant_summary"
    assert payload["title"] == "NVIDIA expands GPU supply"
    assert payload["source_url"] == "https://example.com/nvidia?utm_source=x"
    assert "embedding" not in payload
    assert payload["published_at"].startswith("2026-05-01")
    assert payload["zh_summary"] == ""
    assert payload["tickers"] == []
    assert payload["what_happened"] == "NVIDIA expanded GPU supply."
    assert payload["search_tokens"]


def test_json_memory_normalizes_tickers_and_keeps_zh_summary(tmp_path):
    service = _service(tmp_path)
    summary = _summary()
    summary.tickers = ["nvda", " AAPL ", "nvda", "", "TSM", "META", "AMZN", "GOOG"]
    summary.zh_summary = "NVIDIA 擴大 GPU 供應，AI 資料中心買家有望取得更多算力。"
    service.archive_summaries(
        [summary], delivered_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    payload = read_json_list(memory_items_path(tmp_path / "data"))[0]
    assert payload["tickers"] == ["NVDA", "AAPL", "TSM", "META", "AMZN"]
    assert payload["zh_summary"] == "NVIDIA 擴大 GPU 供應，AI 資料中心買家有望取得更多算力。"


def test_json_memory_upsert_and_prune(tmp_path):
    service = _service(tmp_path)
    old = _summary(source_url="https://example.com/old")
    new = _summary(source_url="https://example.com/new")
    service.archive_summaries(
        [old], delivered_at=datetime.now(timezone.utc) - timedelta(days=120)
    )
    service.archive_summaries([new], delivered_at=datetime.now(timezone.utc))
    rows = read_json_list(memory_items_path(tmp_path / "data"))
    urls = {row["source_url"] for row in rows}
    assert "https://example.com/new" in urls
    assert "https://example.com/old" not in urls


def test_prune_keeps_old_earnings_kind():
    old = datetime.now(timezone.utc) - timedelta(days=200)
    rows = [
        {
            "kind": "earnings",
            "item_id": "e1",
            "delivered_at": old.isoformat().replace("+00:00", "Z"),
        },
        {
            "kind": "instant_summary",
            "item_id": "n1",
            "delivered_at": old.isoformat().replace("+00:00", "Z"),
        },
    ]
    kept = prune_by_timestamp(rows, retention_days=90)
    ids = {row["item_id"] for row in kept}
    assert ids == {"e1"}


def test_json_memory_writes_translation_aligned(tmp_path):
    service = _service(tmp_path)
    summary = _summary()
    summary.translation_aligned = True
    service.archive_summaries(
        [summary], delivered_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    payload = read_json_list(memory_items_path(tmp_path / "data"))[0]
    assert payload["translation_aligned"] is True


def test_json_memory_search_uses_sqlite_cosine(tmp_path):
    embedder = _FakeEmbedder([1.0, 0.0, 0.0, 0.0])
    service = _service(tmp_path, embedder)
    service.archive_summaries(
        [_summary()], delivered_at=datetime.now(timezone.utc) - timedelta(days=1)
    )
    results = service.search_similar("NVIDIA", "GPU supply", top_k=1)
    assert len(results) == 1
    assert results[0].title == "NVIDIA expands GPU supply"
    assert results[0].distance is not None
    assert results[0].distance < 0.01
    assert service.is_semantic_duplicate("NVIDIA", "GPU supply", threshold=0.12)


def test_json_digest_store_save_run(tmp_path):
    store = JsonDigestStore(data_dir=tmp_path / "data")
    summary = _summary(source_url="https://example.com/gemini", title="Gemini Spark")
    digest_id = store.save_run(
        digest=None,
        summaries=[summary],
        deep_briefs=[],
        delivered_at=datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc),
        funnel={"semantic_prefilter_dropped": 1},
    )
    assert digest_id == "20260520T120000Z"
    latest = store.get_latest()
    assert latest is not None
    assert latest["theme_groups"]
    assert latest["funnel"]["semantic_prefilter_dropped"] == 1
    assert "embedding" not in latest


def test_json_earnings_store_splits_index_and_detail(tmp_path):
    store = JsonEarningsReportStore(data_dir=tmp_path / "data")
    report = EarningsReport(
        report_id="NVDA_2026_FY2026Q1",
        ticker="NVDA",
        company="NVIDIA Corporation",
        cik="0001045810",
        fiscal_period="FY2026Q1",
        quarter_label="FY2026 Q1",
        published_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
        rendered_markdown_zh="# 長文不該進 index",
    )
    assert store.save(report) == "NVDA_2026_FY2026Q1"
    detail = read_json_object(earnings_report_path("NVDA_2026_FY2026Q1", tmp_path / "data"))
    assert detail is not None
    assert detail["rendered_markdown_zh"] == "# 長文不該進 index"
    index = read_json_list(earnings_index_path(tmp_path / "data"))
    assert len(index) == 1
    assert "rendered_markdown_zh" not in index[0]
    loaded = store.get("NVDA_2026_FY2026Q1")
    assert loaded is not None
    assert loaded["ticker"] == "NVDA"
