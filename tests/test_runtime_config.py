
from pipeline.runtime_config import (
    is_staging,
    semantic_prefilter_enabled,
    semantic_prefilter_threshold,
)


def test_staging_env_enables_semantic_prefilter(monkeypatch):
    monkeypatch.delenv("SEMANTIC_PREFILTER_ENABLED", raising=False)
    monkeypatch.setenv("TECH_PULSE_ENV", "staging")
    assert is_staging() is True
    assert semantic_prefilter_enabled() is True


def test_explicit_flag_enables_semantic_prefilter(monkeypatch):
    monkeypatch.setenv("TECH_PULSE_ENV", "production")
    monkeypatch.setenv("SEMANTIC_PREFILTER_ENABLED", "1")
    assert semantic_prefilter_enabled() is True


def test_production_default_off(monkeypatch):
    monkeypatch.setenv("TECH_PULSE_ENV", "production")
    monkeypatch.delenv("SEMANTIC_PREFILTER_ENABLED", raising=False)
    assert semantic_prefilter_enabled() is False


def test_semantic_prefilter_threshold_default():
    assert semantic_prefilter_threshold() == 0.85
