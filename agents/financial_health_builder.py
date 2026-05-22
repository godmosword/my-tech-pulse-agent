"""Build §5 financial health metrics from XBRL."""

from __future__ import annotations

import re
from typing import Optional

from agents.earnings_models import EarningsReport
from agents.earnings_v3_models import FinancialHealth
from agents.scorecard_builder import _prior_fiscal_period, _xbrl_metric_for_period
from sources.sec_concept_map import HEALTH_CONCEPTS
from sources.sec_xbrl_fetcher import SecXbrlFetcher


def _metric(
    xbrl: SecXbrlFetcher,
    company_facts: dict,
    metric: str,
    fy: int,
    fp: str,
) -> Optional[float]:
    from sources.sec_concept_map import ConceptSpec  # noqa: PLC0415

    spec = next((s for s in HEALTH_CONCEPTS if s.metric == metric), None)
    if not spec:
        return None
    entries = xbrl.extract_concept_entries(company_facts, spec)
    fp_u = fp.upper()
    for row in entries:
        if row.get("val") is None:
            continue
        try:
            if int(row.get("fy")) == fy and str(row.get("fp") or "").upper() == fp_u:
                return float(row["val"])
        except (TypeError, ValueError):
            continue
    return None


def _shareholder_returns_from_text(text: str) -> str:
    parts: list[str] = []
    if re.search(r"repurchas|buyback", text, re.I):
        m = re.search(
            r"(?:repurchas\w*|buyback)[^.]{0,80}?\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(billion|million|B|M)?",
            text,
            re.I,
        )
        if m:
            parts.append(f"股票回購提及（原文含 ${m.group(1)} {m.group(2) or ''}）".strip())
        else:
            parts.append("提及股票回購")
    if re.search(r"dividend", text, re.I):
        parts.append("提及股息政策")
    return "；".join(parts) if parts else ""


def build_financial_health(
    report: EarningsReport,
    *,
    company_facts: dict,
    xbrl: SecXbrlFetcher,
    filing_text: str = "",
) -> FinancialHealth:
    fy = report.fiscal_year
    fp = report.fiscal_period or ""
    ocf = capex = None
    if fy is not None and fp:
        ocf = _metric(xbrl, company_facts, "operating_cash_flow", int(fy), fp)
        capex = _metric(xbrl, company_facts, "capex", int(fy), fp)
        if capex is not None and capex < 0:
            capex = abs(capex)

    fcf = None
    fcf_conv = None
    if ocf is not None:
        fcf = ocf - (capex or 0.0)
        rev = None
        for m in report.headline_metrics:
            if m.metric == "revenue":
                rev = m.value
                break
        if rev and rev > 0 and fcf is not None:
            fcf_conv = round((fcf / rev) * 100.0, 1)

    roic_trend = "資料不足"
    if fy is not None and fp:
        py, pfp = _prior_fiscal_period(int(fy), fp)
        ni = _xbrl_metric_for_period(xbrl, company_facts, "net_income", py, pfp)
        ni_now = _xbrl_metric_for_period(xbrl, company_facts, "net_income", int(fy), fp)
        if ni and ni_now:
            roic_trend = "上升" if ni_now > ni else "下降" if ni_now < ni else "持平"

    return FinancialHealth(
        fcf=fcf,
        fcf_conversion_pct=fcf_conv,
        roic_trend=roic_trend,
        shareholder_returns_zh=_shareholder_returns_from_text(filing_text),
    )
