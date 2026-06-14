"""Per-type, env-overridable scoring thresholds (A5)."""

import pytest

from scoring.scorer import Scorer, _env_float


@pytest.fixture
def scorer() -> Scorer:
    # Bypass Gemini client init; only config-driven threshold() is exercised.
    s = Scorer.__new__(Scorer)
    s._config = {
        "thresholds": {
            "default": 6.8,
            "earnings": 7.5,
            "social_signal": 4.0,
            "kol": 5.5,
        }
    }
    return s


def test_env_float_treats_unset_empty_invalid_as_absent(monkeypatch):
    monkeypatch.delenv("SCORE_THRESHOLD", raising=False)
    assert _env_float("SCORE_THRESHOLD") is None
    monkeypatch.setenv("SCORE_THRESHOLD", "")
    assert _env_float("SCORE_THRESHOLD") is None
    monkeypatch.setenv("SCORE_THRESHOLD", "   ")
    assert _env_float("SCORE_THRESHOLD") is None
    monkeypatch.setenv("SCORE_THRESHOLD", "abc")
    assert _env_float("SCORE_THRESHOLD") is None
    monkeypatch.setenv("SCORE_THRESHOLD", "6.8")
    assert _env_float("SCORE_THRESHOLD") == 6.8


def test_threshold_uses_config_default_when_env_unset(scorer, monkeypatch):
    monkeypatch.delenv("SCORE_THRESHOLD", raising=False)
    monkeypatch.delenv("SCORE_THRESHOLD_KOL", raising=False)
    assert scorer.threshold() == 6.8
    assert scorer.threshold("default") == 6.8
    assert scorer.threshold("kol") == 5.5


def test_default_threshold_env_override(scorer, monkeypatch):
    monkeypatch.setenv("SCORE_THRESHOLD", "8.0")
    assert scorer.threshold() == 8.0


def test_per_type_threshold_env_override(scorer, monkeypatch):
    monkeypatch.setenv("SCORE_THRESHOLD_KOL", "6.0")
    assert scorer.threshold("kol") == 6.0
    # default unaffected by the per-type override
    monkeypatch.delenv("SCORE_THRESHOLD", raising=False)
    assert scorer.threshold("default") == 6.8


def test_empty_or_invalid_env_falls_back_to_config(scorer, monkeypatch):
    monkeypatch.setenv("SCORE_THRESHOLD", "")
    assert scorer.threshold() == 6.8
    monkeypatch.setenv("SCORE_THRESHOLD", "not_a_number")
    assert scorer.threshold() == 6.8


def test_unknown_type_falls_back_to_default(scorer, monkeypatch):
    monkeypatch.delenv("SCORE_THRESHOLD_MYSTERY", raising=False)
    assert scorer.threshold("mystery") == 6.8
