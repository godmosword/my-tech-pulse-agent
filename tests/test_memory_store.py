from datetime import datetime, timezone

from scoring.memory_store import JsonMemoryService, make_memory_service, DisabledMemoryService
from scoring.state_store import SQLiteStateStore
from tests.test_json_stores import _summary, _FakeEmbedder


def test_make_memory_service_defaults_to_json(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMORY_ENABLED", "1")
    monkeypatch.setenv("MEMORY_BACKEND", "json")
    monkeypatch.setenv("DASHBOARD_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("STATE_SQLITE_PATH", str(tmp_path / "dedup.sqlite"))
    service = make_memory_service()
    assert isinstance(service, JsonMemoryService)


def test_make_memory_service_can_disable(monkeypatch):
    monkeypatch.setenv("MEMORY_ENABLED", "0")
    assert isinstance(make_memory_service(), DisabledMemoryService)


def test_json_memory_archive_summaries_writes_expected_payload(tmp_path):
    service = JsonMemoryService(
        embedder=_FakeEmbedder(),
        state=SQLiteStateStore(tmp_path / "dedup.sqlite"),
        data_dir=tmp_path / "data",
    )
    service.archive_summaries(
        [_summary()], delivered_at=datetime.now(timezone.utc)
    )
    from scoring.json_io import memory_items_path, read_json_list

    payload = read_json_list(memory_items_path(tmp_path / "data"))[0]
    assert payload["kind"] == "instant_summary"
    assert "embedding" not in payload
