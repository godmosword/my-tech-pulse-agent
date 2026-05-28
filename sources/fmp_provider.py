"""Financial Modeling Prep HTTP client for fundamentals and earnings history."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/api/v3"
FMP_STABLE = "https://financialmodelingprep.com/stable"


class FmpProvider:
    BASE = FMP_BASE
    STABLE = FMP_STABLE

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 10.0,
        on_call: Callable[[], bool] | None = None,
    ):
        self.api_key = api_key.strip()
        self.timeout = timeout
        self._on_call = on_call

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        base: str | None = None,
    ) -> Any:
        if not self.api_key:
            return None
        if self._on_call is not None and not self._on_call():
            return None
        q = dict(params or {})
        q["apikey"] = self.api_key
        root = base or self.BASE
        url = f"{root}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=q)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.warning("FMP request failed %s: %s", path, exc)
            return None

    def _list(self, path: str, *, limit: int = 8) -> list[dict[str, Any]]:
        data = self._get(
            path,
            {"period": "quarter", "limit": limit},
        )
        return data if isinstance(data, list) else []

    def income_statement(self, symbol: str, *, limit: int = 8) -> list[dict[str, Any]]:
        return self._list(f"/income-statement/{symbol.upper()}", limit=limit)

    def balance_sheet(self, symbol: str, *, limit: int = 8) -> list[dict[str, Any]]:
        return self._list(f"/balance-sheet-statement/{symbol.upper()}", limit=limit)

    def cash_flow(self, symbol: str, *, limit: int = 8) -> list[dict[str, Any]]:
        return self._list(f"/cash-flow-statement/{symbol.upper()}", limit=limit)

    def ratios(self, symbol: str, *, limit: int = 8) -> list[dict[str, Any]]:
        return self._list(f"/ratios/{symbol.upper()}", limit=limit)

    def key_metrics(self, symbol: str, *, limit: int = 8) -> list[dict[str, Any]]:
        return self._list(f"/key-metrics/{symbol.upper()}", limit=limit)

    def analyst_estimates(self, symbol: str, *, limit: int = 8) -> list[dict[str, Any]]:
        return self._list(f"/analyst-estimates/{symbol.upper()}", limit=limit)

    def earnings_surprises(self, symbol: str, *, limit: int = 8) -> list[dict[str, Any]]:
        data = self._get(
            f"/earnings-surprises/{symbol.upper()}",
            {"limit": limit},
        )
        return data if isinstance(data, list) else []

    def quote(self, symbol: str) -> Optional[dict[str, Any]]:
        data = self._get(f"/quote/{symbol.upper()}")
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else None
        return data if isinstance(data, dict) else None
