"""Normalize FMP raw payloads to report-period fundamentals."""

from __future__ import annotations

from typing import Any

from sources.fmp_provider import FmpProvider


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(value: Any) -> float | None:
    """FMP margins/returns are often 0–1 ratios; expose as percentage."""
    v = _as_float(value)
    if v is None:
        return None
    if abs(v) <= 1.5:
        return round(v * 100.0, 2)
    return round(v, 2)


def _row_year(row: dict[str, Any]) -> int | None:
    for key in ("calendarYear", "fiscalYear", "year"):
        v = row.get(key)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
    date = row.get("date")
    if isinstance(date, str) and len(date) >= 4:
        try:
            return int(date[:4])
        except ValueError:
            return None
    return None


def _row_period(row: dict[str, Any]) -> str:
    p = str(row.get("period") or "").upper().strip()
    if p.startswith("Q"):
        return p
    date = row.get("date")
    if isinstance(date, str) and len(date) >= 7:
        month = int(date[5:7])
        q = (month - 1) // 3 + 1
        return f"Q{q}"
    return ""


def match_period(
    rows: list[dict[str, Any]],
    *,
    fiscal_year: int | None,
    fiscal_period: str,
) -> tuple[dict[str, Any] | None, str]:
    """Match calendarYear + period (Q1..Q4); fallback to newest row as approx."""
    if not rows:
        return None, "none"
    fp = fiscal_period.upper().strip()
    if fiscal_year is not None and fp:
        for row in rows:
            if _row_year(row) == int(fiscal_year) and _row_period(row) == fp:
                return row, "exact"
    return rows[0], "approx"


def _surprise_period(row: dict[str, Any]) -> str:
    date = row.get("date")
    if isinstance(date, str) and len(date) >= 7:
        year = date[:4]
        month = int(date[5:7])
        q = (month - 1) // 3 + 1
        return f"{year}Q{q}"
    period = row.get("period")
    if period:
        return str(period)
    return str(date or "")


def extract_fundamentals(
    symbol: str,
    *,
    fmp: FmpProvider,
    fiscal_year: int | None,
    fiscal_period: str,
    limit: int = 8,
) -> dict[str, Any]:
    """Fetch and normalize FMP data for one earnings report period."""
    sym = symbol.upper()
    income_rows = fmp.income_statement(sym, limit=limit)
    bs_rows = fmp.balance_sheet(sym, limit=limit)
    cf_rows = fmp.cash_flow(sym, limit=limit)
    ratio_rows = fmp.ratios(sym, limit=limit)
    km_rows = fmp.key_metrics(sym, limit=limit)
    surprise_rows = fmp.earnings_surprises(sym, limit=limit)

    income, _ = match_period(income_rows, fiscal_year=fiscal_year, fiscal_period=fiscal_period)
    bs, bs_match = match_period(bs_rows, fiscal_year=fiscal_year, fiscal_period=fiscal_period)
    cf, cf_match = match_period(cf_rows, fiscal_year=fiscal_year, fiscal_period=fiscal_period)
    ratios_row, ratios_match = match_period(
        ratio_rows, fiscal_year=fiscal_year, fiscal_period=fiscal_period
    )
    km_row, km_match = match_period(km_rows, fiscal_year=fiscal_year, fiscal_period=fiscal_period)

    matches = [m for m in (bs_match, cf_match, ratios_match, km_match) if m != "none"]
    if matches and all(m == "exact" for m in matches):
        period_matched = "exact"
    elif matches:
        period_matched = "approx" if "approx" in matches else matches[0]
    else:
        period_matched = "none"

    revenue = _as_float((income or {}).get("revenue"))
    ocf = _as_float((cf or {}).get("operatingCashFlow"))
    capex_raw = _as_float((cf or {}).get("capitalExpenditure"))
    capex = abs(capex_raw) if capex_raw is not None else None
    fcf = _as_float((cf or {}).get("freeCashFlow"))
    if fcf is None and ocf is not None:
        fcf = ocf - (capex or 0.0)

    fcf_margin = None
    if fcf is not None and revenue and revenue > 0:
        fcf_margin = round((fcf / revenue) * 100.0, 2)
    elif km_row:
        fcf_margin = _pct(km_row.get("freeCashFlowYield"))

    roic = _pct((km_row or {}).get("roic"))
    if roic is None and ratios_row:
        roic = _pct(ratios_row.get("returnOnCapitalEmployed"))

    ratios = {
        "gross_margin": _pct((ratios_row or {}).get("grossProfitMargin")),
        "operating_margin": _pct((ratios_row or {}).get("operatingProfitMargin")),
        "net_margin": _pct((ratios_row or {}).get("netProfitMargin")),
        "roe": _pct((ratios_row or {}).get("returnOnEquity")),
        "roic": roic,
        "debt_to_equity": _as_float((ratios_row or {}).get("debtEquityRatio")),
        "fcf_margin": fcf_margin,
    }

    cash_flow = {
        "operating_cf": ocf,
        "capex": capex,
        "free_cash_flow": fcf,
        "fcf_margin": fcf_margin,
    }

    balance_sheet = {
        "total_debt": _as_float((bs or {}).get("totalDebt")),
        "cash_and_st_inv": _as_float((bs or {}).get("cashAndShortTermInvestments")),
        "total_equity": _as_float((bs or {}).get("totalStockholdersEquity")),
    }

    surprise_history: list[dict[str, Any]] = []
    for row in surprise_rows[:limit]:
        actual = _as_float(row.get("actualEarningResult") or row.get("actual"))
        estimate = _as_float(row.get("estimatedEarning") or row.get("estimate"))
        surprise_pct = _as_float(row.get("surprisePercentage") or row.get("surprise"))
        if surprise_pct is None and actual is not None and estimate not in (None, 0):
            surprise_pct = round(((actual - estimate) / abs(estimate)) * 100.0, 2)
        surprise_history.append(
            {
                "period": _surprise_period(row),
                "eps_actual": actual,
                "eps_estimate": estimate,
                "surprise_pct": surprise_pct,
            }
        )

    return {
        "ratios": ratios,
        "cash_flow": cash_flow,
        "balance_sheet": balance_sheet,
        "surprise_history": surprise_history,
        "period_matched": period_matched,
        "source": "fmp",
    }
