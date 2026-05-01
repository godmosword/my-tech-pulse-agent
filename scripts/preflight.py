"""Production preflight checks for tech-pulse.

This script validates production configuration without calling external APIs.
It is meant to fail fast before a deployed production run.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ENV = ("GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID")
EXPECTED_MODELS = {
    "GEMINI_MODEL": "gemini-3.1-pro-preview",
    "GEMINI_FLASH_MODEL": "gemini-3-flash-preview",
}
STATE_BACKENDS = {"auto", "sqlite", "firestore"}
MEMORY_BACKENDS = {"firestore"}


def _failures() -> list[str]:
    load_dotenv(ROOT / ".env")
    failures: list[str] = []

    for key in REQUIRED_ENV:
        if not os.getenv(key, "").strip():
            failures.append(f"Missing required env var: {key}")

    for key, expected in EXPECTED_MODELS.items():
        value = os.getenv(key, expected).strip()
        if value != expected:
            failures.append(f"{key} must be {expected!r}, got {value!r}")

    state_backend = os.getenv("STATE_BACKEND", "auto").strip().lower()
    if state_backend not in STATE_BACKENDS:
        failures.append(
            f"STATE_BACKEND must be one of {sorted(STATE_BACKENDS)!r}, got {state_backend!r}"
        )

    if state_backend in {"auto", "firestore"}:
        prefix = os.getenv("FIRESTORE_COLLECTION_PREFIX", "tech_pulse").strip()
        if not prefix:
            failures.append("FIRESTORE_COLLECTION_PREFIX must not be empty for Firestore state")

    memory_enabled = os.getenv("MEMORY_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
    if memory_enabled:
        memory_backend = os.getenv("MEMORY_BACKEND", "firestore").strip().lower()
        if memory_backend not in MEMORY_BACKENDS:
            failures.append(
                f"MEMORY_BACKEND must be one of {sorted(MEMORY_BACKENDS)!r}, got {memory_backend!r}"
            )
        try:
            memory_dim = int(os.getenv("MEMORY_EMBEDDING_DIM", "768"))
        except ValueError:
            failures.append("MEMORY_EMBEDDING_DIM must be an integer")
        else:
            if memory_dim != 768:
                failures.append("MEMORY_EMBEDDING_DIM must be 768 to match the Firestore vector index")

    if not (ROOT / ".env.example").exists():
        failures.append("Missing .env.example")

    return failures


def main() -> int:
    failures = _failures()
    if failures:
        print("Preflight failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Preflight passed: required launch configuration is present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
