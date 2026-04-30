from unittest.mock import patch

from scoring.state_store import FirestoreStateStore, SQLiteStateStore, make_state_store


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
