"""SEC EDGAR HTTP client with User-Agent, rate limit, and retry."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SEC_BASE = "https://data.sec.gov"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
MIN_INTERVAL_SEC = float(os.getenv("SEC_MIN_INTERVAL_SEC", "0.11"))
MAX_RETRIES = int(os.getenv("SEC_MAX_RETRIES", "3"))

_DEFAULT_UA = "tech-pulse/0.2 research@example.com"


def sec_user_agent() -> str:
    return os.getenv("SEC_USER_AGENT", _DEFAULT_UA).strip() or _DEFAULT_UA


def sec_headers() -> dict[str, str]:
    return {
        "User-Agent": sec_user_agent(),
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json",
    }


class SecClient:
    """Thin SEC data.sec.gov client with polite pacing."""

    def __init__(self, *, min_interval_sec: float = MIN_INTERVAL_SEC):
        self._min_interval = min_interval_sec
        self._last_request_at = 0.0

    def _pace(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def get_json(self, url: str, *, host_allowlist: tuple[str, ...] = ("data.sec.gov", "www.sec.gov")) -> Any:
        parsed = httpx.URL(url)
        if parsed.host not in host_allowlist:
            raise ValueError(f"SEC client refused host: {parsed.host}")

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            self._pace()
            try:
                with httpx.Client(timeout=30, headers=sec_headers(), follow_redirects=True) as client:
                    resp = client.get(url)
                    self._last_request_at = time.monotonic()
                    if resp.status_code == 429:
                        time.sleep(2 ** attempt)
                        continue
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                last_exc = exc
                logger.warning("SEC GET failed (attempt %d): %s %s", attempt + 1, url[:120], exc)
                time.sleep(0.5 * (attempt + 1))
        if last_exc:
            raise last_exc
        raise RuntimeError(f"SEC GET failed: {url}")
