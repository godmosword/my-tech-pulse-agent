"""Production preflight checks for tech-pulse.

This script validates local/GitHub Actions configuration without calling
external APIs. It is meant to fail fast before a scheduled production run.
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

    workflow = ROOT / ".github" / "workflows" / "pages.yml"
    if not workflow.exists():
        failures.append("Missing GitHub Pages workflow: .github/workflows/pages.yml")
    else:
        workflow_text = workflow.read_text(encoding="utf-8")
        for needle in ("python -m pipeline.crew", "upload-pages-artifact", "docs/"):
            if needle not in workflow_text:
                failures.append(f"Pages workflow missing {needle!r}")

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
