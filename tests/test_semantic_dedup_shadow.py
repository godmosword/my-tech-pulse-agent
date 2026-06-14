"""Shadow-rollout observability for cross-run semantic dedup (A7).

Verifies _apply_memory_context tracks would-drop / checked / dropped counts
without changing the drop decision (gated by SEMANTIC_DUP_DROP_ENABLED).
"""

from agents.extractor_agent import ArticleSummary
from pipeline import crew as crew_module
from pipeline.crew import TechPulseCrew
from scoring.memory_store import MemorySearchResult


class _FakeMemory:
    def __init__(self, distance: float | None):
        self._distance = distance

    def search_similar(self, title, summary, *, top_k, exclude_url):  # noqa: ANN001
        if self._distance is None:
            return []
        return [
            MemorySearchResult(
                item_id="prior-1",
                title="prior headline",
                summary="prior",
                source_url="http://example.com/prior",
                source_name="src",
                distance=self._distance,
            )
        ]


def _crew(distance: float | None) -> TechPulseCrew:
    c = TechPulseCrew.__new__(TechPulseCrew)
    c.memory = _FakeMemory(distance)
    c._semantic_dup_checked = 0
    c._semantic_dup_would_drop = 0
    c._semantic_dup_dropped = 0
    return c


def _summary(i: int = 0) -> ArticleSummary:
    return ArticleSummary(
        entity=f"Co{i}",
        summary="s",
        title=f"t{i}",
        source_url=f"http://e/{i}",
        category="other",
        sentiment="neutral",
        confidence="high",
    )


def test_shadow_counts_when_drop_disabled(monkeypatch):
    monkeypatch.setattr(crew_module, "SEMANTIC_DUP_DROP_ENABLED", False)
    c = _crew(distance=0.05)  # near-duplicate (<= 0.12)
    out = c._apply_memory_context([_summary(0), _summary(1)])
    assert len(out) == 2  # nothing dropped when flag is off
    assert c._semantic_dup_checked == 2
    assert c._semantic_dup_would_drop == 2
    assert c._semantic_dup_dropped == 0
    assert all(s.semantic_duplicate for s in out)


def test_drops_when_enabled(monkeypatch):
    monkeypatch.setattr(crew_module, "SEMANTIC_DUP_DROP_ENABLED", True)
    c = _crew(distance=0.05)
    out = c._apply_memory_context([_summary(0), _summary(1)])
    assert out == []
    assert c._semantic_dup_would_drop == 2
    assert c._semantic_dup_dropped == 2


def test_far_match_is_not_a_candidate(monkeypatch):
    monkeypatch.setattr(crew_module, "SEMANTIC_DUP_DROP_ENABLED", True)
    c = _crew(distance=0.9)  # far (> 0.12)
    out = c._apply_memory_context([_summary(0)])
    assert len(out) == 1
    assert c._semantic_dup_checked == 1
    assert c._semantic_dup_would_drop == 0
    assert c._semantic_dup_dropped == 0


def test_metrics_reset_between_calls(monkeypatch):
    monkeypatch.setattr(crew_module, "SEMANTIC_DUP_DROP_ENABLED", False)
    c = _crew(distance=0.05)
    c._apply_memory_context([_summary(0)])
    assert c._semantic_dup_would_drop == 1
    c.memory = _FakeMemory(0.9)  # far on the next run
    c._apply_memory_context([_summary(1)])
    assert c._semantic_dup_would_drop == 0
    assert c._semantic_dup_checked == 1


def test_shadow_log_emitted_for_candidate(monkeypatch, caplog):
    monkeypatch.setattr(crew_module, "SEMANTIC_DUP_DROP_ENABLED", False)
    monkeypatch.setattr(crew_module, "SEMANTIC_DUP_SHADOW_LOG", True)
    c = _crew(distance=0.05)
    with caplog.at_level("INFO"):
        c._apply_memory_context([_summary(0)])
    assert any("Semantic dup candidate" in r.message for r in caplog.records)
