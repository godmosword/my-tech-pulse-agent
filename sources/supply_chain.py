"""Supply-chain indicators: TSM monthly revenue + manual SIA/ASML entries."""

from __future__ import annotations

import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import yaml

from sources._cache import cached_call

logger = logging.getLogger(__name__)

MANUAL_PATH = Path(__file__).resolve().parent.parent / "config" / "supply_chain_manual.yaml"
TWSE_REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TSM_ID = "2330"


def _parse_pct(raw: Any) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip().replace("%", "")
    if not s or s in {".", "-", "—"}:
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _parse_num(raw: Any) -> float | None:
    if raw is None:
        return None
    s = str(raw).replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _roc_year_month_to_iso(ym: str) -> str | None:
    """ROC YYYYMM or YYYY-MM → YYYY-MM."""
    digits = re.sub(r"\D", "", ym)
    if len(digits) == 5:  # e.g. 11401 = ROC114 Jan
        roc_year = int(digits[:3])
        month = int(digits[3:])
        year = roc_year + 1911
        return f"{year}-{month:02d}"
    if len(digits) == 6:  # 202501
        return f"{digits[:4]}-{digits[4:]}"
    return None


def _load_manual() -> dict[str, Any]:
    if not MANUAL_PATH.is_file():
        return {}
    try:
        with open(MANUAL_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        logger.warning("Failed to read %s", MANUAL_PATH, exc_info=True)
        return {}


def _field(row: dict[str, Any], *candidates: str) -> Any:
    lowered = {str(k).lower(): v for k, v in row.items()}
    for c in candidates:
        if c.lower() in lowered:
            return lowered[c.lower()]
    return None


class SupplyChain:
    def __init__(self, *, timeout: float = 20.0, tsm_cache_ttl_sec: int | None = None):
        self.timeout = timeout
        self.tsm_cache_ttl_sec = int(
            tsm_cache_ttl_sec
            if tsm_cache_ttl_sec is not None
            else os.getenv("SUPPLY_CHAIN_CACHE_TTL_SEC", "86400")
        )

    def tsm_monthly_revenue(self) -> list[dict[str, Any]]:
        """TSM (2330) monthly revenue; ascending by month; [] on failure."""

        def _fetch() -> list[dict[str, Any]]:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(TWSE_REVENUE_URL)
                    resp.raise_for_status()
                    payload = resp.json()
            except Exception as exc:
                logger.warning("TSM revenue fetch failed: %s", exc)
                return _tsm_from_mops_html()

            if not isinstance(payload, list):
                return []

            rows: list[dict[str, Any]] = []
            for row in payload:
                if not isinstance(row, dict):
                    continue
                code = str(
                    _field(row, "公司代號", "Company Code", "stock_no", "Code") or ""
                ).strip()
                if code != TSM_ID:
                    continue
                ym_raw = _field(row, "資料年月", "YearMonth", "month", "年月")
                month = _roc_year_month_to_iso(str(ym_raw or ""))
                if not month:
                    continue
                revenue = _parse_num(
                    _field(row, "營業收入", "當月營收", "Monthly Revenue", "revenue")
                )
                yoy = _parse_pct(_field(row, "去年同月增減(%)", "YoY", "yoy_pct"))
                mom = _parse_pct(_field(row, "上月增減(%)", "MoM", "mom_pct"))
                if revenue is None:
                    continue
                rows.append(
                    {
                        "month": month,
                        "revenue_ntd": revenue,
                        "yoy_pct": yoy,
                        "mom_pct": mom,
                        "source": "twse_openapi",
                    }
                )
            rows.sort(key=lambda r: r["month"])
            return rows[-12:]

        cached = cached_call(
            "tsm_monthly_revenue",
            self.tsm_cache_ttl_sec,
            _fetch,
        )
        return cached if isinstance(cached, list) else []

    def sia_semiconductor_sales(self) -> list[dict[str, Any]]:
        manual = _load_manual()
        block = manual.get("sia_semiconductor_sales") or {}
        rows = block.get("rows") or []
        out: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            month = str(row.get("month") or "")
            sales = row.get("sales_usd_b")
            yoy = row.get("yoy_pct")
            if not month or sales is None:
                continue
            out.append(
                {
                    "month": month,
                    "sales_usd_b": float(sales),
                    "yoy_pct": float(yoy) if yoy is not None else None,
                    "source": "manual",
                    "as_of": block.get("as_of"),
                }
            )
        out.sort(key=lambda r: r["month"])
        return out[-12:]

    def asml_bookings(self) -> dict[str, Any] | None:
        manual = _load_manual()
        block = manual.get("asml_bookings")
        if not isinstance(block, dict) or block.get("bookings_eur_b") is None:
            return None
        return {
            "quarter": block.get("quarter"),
            "bookings_eur_b": float(block["bookings_eur_b"]),
            "trend": block.get("trend"),
            "source": "manual",
            "as_of": block.get("as_of"),
            "note": block.get("note"),
        }


def _tsm_from_mops_html() -> list[dict[str, Any]]:
    """Fallback: scrape latest MOPS monthly table for 2330 (best-effort)."""
    today = date.today()
    roc_year = today.year - 1911
    month = today.month
    url = f"https://mops.twse.com.tw/nas/t21/sii/t21sc03_{roc_year}_{month}_0.html"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            text = resp.content.decode("big5", errors="ignore")
    except Exception:
        return []

    # Very loose row match for 2330
    pattern = re.compile(
        r"2330[^0-9]+[\s\S]{0,200}?([0-9,]+)[\s\S]{0,80}?([0-9,\.\-]+)%",
        re.MULTILINE,
    )
    m = pattern.search(text)
    if not m:
        return []
    revenue = _parse_num(m.group(1))
    yoy = _parse_pct(m.group(2))
    if revenue is None:
        return []
    return [
        {
            "month": f"{today.year}-{today.month:02d}",
            "revenue_ntd": revenue,
            "yoy_pct": yoy,
            "mom_pct": None,
            "source": "mops_scrape",
        }
    ]
