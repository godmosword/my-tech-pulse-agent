from scoring.state_store import SQLiteStateStore, _cosine_similarity, make_state_store


def test_state_backend_defaults_to_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv("STATE_BACKEND", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("CLOUD_RUN_JOB", raising=False)
    monkeypatch.setenv("STATE_SQLITE_PATH", str(tmp_path / "dedup.sqlite"))

    store = make_state_store()

    assert isinstance(store, SQLiteStateStore)


def test_state_backend_firestore_falls_back_to_sqlite(monkeypatch, tmp_path):
    monkeypatch.setenv("STATE_BACKEND", "firestore")
    monkeypatch.setenv("STATE_SQLITE_PATH", str(tmp_path / "dedup.sqlite"))

    store = make_state_store()

    assert isinstance(store, SQLiteStateStore)


def test_sqlite_is_processed_and_store_is_atomic_claim(tmp_path):
    store = SQLiteStateStore(tmp_path / "dedup.sqlite")

    assert store.is_processed_and_store("article-1") is False
    assert store.is_processed_and_store("article-1") is True


def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.5, -0.3]
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6


def test_sqlite_semantic_duplicate_detected(tmp_path):
    store = SQLiteStateStore(tmp_path / "dedup.sqlite")
    ref = [1.0, 0.0, 0.0, 0.0]
    store.store_embedding("article-ref", "https://example.com/ref", ref)
    near = [0.99, 0.01, 0.0, 0.0]
    is_dup, sim = store.is_semantically_duplicate(near, threshold=0.85, window_days=7)
    assert is_dup is True
    assert sim >= 0.85


def test_sqlite_semantic_novel_article_passes(tmp_path):
    store = SQLiteStateStore(tmp_path / "dedup.sqlite")
    ref = [1.0, 0.0, 0.0, 0.0]
    store.store_embedding("article-ref", "https://example.com/ref", ref)
    orthogonal = [0.0, 1.0, 0.0, 0.0]
    is_dup, sim = store.is_semantically_duplicate(orthogonal, threshold=0.85, window_days=7)
    assert is_dup is False
    assert sim < 0.85


def test_list_recent_embeddings(tmp_path):
    store = SQLiteStateStore(tmp_path / "dedup.sqlite")
    store.store_embedding("a1", "https://example.com/a", [1.0, 0.0])
    rows = store.list_recent_embeddings(90)
    assert len(rows) == 1
    assert rows[0][0] == "a1"
    assert rows[0][2] == [1.0, 0.0]
