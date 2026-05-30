"""Historical signal replay with strict point-in-time fundamentals."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agents.scorecard_builder import apply_scorecard_v3
from backtest.pit_data import (
    first_trading_day_after,
    list_historical_earnings,
    reconstruct_company_facts_asof,
)
from pipeline.earnings_pipeline import build_report_from_filing
from scoring.signal_engine import build_investment_signal
from sources.earnings_fetcher import EarningsFiling
from sources.sec_submissions import SecSubmissionsClient
from sources.sec_xbrl_fetcher import SecXbrlFetcher
from sources.ticker_cik_map import TickerCikMap
from sources.watchlist import EarningsWatchlist

logger = logging.getLogger(__name__)

# Backtest excludes market_confirmation: it uses post-filing prices and would
# circularly leak future information when predicting forward returns.
BACKTEST_EXCLUDE_FACTORS = frozenset({"market_confirmation"})


def rebuild_signal_for_quarter(
    symbol: str,
    cik: str,
    filing: dict[str, Any],
    *,
    finnhub: Any,
    xbrl: SecXbrlFetcher,
    company_facts: dict[str, Any],
    tier: int | None = None,
    company_name: str | None = None,
) -> dict[str, Any] | None:
    """Point-in-time rebuild of investment signal for one historical quarter."""
    filed = str(filing.get("filed") or "")[:10]
    if not filed:
        return None

    pit_facts = reconstruct_company_facts_asof(company_facts, asof_filed_date=filed)

    filed_dt = datetime.strptime(filed, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    ef = EarningsFiling(
        company=company_name or symbol,
        ticker=symbol.upper(),
        form_type=str(filing.get("form") or ""),
        accession=str(filing.get("accession") or ""),
        filed_at=filed_dt,
        filing_url=str(filing.get("filing_url") or ""),
        source=f"SEC {filing.get('form')}",
    )

    report = build_report_from_filing(
        ef,
        ticker=symbol.upper(),
        cik=cik,
        tier=tier,
        company_facts=pit_facts,
        xbrl=xbrl,
    )
    if not report:
        return None

    # No vendor estimates / FMP ratios at point-in-time in v1 → surprise & quality often unavailable.
    report = apply_scorecard_v3(
        report,
        company_facts=pit_facts,
        xbrl=xbrl,
        filing_text="",
        vendor_estimates=None,
        vendor_market=None,
    )
    # Explicitly omit price_reaction — market_confirmation excluded below.
    report = report.model_copy(update={"price_reaction": None, "ratios": None})

    signal = build_investment_signal(
        report,
        exclude_factors=BACKTEST_EXCLUDE_FACTORS,
    )

    decision_date = first_trading_day_after(finnhub, symbol, from_date=filed)
    period = report.quarter_label or filing.get("period_end") or filed

    return {
        "symbol": symbol.upper(),
        "cik": cik,
        "period": period,
        "filed": filed,
        "accession": filing.get("accession"),
        "form": filing.get("form"),
        "decision_date": decision_date,
        "score": signal.score,
        "rating": signal.rating,
        "conviction": signal.conviction,
        "factors_available": sum(1 for f in signal.factors if f.available),
    }


def replay_universe(
    *,
    tickers: list[str],
    since: str,
    finnhub: Any,
    xbrl: SecXbrlFetcher,
    cik_map: TickerCikMap | None = None,
    watchlist: EarningsWatchlist | None = None,
    submissions: SecSubmissionsClient | None = None,
) -> list[dict[str, Any]]:
    """Replay historical signals for all (ticker × quarter) in the watchlist subset."""
    cik_map = cik_map or TickerCikMap.load()
    watchlist = watchlist or EarningsWatchlist.load()
    submissions = submissions or SecSubmissionsClient()
    records: list[dict[str, Any]] = []

    for ticker in tickers:
        sym = ticker.upper()
        cik = cik_map.cik_for(sym)
        if not cik:
            logger.warning("Skip %s: no CIK", sym)
            continue
        try:
            company_facts = xbrl.get_company_facts(cik)
        except Exception:
            logger.warning("XBRL fetch failed for %s", sym, exc_info=True)
            continue

        filings = list_historical_earnings(cik, since=since, submissions=submissions)
        tier = watchlist.tier(sym)
        for filing in filings:
            try:
                row = rebuild_signal_for_quarter(
                    sym,
                    cik,
                    filing,
                    finnhub=finnhub,
                    xbrl=xbrl,
                    company_facts=company_facts,
                    tier=tier,
                )
            except Exception:
                logger.warning(
                    "Replay failed %s %s",
                    sym,
                    filing.get("accession"),
                    exc_info=True,
                )
                continue
            if row and row.get("decision_date") and row.get("score") is not None:
                records.append(row)
    return records
