"""Regex recovery when Gemini Flash returns truncated score JSON."""

from scoring.scorer import Scorer


def test_recover_three_dimensions_computes_score():
    s = Scorer()
    text = '{"relevance": 8, "novelty": 7, "depth": 6, "scor'  # truncated after score key
    # Still have rel, nov, dep
    r = s._recover_scores_from_partial_json(text, "default")  # noqa: SLF001
    assert r is not None
    assert r.relevance == 8 and r.novelty == 7 and r.depth == 6
    assert r.score > 0


def test_recover_only_score_field():
    s = Scorer()
    text = '{"relevance": , broken but "score": 7.5}'
    r = s._recover_scores_from_partial_json(text, "default")  # noqa: SLF001
    assert r is not None
    assert r.score == 7.5


def test_recover_returns_none_when_no_numbers():
    s = Scorer()
    assert s._recover_scores_from_partial_json("", "default") is None  # noqa: SLF001
    assert s._recover_scores_from_partial_json('{"foo": 1}', "default") is None  # noqa: SLF001
