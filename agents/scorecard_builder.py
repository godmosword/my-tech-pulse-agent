"""Build earnings_v3 scorecard with GAAP/Non-GAAP basis alignment."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from agents.earnings_models import EarningsFact, EarningsReport
from agents.earnings_v3_models import (
    AccountingBasis,
    HeadlineVerdict,
    MarketContext,
    MetricValue,
    Scorecard,
)
from agents.eps_non_gaap_extractor import extract_non_gaap_eps_diluted
from sources.sec_xbrl_fetcher import SecXbrlFetcher

logger = logging.getLogger(__name__)

_GAAP: AccountingBasis = "GAAP"
_NON_GAAP: AccountingBasis = "Non-GAAP"


def align_basis(actual_basis: AccountingBasis, estimate_basis: AccountingBasis) -> AccountingBasis:
    if actual_basis == "Unknown" or estimate_basis == "Unknown":
        return "Unknown"
    if actual_basis == estimate_basis:
        return actual_basis
    return "Mixed"


def compute_surprise_pct(actual: float, estimate: float) -> Optional[float]:
    if estimate == 0:
        return None
    return round(((actual - estimate) / abs(estimate)) * 100.0, 2)


def compute_yoy_pct(current: float, prior: float) -> Optional[float]:
    if prior == 0:
        return None
    return round(((current - prior) / abs(prior)) * 100.0, 2)


def _prior_fiscal_period(fiscal_year: int, fiscal_period: str) -> tuple[int, str]:
    fp = fiscal_period.upper().strip()
    if fp.startswith("Q") and len(fp) >= 2 and fp[1:].isdigit():
        q = int(fp[1:])
        if q > 1:
            return fiscal_year, f"Q{q - 1}"
        return fiscal_year - 1, "Q4"
    return fiscal_year - 1, "Q4"


def _metric_from_headline(metrics: list[EarningsFact], name: str) -> Optional[float]:
    for m in metrics:
        if m.metric == name:
            return m.value
    return None


def _xbrl_metric_for_period(
    xbrl: SecXbrlFetcher,
    company_facts: dict,
    metric: str,
    fiscal_year: int,
    fiscal_period: str,
) -> Optional[float]:
    from sources.sec_concept_map import HEADLINE_CONCEPTS  # noqa: PLC0415

    spec = next((s for s in HEADLINE_CONCEPTS if s.metric == metric), None)
    if not spec:
        return None
    entries = xbrl.extract_concept_entries(company_facts, spec)
    fp_u = fiscal_period.upper()
    for row in entries:
        if row.get("val") is None:
            continue
        try:
            fy = int(row["fy"])
        except (TypeError, ValueError):
            continue
        if fy == fiscal_year and str(row.get("fp") or "").upper() == fp_u:
            return float(row["val"])
    return None


def _build_metric_row(
    *,
    actual: Optional[float],
    estimate: Optional[float],
    actual_basis: AccountingBasis,
    estimate_basis: AccountingBasis,
    actual_source: str,
    estimate_source: str,
    prior_actual: Optional[float] = None,
) -> MetricValue:
    basis = align_basis(actual_basis, estimate_basis)
    surprise: Optional[float] = None
    if (
        actual is not None
        and estimate is not None
        and basis not in ("Mixed", "Unknown")
    ):
        surprise = compute_surprise_pct(actual, estimate)
    elif basis == "Mixed":
        logger.debug(
            "Skipping surprise: actual_basis=%s estimate_basis=%s",
            actual_basis,
            estimate_basis,
        )

    yoy = None
    if actual is not None and prior_actual is not None:
        yoy = compute_yoy_pct(actual, prior_actual)

    return MetricValue(
        actual=actual,
        estimate=estimate,
        surprise_pct=surprise,
        yoy_pct=yoy,
        accounting_basis=basis,
        actual_source=actual_source,  # type: ignore[arg-type]
        estimate_source=estimate_source,  # type: ignore[arg-type]
    )


def _headline_verdict(scorecard: Scorecard) -> HeadlineVerdict:
    surprises: list[float] = []
    for row in (scorecard.revenue, scorecard.eps, scorecard.gross_margin_pct):
        if row is None or row.surprise_pct is None or row.accounting_basis == "Mixed":
            continue
        surprises.append(row.surprise_pct)

    if not surprises:
        return "無法判定"

    beats = sum(1 for s in surprises if s > 0.5)
    misses = sum(1 for s in surprises if s < -0.5)
    if beats == len(surprises):
        return "雙擊"
    if misses == len(surprises):
        return "雙殺"
    if beats > 0 and misses > 0:
        return "喜憂參半"
    if beats > misses:
        return "雙擊"
    if misses > beats:
        return "雙殺"
    return "喜憂參半"


def _vendor_estimate(vendor_estimates: dict[str, Any], key: str) -> tuple[Optional[float], AccountingBasis]:
    block = vendor_estimates.get(key) if vendor_estimates else None
    if not isinstance(block, dict):
        return None, "Unknown"
    val = block.get("value")
    if val is None:
        return None, "Unknown"
    try:
        num = float(val)
    except (TypeError, ValueError):
        return None, "Unknown"
    basis_raw = str(block.get("basis") or "Non-GAAP" if key == "eps" else "GAAP")
    basis: AccountingBasis = "Non-GAAP" if "non" in basis_raw.lower() else "GAAP"
    return num, basis


def build_scorecard(
    report: EarningsReport,
    *,
    company_facts: dict,
    xbrl: SecXbrlFetcher,
    filing_text: str = "",
    vendor_estimates: dict[str, Any] | None = None,
) -> Scorecard:
    vendor_estimates = vendor_estimates or {}
    metrics = report.headline_metrics
    fy = report.fiscal_year
    fp = report.fiscal_period or ""

    rev_actual = _metric_from_headline(metrics, "revenue")
    eps_gaap = _metric_from_headline(metrics, "eps_diluted") or _metric_from_headline(
        metrics, "eps_basic"
    )
    gross_profit = _metric_from_headline(metrics, "gross_profit")

    rev_est, rev_est_basis = _vendor_estimate(vendor_estimates, "revenue")
    eps_est, eps_est_basis = _vendor_estimate(vendor_estimates, "eps")
    gm_est, gm_est_basis = _vendor_estimate(vendor_estimates, "gross_margin_pct")

    prior_rev = prior_gp = None
    if fy is not None and fp:
        py, pfp = _prior_fiscal_period(int(fy), fp)
        prior_rev = _xbrl_metric_for_period(xbrl, company_facts, "revenue", py, pfp)
        prior_gp = _xbrl_metric_for_period(xbrl, company_facts, "gross_profit", py, pfp)

    revenue_row = _build_metric_row(
        actual=rev_actual,
        estimate=rev_est,
        actual_basis=_GAAP,
        estimate_basis=rev_est_basis if rev_est is not None else "Unknown",
        actual_source="XBRL",
        estimate_source="Vendor" if rev_est is not None else "Unknown",
        prior_actual=prior_rev,
    )

    eps_actual = extract_non_gaap_eps_diluted(filing_text)
    eps_actual_basis: AccountingBasis = _NON_GAAP if eps_actual is not None else _GAAP
    eps_actual_source = "8-K Text" if eps_actual is not None else "XBRL"
    if eps_actual is None:
        eps_actual = eps_gaap

    eps_row = _build_metric_row(
        actual=eps_actual,
        estimate=eps_est,
        actual_basis=eps_actual_basis,
        estimate_basis=eps_est_basis if eps_est is not None else "Unknown",
        actual_source=eps_actual_source,
        estimate_source="Vendor" if eps_est is not None else "Unknown",
    )

    gross_margin_row: Optional[MetricValue] = None
    if rev_actual and rev_actual != 0 and gross_profit is not None:
        gm_actual = (gross_profit / rev_actual) * 100.0
        prior_gm = None
        if prior_rev and prior_gp and prior_rev != 0:
            prior_gm = (prior_gp / prior_rev) * 100.0
        gross_margin_row = _build_metric_row(
            actual=round(gm_actual, 2),
            estimate=gm_est,
            actual_basis=_GAAP,
            estimate_basis=gm_est_basis if gm_est is not None else "Unknown",
            actual_source="XBRL",
            estimate_source="Vendor" if gm_est is not None else "Unknown",
            prior_actual=round(prior_gm, 2) if prior_gm is not None else None,
        )

    scorecard = Scorecard(
        revenue=revenue_row,
        eps=eps_row,
        gross_margin_pct=gross_margin_row,
    )
    scorecard.headline_verdict = _headline_verdict(scorecard)
    return scorecard


def build_market_context(
    vendor_market: dict[str, Any] | None = None,
) -> MarketContext:
    vendor_market = vendor_market or {}
    session_raw = str(vendor_market.get("session") or "unknown").lower()
    session = session_raw if session_raw in {"pre", "post", "unknown"} else "unknown"
    price = vendor_market.get("price_usd")
    try:
        price_f = float(price) if price is not None else None
    except (TypeError, ValueError):
        price_f = None
    return MarketContext(
        report_generated_at=datetime.now(timezone.utc),
        price_usd=price_f,
        earnings_date=vendor_market.get("earnings_date"),
        session=session,  # type: ignore[arg-type]
    )


def surprise_dict_from_scorecard(scorecard: Scorecard) -> dict[str, Any]:
    """Legacy flat surprise map for backward compat."""
    out: dict[str, Any] = {}
    if scorecard.revenue and scorecard.revenue.surprise_pct is not None:
        out["revenue_beat_pct"] = scorecard.revenue.surprise_pct
    if scorecard.eps and scorecard.eps.surprise_pct is not None:
        out["eps_beat_pct"] = scorecard.eps.surprise_pct
    if scorecard.gross_margin_pct and scorecard.gross_margin_pct.surprise_pct is not None:
        out["gross_margin_bps"] = scorecard.gross_margin_pct.surprise_pct
    return out


def apply_scorecard_v3(
    report: EarningsReport,
    *,
    company_facts: dict,
    xbrl: SecXbrlFetcher,
    filing_text: str = "",
    vendor_estimates: dict[str, Any] | None = None,
    vendor_market: dict[str, Any] | None = None,
) -> EarningsReport:
    scorecard = build_scorecard(
        report,
        company_facts=company_facts,
        xbrl=xbrl,
        filing_text=filing_text,
        vendor_estimates=vendor_estimates,
    )
    market_context = build_market_context(vendor_market)
    surprise = surprise_dict_from_scorecard(scorecard)
    return report.model_copy(
        update={
            "schema_version": "earnings_v3",
            "scorecard": scorecard,
            "market_context": market_context,
            "surprise": surprise,
            "transcript_status": "pending",
        }
    )
