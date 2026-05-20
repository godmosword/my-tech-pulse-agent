"""Runtime environment helpers (staging vs production toggles)."""

from __future__ import annotations

import os


def tech_pulse_env() -> str:
    return (os.getenv("TECH_PULSE_ENV") or "production").strip().lower()


def is_staging() -> bool:
    return tech_pulse_env() == "staging"


def semantic_prefilter_enabled() -> bool:
    """True when SEMANTIC_PREFILTER_ENABLED=1 or TECH_PULSE_ENV=staging."""
    flag = (os.getenv("SEMANTIC_PREFILTER_ENABLED") or "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    return is_staging()


def semantic_prefilter_threshold() -> float:
    return float(os.getenv("SEMANTIC_PREFILTER_THRESHOLD", "0.85"))
