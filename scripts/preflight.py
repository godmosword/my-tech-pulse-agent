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
