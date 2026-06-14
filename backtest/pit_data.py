"""Point-in-time data helpers for historical signal replay."""

from __future__ import annotations

import copy
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sources.sec_submissions import SecSubmissionsClient, filing_archive_url
from sources.ticker_cik_map import format_cik

logger = logging.getLogger(__name__)

QUARTERLY_FORMS = frozenset({"10-Q", "10-K", "10-Q/A", "10-K/A"})


def _parse_day(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _entry_filed_day(entry: dict[str, Any]) -> date | None:
    return _parse_day(str(entry.get("filed") or ""))


def list_historical_earnings(
    cik: str,
    *,
    since: str = "2022-01-01",
    until: str | None = None,
    submissions: SecSubmissionsClient | None = None,
) -> list[dict[str, Any]]:
    """List historical 10-Q/10-K from SEC submissions, oldest filed first."""
    since_day = _parse_day(since)
    if since_day is None:
        raise ValueError(f"Invalid since date: {since!r}")
    until_day = _parse_day(until) if until else date.today()
    if until_day is None:
        raise ValueError(f"Invalid until date: {until!r}")

    client = submissions or SecSubmissionsClient()
    padded = format_cik(cik)
    raw = client.get_submissions(padded)
    out: list[dict[str, Any]] = []
    for row in client.iter_recent_filings(raw):
        form = str(row.get("form") or "").strip().upper()
        if form not in QUARTERLY_FORMS:
            continue
        filed = _parse_day(str(row.get("filingDate") or ""))
        if filed is None or filed < since_day or filed > until_day:
            continue
        accession = str(row.get("accessionNumber") or "").strip()
        if not accession:
            continue
        primary = str(row.get("primaryDocument") or "").strip()
        out.append(
            {
                "accession": accession,
                "form": form,
                "filed": filed.isoformat(),
                "period_end": str(row.get("reportDate") or "") or None,
                "primary_document": primary,
                "filing_url": filing_archive_url(padded, accession, primary),
            }
        )
    out.sort(key=lambda r: r["filed"])
    return out


def reconstruct_company_facts_asof(
    company_facts: dict[str, Any],
    *,
    asof_filed_date: str,
) -> dict[str, Any]:
    """Return a copy of companyfacts with only entries filed on or before asof.

    Point-in-time core: simulates what was knowable at the SEC filing date.
    """
    asof = _parse_day(asof_filed_date)
    if asof is None:
        raise ValueError(f"Invalid asof_filed_date: {asof_filed_date!r}")

    cloned = copy.deepcopy(company_facts)
    facts_root = cloned.get("facts")
    if not isinstance(facts_root, dict):
        return cloned

    for taxonomy in facts_root.values():
        if not isinstance(taxonomy, dict):
            continue
        for concept in taxonomy.values():
            if not isinstance(concept, dict):
                continue
            units = concept.get("units")
            if not isinstance(units, dict):
                continue
            for unit_key, entries in list(units.items()):
                if not isinstance(entries, list):
                    continue
                kept = [
                    e
                    for e in entries
                    if isinstance(e, dict)
                    and (fd := _entry_filed_day(e)) is not None
                    and fd <= asof
                ]
                if kept:
                    units[unit_key] = kept
                else:
                    del units[unit_key]
    return cloned


def candle_series(candle: dict[str, Any] | None) -> list[tuple[str, float]]:
    """Parse Finnhub candle payload to sorted (YYYY-MM-DD, close) pairs."""
    if not candle or candle.get("s") != "ok":
        return []
    ts_list = candle.get("t") or []
    closes = candle.get("c") or []
    out: list[tuple[str, float]] = []
    for ts, close in zip(ts_list, closes, strict=False):
        try:
            day = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
            out.append((day, float(close)))
        except (TypeError, ValueError, OSError):
            continue
    return sorted(out, key=lambda x: x[0])


def first_trading_day_after(
    finnhub: Any,
    symbol: str,
    *,
    from_date: str,
) -> str | None:
    """First session date strictly after from_date (post-filing decision day)."""
    anchor = _parse_day(from_date)
    if anchor is None:
        return None
    end = (anchor + timedelta(days=15)).isoformat()
    candle = finnhub.candle(symbol, around=end, days_back=30)
    series = candle_series(candle)
    for day, _ in series:
        if day > from_date:
            return day
    return None


def first_trading_day_on_or_after(
    finnhub: Any,
    symbol: str,
    *,
    from_date: str,
) -> str | None:
    """First session date >= from_date with a daily close."""
    anchor = _parse_day(from_date)
    if anchor is None:
        return None
    end = (anchor + timedelta(days=15)).isoformat()
    candle = finnhub.candle(symbol, around=from_date, days_back=10)
    series = candle_series(candle)
    if not series:
        candle = finnhub.candle(
            symbol,
            around=end,
            days_back=30,
        )
        series = candle_series(candle)
    for day, _ in series:
        if day >= from_date:
            return day
    return None


def _closes_on_or_after(series: list[tuple[str, float]], from_date: str) -> list[float]:
    return [c for d, c in series if d >= from_date]


def price_after(
    finnhub: Any,
    symbol: str,
    *,
    from_date: str,
    trading_days: int,
) -> float | None:
    """Close on the trading_days-th session on or after from_date (1 = decision day)."""
    if trading_days < 1:
        return None
    anchor = _parse_day(from_date)
    if anchor is None:
        return None
    window_end = (anchor + timedelta(days=max(trading_days * 3, 30))).isoformat()
    candle = finnhub.candle(symbol, around=window_end, days_back=max(trading_days * 3, 90))
    series = candle_series(candle)
    if not series:
        return None
    closes = _closes_on_or_after(series, from_date)
    if len(closes) < trading_days:
        return None
    return closes[trading_days - 1]


def return_between(
    finnhub: Any,
    symbol: str,
    *,
    start_date: str,
    horizon_trading_days: int,
) -> float | None:
    """Percent return from start_date close through horizon_trading_days later."""
    start_px = price_after(finnhub, symbol, from_date=start_date, trading_days=1)
    end_px = price_after(
        finnhub,
        symbol,
        from_date=start_date,
        trading_days=horizon_trading_days + 1,
    )
    if start_px is None or end_px is None or start_px == 0:
        return None
    return round(((end_px - start_px) / abs(start_px)) * 100.0, 4)
