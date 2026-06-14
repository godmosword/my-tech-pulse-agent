"""Guard the firestore.indexes.json artifact deployed by scripts/deploy_firestore_indexes.sh.

Validates structure and the specific indexes the runtime relies on, without
snapshotting the whole file (so adding a legitimate new index does not break CI).
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INDEXES_PATH = ROOT / "firestore.indexes.json"


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(INDEXES_PATH.read_text(encoding="utf-8"))


def _index(doc: dict, collection_group: str) -> dict:
    matches = [i for i in doc["indexes"] if i["collectionGroup"] == collection_group]
    assert matches, f"no index for {collection_group}"
    return matches[0]


def test_is_valid_json_with_expected_top_level_keys(doc):
    assert isinstance(doc["indexes"], list) and doc["indexes"]
    assert isinstance(doc["fieldOverrides"], list)


def test_seen_items_composite_fields_and_order(doc):
    idx = _index(doc, "tech_pulse_seen_items")
    assert idx["queryScope"] == "COLLECTION"
    assert idx["fields"] == [
        {"fieldPath": "content_hash", "order": "ASCENDING"},
        {"fieldPath": "seen_at", "order": "ASCENDING"},
    ]


def test_earnings_composite_fields_and_order(doc):
    idx = _index(doc, "tech_pulse_earnings_reports")
    assert idx["fields"] == [
        {"fieldPath": "ticker", "order": "ASCENDING"},
        {"fieldPath": "published_at", "order": "DESCENDING"},
    ]


def test_memory_items_vector_index(doc):
    idx = _index(doc, "tech_pulse_memory_items")
    fields = idx["fields"]
    assert len(fields) == 1
    field = fields[0]
    assert field["fieldPath"] == "embedding"
    vec = field["vectorConfig"]
    assert vec["dimension"] == 768
    assert vec["flat"] == {}


def test_ttl_field_overrides(doc):
    ttl_by_group = {
        (o["collectionGroup"], o["fieldPath"]): o
        for o in doc["fieldOverrides"]
    }
    for group in ("tech_pulse_seen_items", "tech_pulse_memory_items"):
        override = ttl_by_group[(group, "expires_at")]
        assert override["ttl"] is True
        assert override["indexes"] == []
