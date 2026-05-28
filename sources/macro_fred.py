"""FRED macro series fetcher (graceful when FRED_API_KEY missing)."""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

import httpx

from sources._cache import cached_call

logger = logging.getLogger(__name__)

FRED_BASE = "https://api.stlouisfed.org/fred"

SERIES = {
    "fed_funds_rate": "FEDFUNDS",
    "cpi_index": "CPIAUCSL",
    "treasury_10y": "DGS10",
    "real_gdp": "GDPC1",
}


def _trend_from_values(values: list[float]) -> str:
    if len(values) < 3:
        return "持平"
    a, b, c = values[-3], values[-2], values[-1]
    if c > b > a:
        return "上升"
    if c < b < a:
        return "下降"
    return "持平"


def _parse_float(raw: Any) -> float | None:
    if raw in (None, ".", ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


class MacroFred:
    BASE = FRED_BASE

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 12.0,
        cache_ttl_sec: int | None = None,
    ):
        self.api_key = (api_key if api_key is not None else os.getenv("FRED_API_KEY", "")).strip()
        self.timeout = timeout
        self.cache_ttl_sec = int(
            cache_ttl_sec if cache_ttl_sec is not None else os.getenv("FRED_CACHE_TTL_SEC", "43200")
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            return None
        q = dict(params or {})
        q["api_key"] = self.api_key
        q.setdefault("file_type", "json")
        url = f"{self.BASE}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=q)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("FRED request failed %s: %s", path, exc)
            return None

    def series_latest(self, series_id: str, *, observations: int = 14) -> list[dict[str, Any]]:
        """Recent {date, value} observations; empty list on failure."""
        if not self.api_key:
            return []

        def _fetch() -> list[dict[str, Any]]:
            data = self._get(
                "/series/observations",
                {
                    "series_id": series_id,
                    "sort_order": "desc",
                    "limit": observations,
                },
            )
            if not isinstance(data, dict):
                return []
            obs = data.get("observations") or []
            out: list[dict[str, Any]] = []
            for row in obs:
                if not isinstance(row, dict):
                    continue
                val = _parse_float(row.get("value"))
                if val is None:
                    continue
                out.append({"date": str(row.get("date") or ""), "value": val})
            out.reverse()
            return out

        cached = cached_call(
            f"fred_{series_id}_{observations}",
            self.cache_ttl_sec,
            _fetch,
        )
        return cached if isinstance(cached, list) else []

    def _metric_block(self, obs: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not obs:
            return None
        values = [float(o["value"]) for o in obs if o.get("value") is not None]
        if not values:
            return None
        latest = obs[-1]
        return {
            "value": latest["value"],
            "date": latest.get("date"),
            "trend": _trend_from_values(values),
        }

    def _cpi_yoy(self) -> dict[str, Any] | None:
        obs = self.series_latest(SERIES["cpi_index"], observations=14)
        if len(obs) < 13:
            return None
        latest = obs[-1]
        prior = obs[-13]
        lv, pv = float(latest["value"]), float(prior["value"])
        if pv == 0:
            return None
        yoy = round(((lv / pv) - 1.0) * 100.0, 2)
        values = [float(o["value"]) for o in obs[-3:]]
        return {
            "value": yoy,
            "date": latest.get("date"),
            "trend": _trend_from_values(values),
            "unit": "pct_yoy",
        }

    def snapshot(self) -> dict[str, Any]:
        """Macro snapshot with trends; empty dict when no API key."""
        if not self.api_key:
            return {}

        def _build() -> dict[str, Any]:
            out: dict[str, Any] = {"as_of": date.today().isoformat()}
            ff = self._metric_block(self.series_latest(SERIES["fed_funds_rate"]))
            if ff:
                out["fed_funds_rate"] = ff
            cpi = self._cpi_yoy()
            if cpi:
                out["cpi_yoy"] = cpi
            t10 = self._metric_block(self.series_latest(SERIES["treasury_10y"]))
            if t10:
                out["treasury_10y"] = t10
            gdp = self._metric_block(self.series_latest(SERIES["real_gdp"], observations=8))
            if gdp:
                out["real_gdp"] = gdp
            return out

        data = cached_call("fred_snapshot", self.cache_ttl_sec, _build)
        return data if isinstance(data, dict) else {}
