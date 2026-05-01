from unittest.mock import patch

from scoring.state_store import FirestoreStateStore, SQLiteStateStore, _cosine_similarity, make_state_store


class _FailingFirestoreQuery:
    def where(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def stream(self, transaction=None):
        del transaction
        raise RuntimeError("400 The query requires an index. You can create it here: https://example.test")


def test_state_backend_auto_uses_sqlite_locally(monkeypatch):
    monkeypatch.delenv("STATE_BACKEND", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("CLOUD_RUN_JOB", raising=False)

    store = make_state_store()

    assert isinstance(store, SQLiteStateStore)


def test_state_backend_auto_uses_firestore_on_cloud_run(monkeypatch):
    monkeypatch.delenv("STATE_BACKEND", raising=False)
    monkeypatch.setenv("CLOUD_RUN_JOB", "tech-pulse-job")

    with patch("scoring.state_store.FirestoreStateStore", autospec=True) as firestore_cls:
        store = make_state_store()

    firestore_cls.assert_called_once()
    assert store == firestore_cls.return_value


def test_state_backend_firestore_falls_back_to_sqlite(monkeypatch):
    monkeypatch.setenv("STATE_BACKEND", "firestore")

    with patch.object(FirestoreStateStore, "__init__", side_effect=RuntimeError("no creds")):
        store = make_state_store()

    assert isinstance(store, SQLiteStateStore)


def test_sqlite_is_processed_and_store_is_atomic_claim(tmp_path):
    store = SQLiteStateStore(tmp_path / "dedup.sqlite")

    assert store.is_processed_and_store("article-1") is False
    assert store.is_processed_and_store("article-1") is True


def test_firestore_content_hash_dedup_skips_missing_index(caplog):
    store = FirestoreStateStore.__new__(FirestoreStateStore)
    store._prefix = "tech_pulse"
    store._failed_precondition_error = RuntimeError
    store._collection = lambda name: _FailingFirestoreQuery()

    assert store._content_hash_seen("content-hash", cutoff=object()) is False
    assert "required composite index is missing" in caplog.text


def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.5, -0.3]
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6


def test_sqlite_semantic_duplicate_detected(tmp_path):
    store = SQLiteStateStore(tmp_path / "dedup.sqlite")
    # Store a reference embedding
    ref = [1.0, 0.0, 0.0, 0.0]
    store.store_embedding("article-ref", "https://example.com/ref", ref)
    # A near-identical vector — same direction
    near = [0.99, 0.01, 0.0, 0.0]
    is_dup, sim = store.is_semantically_duplicate(near, threshold=0.85, window_days=7)
    assert is_dup is True
    assert sim >= 0.85


def test_sqlite_semantic_novel_article_passes(tmp_path):
    store = SQLiteStateStore(tmp_path / "dedup.sqlite")
    ref = [1.0, 0.0, 0.0, 0.0]
    store.store_embedding("article-ref", "https://example.com/ref", ref)
    # Orthogonal vector — completely different topic
    orthogonal = [0.0, 1.0, 0.0, 0.0]
    is_dup, sim = store.is_semantically_duplicate(orthogonal, threshold=0.85, window_days=7)
    assert is_dup is False
    assert sim < 0.85
