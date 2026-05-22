"""Optional vendor enrichment for earnings (Finnhub primary). Default off."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from agents.earnings_models import EarningsReport
from sources.finnhub_provider import FinnhubProvider

logger = logging.getLogger(__name__)

MAX_VENDOR_CALLS_PER_RUN = int(os.getenv("MAX_VENDOR_CALLS_PER_RUN", "20"))


@dataclass
class VendorEnrichmentResult:
    estimates: dict[str, Any] = field(default_factory=dict)
    surprise: dict[str, Any] = field(default_factory=dict)
    market_context: dict[str, Any] = field(default_factory=dict)
    calendar_events: list[dict[str, Any]] = field(default_factory=list)
    calls_made: int = 0
    enriched: bool = False


class VendorEarningsProvider:
    """Finnhub-backed vendor enrichment; SEC-only path when disabled."""

    def __init__(self):
        self.mode = os.getenv("EARNINGS_VENDOR_MODE", "off").strip().lower()
        self.finnhub_key = os.getenv("FINNHUB_API_KEY", "").strip()
        self._calls = 0
        self._finnhub: FinnhubProvider | None = None
        if self.finnhub_key:
            self._finnhub = FinnhubProvider(self.finnhub_key)

    def enabled(self) -> bool:
        return self.mode in {"free", "paid"} and self._finnhub is not None

    def enrich_for_report(self, report: EarningsReport) -> VendorEnrichmentResult:
        if not self.enabled() or self._calls >= MAX_VENDOR_CALLS_PER_RUN:
            return VendorEnrichmentResult()
        if self._finnhub is None:
            return VendorEnrichmentResult()

        self._calls += 1
        symbol = report.ticker.upper()
        try:
            estimates = self._finnhub.enrich_estimates(
                symbol,
                fiscal_year=report.fiscal_year,
                fiscal_period=report.fiscal_period,
            )
            market = self._finnhub.enrich_market(
                symbol,
                fiscal_year=report.fiscal_year,
                fiscal_period=report.fiscal_period,
            )
        except Exception as exc:
            logger.warning("Finnhub enrich failed for %s: %s", symbol, exc)
            return VendorEnrichmentResult(calls_made=1)

        enriched = bool(estimates or market.get("price_usd"))
        return VendorEnrichmentResult(
            estimates=estimates,
            market_context=market,
            calls_made=1,
            enriched=enriched,
        )

    def enrich_ticker(self, ticker: str) -> VendorEnrichmentResult:
        """Backward-compatible ticker-only enrich (no fiscal match)."""
        if not self.enabled() or self._calls >= MAX_VENDOR_CALLS_PER_RUN:
            return VendorEnrichmentResult()
        if self._finnhub is None:
            return VendorEnrichmentResult()
        self._calls += 1
        try:
            estimates = self._finnhub.enrich_estimates(ticker, fiscal_year=None, fiscal_period="")
            market = self._finnhub.enrich_market(ticker, fiscal_year=None, fiscal_period="")
        except Exception as exc:
            logger.warning("Finnhub enrich failed for %s: %s", ticker, exc)
            return VendorEnrichmentResult(calls_made=1)
        return VendorEnrichmentResult(
            estimates=estimates,
            market_context=market,
            calls_made=1,
            enriched=bool(estimates),
        )

    def get_calendar(self, _horizon_days: int = 30) -> list[dict[str, Any]]:
        if not self.enabled():
            return []
        return []

    @property
    def calls_made(self) -> int:
        return self._calls
