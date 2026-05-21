"""Source-aware fact_guard for earnings_v2 reports."""

from __future__ import annotations

import re
from typing import Optional

from agents.earnings_models import EarningsFact, EarningsReport

_QUOTE_MIN_LEN = 12


def _normalize_text(text: str) -> str:
    return re.sub(r"[$,\s]", "", text.lower())


def _value_in_source(value: float, source_text: str) -> bool:
    clean = _normalize_text(source_text)
    for fmt in (str(value), f"{value:.1f}", f"{value:.2f}", str(int(value))):
        if _normalize_text(fmt) in clean:
            return True
    return False


def verify_quote_substring(quote: str, source_text: str) -> bool:
    q = quote.strip()
    if len(q) < _QUOTE_MIN_LEN:
        return False
    # Allow minor whitespace differences
    collapsed_src = " ".join(source_text.split())
    collapsed_q = " ".join(q.split())
    return collapsed_q in collapsed_src


def verify_xbrl_fact(fact: EarningsFact) -> bool:
    if fact.source_type != "sec_xbrl":
        return False
    return bool(fact.source_tag and fact.value is not None)


def apply_fact_guard_v2(
    report: EarningsReport,
    *,
    filing_text: str = "",
) -> EarningsReport:
    """Validate report fields by source type; clear unverifiable narrative fields."""
    violations: list[str] = []
    headline: list[EarningsFact] = []
    for fact in report.headline_metrics:
        if verify_xbrl_fact(fact):
            headline.append(fact)
        else:
            violations.append(f"headline.{fact.metric}")

    segment: list[EarningsFact] = []
    for fact in report.segment_metrics:
        if fact.source_type == "sec_xbrl" and verify_xbrl_fact(fact):
            segment.append(fact)
        elif fact.source_type.startswith("vendor") and fact.source_tag:
            segment.append(fact)
        else:
            violations.append(f"segment.{fact.metric}")

    quotes: list[str] = []
    if filing_text:
        for q in report.key_quotes:
            if verify_quote_substring(q, filing_text):
                quotes.append(q)
            else:
                violations.append("key_quotes")
    else:
        quotes = list(report.key_quotes)

    estimates = dict(report.estimates)
    if estimates and not any(
        isinstance(v, dict) and v.get("source_type", "").startswith("vendor")
        for v in estimates.values()
        if isinstance(v, dict)
    ):
        # Legacy LLM-inferred estimates without vendor metadata — drop
        if estimates:
            violations.append("estimates")
        estimates = {}

    confidence = report.confidence
    if violations:
        confidence = "low"

    return report.model_copy(
        update={
            "headline_metrics": headline,
            "segment_metrics": segment,
            "key_quotes": quotes[:5],
            "estimates": estimates,
            "confidence": confidence,
        }
    )


def strip_llm_numeric_overrides(
    report: EarningsReport,
    llm_revenue: Optional[float],
    llm_eps: Optional[float],
    source_text: str,
) -> tuple[Optional[float], Optional[float]]:
    """Reject LLM-extracted headline numbers not present in filing text."""
    rev = llm_revenue if llm_revenue is None or _value_in_source(llm_revenue, source_text) else None
    eps = llm_eps if llm_eps is None or _value_in_source(llm_eps, source_text) else None
    return rev, eps
