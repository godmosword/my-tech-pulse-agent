"""Optional vendor enrichment for earnings (FMP / Finnhub). Default off."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_VENDOR_CALLS_PER_RUN = int(os.getenv("MAX_VENDOR_CALLS_PER_RUN", "20"))


@dataclass
class VendorEnrichmentResult:
    estimates: dict[str, Any] = field(default_factory=dict)
    surprise: dict[str, Any] = field(default_factory=dict)
    calendar_events: list[dict[str, Any]] = field(default_factory=list)
    calls_made: int = 0
    enriched: bool = False


class VendorEarningsProvider:
    """Thin abstraction; real HTTP providers can be added incrementally."""

    def __init__(self):
        self.mode = os.getenv("EARNINGS_VENDOR_MODE", "off").strip().lower()
        self.fmp_key = os.getenv("FMP_API_KEY", "").strip()
        self.finnhub_key = os.getenv("FINNHUB_API_KEY", "").strip()
        self._calls = 0

    def enabled(self) -> bool:
        return self.mode in {"free", "paid"} and bool(self.fmp_key or self.finnhub_key)

    def enrich_ticker(self, ticker: str) -> VendorEnrichmentResult:
        if not self.enabled() or self._calls >= MAX_VENDOR_CALLS_PER_RUN:
            return VendorEnrichmentResult()
        self._calls += 1
        # Free-tier HTTP wiring is optional; SEC-only path must remain fully functional.
        logger.debug("Vendor enrichment skipped (stub) for %s mode=%s", ticker, self.mode)
        return VendorEnrichmentResult(calls_made=1)

    def get_calendar(self, horizon_days: int = 30) -> list[dict[str, Any]]:
        if not self.enabled():
            return []
        return []

    @property
    def calls_made(self) -> int:
        return self._calls


def vendor_estimate_payload(
    *,
    vendor_name: str,
    endpoint: str,
    as_of_date: datetime | None = None,
    data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_type": "vendor_estimate",
        "vendor_name": vendor_name,
        "endpoint": endpoint,
        "as_of_date": (as_of_date or datetime.now(timezone.utc)).isoformat(),
        **data,
    }
