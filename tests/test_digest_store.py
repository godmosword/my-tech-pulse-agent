from datetime import datetime, timezone

from agents.extractor_agent import ArticleSummary
from scoring.digest_store import FirestoreDigestStore


class _FakeDoc:
    def __init__(self, doc_id: str, data: dict):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return dict(self._data)


class _FakeSnapshot:
    def __init__(self, docs):
        self._docs = docs
        self.empty = not docs

    def stream(self):
        return iter(self._docs)


class _FakeCollection:
    def __init__(self):
        self.writes: dict[str, dict] = {}
        self._latest: _FakeSnapshot = _FakeSnapshot([])

    def document(self, doc_id: str):
        collection = self

        class Ref:
            def set(self, payload, merge=False):
                collection.writes[doc_id] = payload

        return Ref()

    def order_by(self, field, direction=None):
        return self

    def limit(self, n: int):
        return self

    def stream(self):
        return self._latest.stream()


class _FakeClient:
    def __init__(self):
        self._collections: dict[str, _FakeCollection] = {}

    def collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = _FakeCollection()
        return self._collections[name]


def test_digest_store_save_run_writes_theme_groups():
    client = _FakeClient()
    store = FirestoreDigestStore(client=client, collection_prefix="tech_pulse")
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
    payload = client.collection("tech_pulse_digests").writes[digest_id]
    assert payload["theme_groups"]
    assert payload["funnel"]["semantic_prefilter_dropped"] == 1
