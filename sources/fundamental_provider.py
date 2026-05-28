"""Optional FMP fundamental enrichment; default off."""

from __future__ import annotations

import logging
import os

from agents.earnings_models import EarningsReport
from agents.earnings_v3_models import SurprisePoint, ValuationRatios
from sources.fmp_normalize import extract_fundamentals
from sources.fmp_provider import FmpProvider

logger = logging.getLogger(__name__)


class FundamentalProvider:
    """FMP-backed ratios / cash-flow fill-in; SEC-only when disabled."""

    def __init__(self) -> None:
        self.mode = os.getenv("EARNINGS_FUNDAMENTAL_MODE", "off").strip().lower()
        self.fmp_key = os.getenv("FMP_API_KEY", "").strip()
        self.max_calls = int(os.getenv("MAX_FMP_CALLS_PER_RUN", "40"))
        self._calls = 0
        self._fmp: FmpProvider | None = None
        if self.fmp_key:
            self._fmp = FmpProvider(self.fmp_key, on_call=self._allow_call)

    def _allow_call(self) -> bool:
        if self._calls >= self.max_calls:
            return False
        self._calls += 1
        return True

    def enabled(self) -> bool:
        return self.mode in {"free", "paid"} and self._fmp is not None

    def enrich_for_report(self, report: EarningsReport) -> dict:
        if not self.enabled():
            return {}
        if self._fmp is None:
            return {}
        try:
            return extract_fundamentals(
                report.ticker,
                fmp=self._fmp,
                fiscal_year=report.fiscal_year,
                fiscal_period=report.fiscal_period or "",
            )
        except Exception as exc:
            logger.warning("FMP extract failed for %s: %s", report.ticker, exc)
            return {}


def attach_fmp_fields_to_report(
    report: EarningsReport,
    fundamentals: dict,
) -> EarningsReport:
    """Map normalized fundamentals onto additive EarningsReport fields."""
    if not fundamentals:
        return report
    ratios_raw = fundamentals.get("ratios") or {}
    cf_raw = fundamentals.get("cash_flow") or {}
    period_matched = str(fundamentals.get("period_matched") or "none")
    valuation = ValuationRatios(
        gross_margin=ratios_raw.get("gross_margin"),
        operating_margin=ratios_raw.get("operating_margin"),
        net_margin=ratios_raw.get("net_margin"),
        roe=ratios_raw.get("roe"),
        roic=ratios_raw.get("roic"),
        debt_to_equity=ratios_raw.get("debt_to_equity"),
        fcf_margin=cf_raw.get("fcf_margin") or ratios_raw.get("fcf_margin"),
        period_matched=period_matched,
    )
    surprise_history = [
        SurprisePoint(**point)
        for point in (fundamentals.get("surprise_history") or [])
        if isinstance(point, dict)
    ]
    return report.model_copy(
        update={"ratios": valuation, "surprise_history": surprise_history},
    )
