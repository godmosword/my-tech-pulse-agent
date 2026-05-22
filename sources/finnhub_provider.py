"""Finnhub HTTP client for earnings estimates, calendar, and quotes."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"
DEFAULT_TIMEOUT = float(os.getenv("FINNHUB_HTTP_TIMEOUT_SEC", "10"))
TRANSCRIPT_TIMEOUT = float(os.getenv("FINNHUB_TRANSCRIPT_TIMEOUT_SEC", "15"))


class FinnhubProvider:
    def __init__(self, api_key: str, *, timeout: float = DEFAULT_TIMEOUT):
        self.api_key = api_key.strip()
        self.timeout = timeout

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        if not self.api_key:
            return None
        q = dict(params or {})
        q["token"] = self.api_key
        url = f"{FINNHUB_BASE}{path}"
        try:
            with httpx.Client(timeout=timeout or self.timeout) as client:
                resp = client.get(url, params=q)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("Finnhub request failed %s: %s", path, exc)
            return None

    def company_earnings(self, symbol: str) -> list[dict[str, Any]]:
        data = self._get("/stock/earnings", {"symbol": symbol.upper()})
        return data if isinstance(data, list) else []

    def quote(self, symbol: str) -> Optional[dict[str, Any]]:
        data = self._get("/quote", {"symbol": symbol.upper()})
        return data if isinstance(data, dict) else None

    def earnings_calendar(
        self,
        symbol: str,
        *,
        days_back: int = 14,
        days_forward: int = 7,
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end = (now + timedelta(days=days_forward)).strftime("%Y-%m-%d")
        data = self._get(
            "/calendar/earnings",
            {"from": start, "to": end, "symbol": symbol.upper()},
        )
        if isinstance(data, dict):
            rows = data.get("earningsCalendar") or data.get("earnings")
            return rows if isinstance(rows, list) else []
        return data if isinstance(data, list) else []

    def match_earnings_row(
        self,
        rows: list[dict[str, Any]],
        *,
        fiscal_year: int | None,
        fiscal_period: str,
    ) -> Optional[dict[str, Any]]:
        """Pick Finnhub earnings row closest to report fiscal period."""
        if not rows:
            return None
        target_q = _fiscal_period_to_quarter_num(fiscal_period)
        if fiscal_year is not None and target_q is not None:
            for row in rows:
                try:
                    year = int(row.get("year") or row.get("fiscalYear") or 0)
                    quarter = int(row.get("quarter") or 0)
                except (TypeError, ValueError):
                    continue
                if year == fiscal_year and quarter == target_q:
                    return row
        return rows[0] if rows else None

    def calendar_session(
        self,
        symbol: str,
        *,
        fiscal_year: int | None,
        fiscal_period: str,
    ) -> tuple[Optional[str], Optional[str]]:
        """Return (earnings_date ISO date, session pre|post|unknown)."""
        rows = self.earnings_calendar(symbol)
        sym = symbol.upper()
        for row in rows:
            if str(row.get("symbol") or "").upper() != sym:
                continue
            date_raw = row.get("date") or row.get("earningsDate")
            hour = str(row.get("hour") or row.get("time") or "").lower()
            session = "unknown"
            if "bmo" in hour or "before" in hour or hour == "am":
                session = "pre"
            elif "amc" in hour or "after" in hour or hour == "pm":
                session = "post"
            date_s = str(date_raw)[:10] if date_raw else None
            return date_s, session
        return None, "unknown"

    def enrich_estimates(
        self,
        symbol: str,
        *,
        fiscal_year: int | None,
        fiscal_period: str,
    ) -> dict[str, Any]:
        rows = self.company_earnings(symbol)
        row = self.match_earnings_row(rows, fiscal_year=fiscal_year, fiscal_period=fiscal_period)
        if not row:
            return {}

        estimates: dict[str, Any] = {}
        rev_est = _float_or_none(row.get("revenueEstimate") or row.get("revenue_estimate"))
        if rev_est is not None:
            estimates["revenue"] = {
                "value": rev_est,
                "basis": "GAAP",
                "source_type": "vendor_estimate",
            }

        eps_est = _float_or_none(row.get("epsEstimate") or row.get("estimate"))
        if eps_est is not None:
            estimates["eps"] = {
                "value": eps_est,
                "basis": "Non-GAAP",
                "source_type": "vendor_estimate",
            }
        return estimates

    def fetch_transcript(
        self,
        symbol: str,
        *,
        year: int,
        quarter: int,
        timeout: float | None = None,
    ) -> tuple[str, str | None]:
        """Return (transcript text, id). Empty text on failure."""
        data = self._get(
            "/stock/transcripts",
            {"symbol": symbol.upper(), "year": year, "quarter": quarter},
            timeout=timeout or TRANSCRIPT_TIMEOUT,
        )
        tid = f"{symbol.upper()}_{year}Q{quarter}"
        if isinstance(data, dict):
            for key in ("transcript", "content", "text"):
                val = data.get(key)
                if isinstance(val, str) and len(val) > 100:
                    return val, tid
            # Finnhub may return list of sections
            if isinstance(data.get("transcript"), list):
                parts = []
                for item in data["transcript"]:
                    if isinstance(item, dict):
                        parts.append(str(item.get("speech") or item.get("content") or ""))
                    elif isinstance(item, str):
                        parts.append(item)
                joined = "\n".join(p for p in parts if p)
                if len(joined) > 100:
                    return joined, tid
        if isinstance(data, str) and len(data) > 100:
            return data, tid
        return "", tid

    def enrich_market(
        self,
        symbol: str,
        *,
        fiscal_year: int | None,
        fiscal_period: str,
    ) -> dict[str, Any]:
        q = self.quote(symbol)
        price = None
        if isinstance(q, dict):
            price = _float_or_none(q.get("c"))
        earnings_date, session = self.calendar_session(
            symbol, fiscal_year=fiscal_year, fiscal_period=fiscal_period
        )
        return {
            "price_usd": price,
            "earnings_date": earnings_date,
            "session": session,
        }


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fiscal_period_to_quarter_num(fiscal_period: str) -> Optional[int]:
    fp = fiscal_period.upper().strip()
    if fp.startswith("Q") and fp[1:].isdigit():
        return int(fp[1:])
    if "Q1" in fp:
        return 1
    if "Q2" in fp:
        return 2
    if "Q3" in fp:
        return 3
    if "Q4" in fp:
        return 4
    return None
