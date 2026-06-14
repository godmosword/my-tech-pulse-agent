"""Map macro + supply-chain data to per-theme tailwind/headwind bias."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from sources.macro_fred import MacroFred
from sources.supply_chain import SupplyChain

logger = logging.getLogger(__name__)

BiasLabel = Literal["順風", "中性", "逆風"]

THEME_DRIVERS: dict[str, dict[str, list[str]]] = {
    "ai_silicon": {
        "tailwind": ["半導體銷售YoY上升", "TSM營收加速", "HBM需求"],
        "headwind": ["利率上升", "CPI高企", "半導體銷售YoY下降"],
    },
    "memory": {
        "tailwind": ["DRAM/HBM循環上行", "半導體銷售YoY上升", "TSM營收加速"],
        "headwind": ["記憶體價格下跌", "半導體銷售YoY下降", "利率上升"],
    },
    "equipment": {
        "tailwind": ["晶圓廠資本支出", "ASML bookings上升", "半導體銷售YoY上升"],
        "headwind": ["半導體銷售YoY下降", "利率上升"],
    },
    "semiconductor": {
        "tailwind": ["半導體銷售YoY上升", "TSM營收加速"],
        "headwind": ["利率上升", "半導體銷售YoY下降", "CPI高企"],
    },
    "cloud_software": {
        "tailwind": ["利率下降", "CPI回落"],
        "headwind": ["利率上升", "CPI高企", "10Y殖利率上升"],
    },
    "hardware": {
        "tailwind": ["半導體銷售YoY上升", "TSM營收加速"],
        "headwind": ["利率上升", "半導體銷售YoY下降"],
    },
    "optical": {
        "tailwind": ["半導體銷售YoY上升", "TSM營收加速"],
        "headwind": ["半導體銷售YoY下降"],
    },
    "consumer_devices": {
        "tailwind": ["CPI回落", "利率下降"],
        "headwind": ["CPI高企", "利率上升"],
    },
}


def _active_signals(
    *,
    fred_snapshot: dict[str, Any],
    tsm_rev: list[dict[str, Any]],
    sia_sales: list[dict[str, Any]],
    asml_bookings: dict[str, Any] | None,
) -> dict[str, str]:
    """Return signal_key → human-readable driver_zh (only data-backed)."""
    signals: dict[str, str] = {}

    ff = fred_snapshot.get("fed_funds_rate") or {}
    if ff.get("trend") == "上升":
        signals["利率上升"] = f"聯邦基金利率 {ff.get('value')}%（{ff.get('date')}）趨勢上升"
    elif ff.get("trend") == "下降":
        signals["利率下降"] = f"聯邦基金利率 {ff.get('value')}%（{ff.get('date')}）趨勢下降"

    cpi = fred_snapshot.get("cpi_yoy") or {}
    if cpi.get("value") is not None:
        val = float(cpi["value"])
        if val >= 3.0:
            signals["CPI高企"] = f"CPI YoY {val:.1f}%（{cpi.get('date')}）"
        elif val <= 2.5 and cpi.get("trend") == "下降":
            signals["CPI回落"] = f"CPI YoY {val:.1f}% 趨勢回落"

    t10 = fred_snapshot.get("treasury_10y") or {}
    if t10.get("trend") == "上升":
        signals["10Y殖利率上升"] = f"10Y 公債 {t10.get('value')}% 趨勢上升"

    if len(tsm_rev) >= 2:
        latest = tsm_rev[-1]
        yoy = latest.get("yoy_pct")
        mom = latest.get("mom_pct")
        if yoy is not None and float(yoy) > 0:
            if mom is not None and float(mom) > 0:
                signals["TSM營收加速"] = (
                    f"TSM {latest.get('month')} 月營收 YoY {float(yoy):+.1f}%、MoM {float(mom):+.1f}%"
                )
            else:
                signals["TSM營收加速"] = f"TSM {latest.get('month')} 月營收 YoY {float(yoy):+.1f}%"
        elif yoy is not None and float(yoy) < 0:
            signals["TSM營收放緩"] = f"TSM {latest.get('month')} 月營收 YoY {float(yoy):+.1f}%"

    if len(sia_sales) >= 3:
        last3 = sia_sales[-3:]
        yoys = [r["yoy_pct"] for r in last3 if r.get("yoy_pct") is not None]
        if len(yoys) == 3:
            if all(float(y) > 0 for y in yoys) and float(yoys[-1]) > float(yoys[0]):
                signals["半導體銷售YoY上升"] = (
                    f"SIA 銷售 YoY 連3月為正（最新 {float(yoys[-1]):+.1f}%）"
                )
            elif all(float(y) < 0 for y in yoys):
                signals["半導體銷售YoY下降"] = (
                    f"SIA 銷售 YoY 連3月為負（最新 {float(yoys[-1]):+.1f}%）"
                )
        latest_yoy = sia_sales[-1].get("yoy_pct")
        if latest_yoy is not None and float(latest_yoy) >= 5.0:
            signals.setdefault(
                "半導體銷售YoY上升",
                f"SIA 最新月 YoY {float(latest_yoy):+.1f}%",
            )

    if asml_bookings and asml_bookings.get("trend") == "上升":
        signals["ASML bookings上升"] = (
            f"ASML {asml_bookings.get('quarter')} bookings "
            f"{asml_bookings.get('bookings_eur_b')}B EUR（人工維護 as_of {asml_bookings.get('as_of')}）"
        )

    return signals


def _score_theme(
    theme: str,
    signals: dict[str, str],
) -> tuple[BiasLabel, list[str]] | None:
    drivers_cfg = THEME_DRIVERS.get(theme)
    if not drivers_cfg:
        return None
    tail_hits: list[str] = []
    head_hits: list[str] = []
    for key in drivers_cfg.get("tailwind", []):
        if key in signals:
            tail_hits.append(signals[key])
    for key in drivers_cfg.get("headwind", []):
        if key in signals:
            head_hits.append(signals[key])
    if not tail_hits and not head_hits:
        return None
    net = len(tail_hits) - len(head_hits)
    if net > 0:
        bias: BiasLabel = "順風"
    elif net < 0:
        bias = "逆風"
    else:
        bias = "中性"
    drivers_zh = tail_hits + head_hits
    return bias, drivers_zh


def build_macro_context(
    *,
    fred_snapshot: dict[str, Any] | None = None,
    tsm_rev: list[dict[str, Any]] | None = None,
    sia_sales: list[dict[str, Any]] | None = None,
    asml_bookings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build macro + supply_chain + theme_bias snapshot."""
    fred_snapshot = fred_snapshot or {}
    tsm_rev = tsm_rev or []
    sia_sales = sia_sales or []

    macro_summary: dict[str, Any] = {}
    for key in ("fed_funds_rate", "cpi_yoy", "treasury_10y", "real_gdp"):
        if fred_snapshot.get(key):
            macro_summary[key] = fred_snapshot[key]

    tsm_block: dict[str, Any] = {}
    if tsm_rev:
        latest = tsm_rev[-1]
        tsm_block = {
            "latest_month": latest.get("month"),
            "yoy_pct": latest.get("yoy_pct"),
            "mom_pct": latest.get("mom_pct"),
            "trend": "加速"
            if latest.get("yoy_pct") is not None and float(latest["yoy_pct"]) > 0
            and latest.get("mom_pct") is not None
            and float(latest["mom_pct"]) > 0
            else "放緩"
            if latest.get("yoy_pct") is not None and float(latest["yoy_pct"]) < 0
            else "持平",
            "source": latest.get("source"),
        }

    sia_block: dict[str, Any] = {}
    if sia_sales:
        latest = sia_sales[-1]
        sia_block = {
            "latest_month": latest.get("month"),
            "yoy_pct": latest.get("yoy_pct"),
            "sales_usd_b": latest.get("sales_usd_b"),
            "trend": "上升"
            if latest.get("yoy_pct") is not None and float(latest["yoy_pct"]) > 0
            else "下降"
            if latest.get("yoy_pct") is not None and float(latest["yoy_pct"]) < 0
            else "持平",
            "source": latest.get("source", "manual"),
            "as_of": latest.get("as_of"),
        }

    signals = _active_signals(
        fred_snapshot=fred_snapshot,
        tsm_rev=tsm_rev,
        sia_sales=sia_sales,
        asml_bookings=asml_bookings,
    )

    theme_bias: dict[str, Any] = {}
    for theme in THEME_DRIVERS:
        scored = _score_theme(theme, signals)
        if scored:
            bias, drivers_zh = scored
            theme_bias[theme] = {"bias": bias, "drivers_zh": drivers_zh}

    return {
        "macro": macro_summary,
        "supply_chain": {
            "tsm": tsm_block,
            "sia": sia_block,
            "asml": asml_bookings,
        },
        "theme_bias": theme_bias,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def fetch_macro_context() -> dict[str, Any]:
    """Fetch all sources and build context; never raises."""
    try:
        fred = MacroFred()
        sc = SupplyChain()
        return build_macro_context(
            fred_snapshot=fred.snapshot(),
            tsm_rev=sc.tsm_monthly_revenue(),
            sia_sales=sc.sia_semiconductor_sales(),
            asml_bookings=sc.asml_bookings(),
        )
    except Exception:
        logger.warning("fetch_macro_context failed", exc_info=True)
        return build_macro_context()
