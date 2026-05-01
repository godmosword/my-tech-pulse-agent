from datetime import datetime, timezone

from agents.extractor_agent import ArticleSummary
from scoring.memory_store import FirestoreMemoryService


class _FakeEmbedder:
    def __init__(self, vector=None):
        self.vector = vector or [0.1] * 768
        self.document_calls = []
        self.query_calls = []

    def embed_document(self, *, title, text):
        self.document_calls.append((title, text))
        return self.vector

    def embed_query(self, text):
        self.query_calls.append(text)
        return self.vector


class _FakeDocRef:
    def __init__(self, store, doc_id):
        self.store = store
        self.doc_id = doc_id

    def set(self, payload, merge=False):
        self.store[self.doc_id] = {"payload": payload, "merge": merge}


class _FakeDoc:
    id = "doc-1"

    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return dict(self._data)

    def get(self, field):
        return self._data.get(field)


class _FakeVectorQuery:
    def __init__(self, docs=None, exc=None):
        self.docs = docs or []
        self.exc = exc

    def stream(self):
        if self.exc:
            raise self.exc
        return iter(self.docs)


class _FakeCollection:
    def __init__(self, docs=None, exc=None):
        self.writes = {}
        self.docs = docs or []
        self.exc = exc
        self.find_nearest_kwargs = None

    def document(self, doc_id):
        return _FakeDocRef(self.writes, doc_id)

    def find_nearest(self, **kwargs):
        self.find_nearest_kwargs = kwargs
        return _FakeVectorQuery(self.docs, self.exc)


class _FakeClient:
    def __init__(self, collection):
        self.collection_ref = collection
        self.collection_name = None

    def collection(self, name):
        self.collection_name = name
        return self.collection_ref


def _memory_service(collection, embedder=None):
    return FirestoreMemoryService(
        embedder=embedder or _FakeEmbedder(),
        client=_FakeClient(collection),
        collection_prefix="tech_pulse",
        vector_cls=list,
        distance_measure="COSINE",
        failed_precondition_error=RuntimeError,
    )


def _summary():
    return ArticleSummary(
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


def test_memory_archive_summaries_writes_expected_payload():
    collection = _FakeCollection()
    service = _memory_service(collection)
    delivered_at = datetime(2026, 5, 1, tzinfo=timezone.utc)

    service.archive_summaries([_summary()], delivered_at=delivered_at)

    assert len(collection.writes) == 1
    write = next(iter(collection.writes.values()))
    payload = write["payload"]
    assert write["merge"] is True
    assert payload["kind"] == "instant_summary"
    assert payload["title"] == "NVIDIA expands GPU supply"
    assert payload["source_url"] == "https://example.com/nvidia?utm_source=x"
    assert len(payload["embedding"]) == 768
    assert payload["published_at"] == datetime(2026, 5, 1, tzinfo=timezone.utc)
    assert payload["expires_at"] > delivered_at


def test_memory_search_similar_uses_firestore_find_nearest():
    collection = _FakeCollection(docs=[
        _FakeDoc({
            "item_id": "abc",
            "title": "Earlier NVIDIA supply story",
            "summary": "Earlier context",
            "source_url": "https://example.com/old",
            "source_name": "Example",
            "vector_distance": 0.24,
        })
    ])
    service = _memory_service(collection)

    results = service.search_similar("NVIDIA", "GPU supply", top_k=2)

    assert len(results) == 1
    assert results[0].title == "Earlier NVIDIA supply story"
    assert results[0].distance == 0.24
    assert collection.find_nearest_kwargs["vector_field"] == "embedding"
    assert collection.find_nearest_kwargs["limit"] == 2
    assert collection.find_nearest_kwargs["distance_result_field"] == "vector_distance"


def test_memory_search_missing_vector_index_fails_open(caplog):
    collection = _FakeCollection(exc=RuntimeError("400 query requires an index"))
    service = _memory_service(collection)

    assert service.search_similar("NVIDIA", "GPU supply") == []
    assert "required vector index" in caplog.text
