"""Ticker ↔ CIK resolution (SEC company_tickers.json + watchlist overrides)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sources.sec_client import SEC_TICKERS_URL, SecClient, sec_headers
from sources.watchlist import EarningsWatchlist

logger = logging.getLogger(__name__)

# Fallback CIKs for watchlist when SEC bulk file is unavailable (tests / offline).
_BUILTIN_CIK: dict[str, str] = {
    "NVDA": "0001045810",
    "TSM": "0001046179",
    "AVGO": "0001730168",
    "AMD": "0000002488",
    "ASML": "0000937966",
    "AMAT": "0000006951",
    "LRCX": "0000707549",
    "KLAC": "0000319201",
    "MRVL": "0001059524",
    "MU": "0000072333",
    "CDNS": "0000813672",
    "SNPS": "0000883241",
    "ARM": "0001973239",
    "ON": "0001097864",
    "WOLF": "0001039565",
    "TXN": "0000097476",
    "ADI": "0000006281",
    "SMCI": "0001375365",
    "RMBS": "0000917273",
    "ACLS": "0001113232",
    "AMKR": "0001047127",
    "ASX": "0001122930",
    "ENTG": "0001101302",
    "NVTS": "0001821769",
}


def format_cik(cik: int | str) -> str:
    raw = str(cik).strip().lstrip("0") or "0"
    return raw.zfill(10)


def cik_int(cik: str) -> int:
    return int(str(cik).lstrip("0") or "0")


class TickerCikMap:
    def __init__(self, ticker_to_cik: dict[str, str], cik_to_ticker: dict[str, str]):
        self._ticker_to_cik = {k.upper(): format_cik(v) for k, v in ticker_to_cik.items()}
        self._cik_to_ticker = {format_cik(k): v.upper() for k, v in cik_to_ticker.items()}

    @classmethod
    def from_builtin(cls) -> TickerCikMap:
        t2c = dict(_BUILTIN_CIK)
        c2t = {format_cik(v): k for k, v in _BUILTIN_CIK.items()}
        return cls(t2c, c2t)

    @classmethod
    def load(cls, *, client: SecClient | None = None, watchlist: EarningsWatchlist | None = None) -> TickerCikMap:
        if os.getenv("SEC_TICKER_MAP_OFFLINE", "").strip().lower() in {"1", "true", "yes"}:
            return cls.from_builtin()

        ticker_to_cik = dict(_BUILTIN_CIK)
        try:
            client = client or SecClient()
            payload = client.get_json(SEC_TICKERS_URL)
            if isinstance(payload, dict):
                for row in payload.values():
                    if not isinstance(row, dict):
                        continue
                    ticker = str(row.get("ticker", "")).strip().upper()
                    cik = row.get("cik_str") or row.get("cik")
                    if ticker and cik is not None:
                        ticker_to_cik[ticker] = format_cik(cik)
        except Exception as exc:
            logger.warning("SEC company_tickers.json unavailable, using builtin map: %s", exc)

        if watchlist:
            for ticker in watchlist.tickers():
                ticker_to_cik.setdefault(ticker, _BUILTIN_CIK.get(ticker, ""))

        ticker_to_cik = {k: v for k, v in ticker_to_cik.items() if v}
        cik_to_ticker = {}
        for ticker, cik in ticker_to_cik.items():
            cik_to_ticker.setdefault(cik, ticker)
        return cls(ticker_to_cik, cik_to_ticker)

    def cik_for(self, ticker: str | None) -> str | None:
        if not ticker:
            return None
        cik = self._ticker_to_cik.get(ticker.upper())
        return format_cik(cik) if cik else None

    def ticker_for(self, cik: str | None) -> str | None:
        if not cik:
            return None
        return self._cik_to_ticker.get(format_cik(cik))

    def resolve_ticker(self, company: str, title: str = "") -> str | None:
        """Best-effort ticker from EDGAR title / company name."""
        blob = f"{company} {title}".upper()
        for ticker in sorted(self._ticker_to_cik.keys(), key=len, reverse=True):
            if f"({ticker})" in blob or f" {ticker} " in f" {blob} ":
                return ticker
        # "NVIDIA CORP" → NVDA via builtin aliases
        aliases = {
            "NVIDIA": "NVDA",
            "ADVANCED MICRO": "AMD",
            "BROADCOM": "AVGO",
            "TAIWAN SEMICONDUCTOR": "TSM",
            "MICRON": "MU",
            "MARVELL": "MRVL",
            "LAM RESEARCH": "LRCX",
            "KLA": "KLAC",
            "APPLIED MATERIALS": "AMAT",
            "SYNOPSYS": "SNPS",
            "CADENCE": "CDNS",
            "SUPER MICRO": "SMCI",
        }
        upper = company.upper()
        for needle, ticker in aliases.items():
            if needle in upper:
                return ticker
        return None
