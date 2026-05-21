"""Earnings sub-pipeline: RSS trigger → XBRL facts → report store → legacy Telegram output."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from agents.earnings_agent import EarningsAgent, EarningsOutput
from agents.earnings_models import (
    EarningsFact,
    EarningsReport,
    SourceDocument,
    build_report_id,
    quarter_label_zh,
    report_to_legacy_output,
)
from scoring.earnings_report_store import EarningsReportStore
from sources.earnings_fetcher import EarningsFetcher, EarningsFiling
from sources.sec_xbrl_fetcher import SecXbrlFetcher
from sources.ticker_cik_map import TickerCikMap
from sources.watchlist import EarningsWatchlist

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

MAX_EARNINGS_FILINGS = int(os.getenv("MAX_EARNINGS_FILINGS", "8"))
MAX_EARNINGS_FILINGS_BROAD = int(os.getenv("MAX_EARNINGS_FILINGS_BROAD", "30"))
MAX_SEC_API_CALLS_PER_RUN = int(os.getenv("MAX_SEC_API_CALLS_PER_RUN", "60"))
EARNINGS_TELEGRAM_MIN_TIER = int(os.getenv("EARNINGS_TELEGRAM_MIN_TIER", "2"))


def _published_at_from_filing(filing: EarningsFiling, period_filed: datetime | None) -> datetime:
    if filing.filed_at:
        return filing.filed_at if filing.filed_at.tzinfo else filing.filed_at.replace(tzinfo=timezone.utc)
    if period_filed:
        return period_filed
    return datetime.now(timezone.utc)


def build_report_from_filing(
    filing: EarningsFiling,
    *,
    ticker: str,
    cik: str,
    tier: int | None,
    company_facts: dict,
    xbrl: SecXbrlFetcher,
) -> EarningsReport | None:
    normalized = xbrl.normalize_quarter_facts(company_facts, accession=filing.accession)
    if not normalized:
        return None

    period_meta, _rows = normalized
    fact_dicts = xbrl.build_facts_from_xbrl(
        company_facts, source_url=filing.filing_url, accession=filing.accession
    )
    if not fact_dicts:
        return None

    headline = [EarningsFact(**f) for f in fact_dicts]
    fy = period_meta.get("fiscal_year")
    fp = str(period_meta.get("fiscal_period") or "")
    period_end = period_meta.get("period_end")
    period_end_dt = None
    if period_end:
        try:
            period_end_dt = datetime.strptime(str(period_end)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            period_end_dt = None

    filed_at = period_meta.get("filed_at") or filing.filed_at
    published_at = _published_at_from_filing(filing, period_meta.get("filed_at"))

    report_id = build_report_id(ticker, int(fy) if fy is not None else None, fp)
    confidence: str = "high" if headline else "low"

    return EarningsReport(
        report_id=report_id,
        ticker=ticker.upper(),
        company=filing.company or ticker,
        cik=cik,
        tier=tier,
        fiscal_year=int(fy) if fy is not None else None,
        fiscal_period=fp,
        period_end=period_end_dt,
        quarter_label=quarter_label_zh(int(fy) if fy is not None else None, fp, str(period_end) if period_end else None),
        published_at=published_at,
        filed_at=filed_at,
        headline_metrics=headline,
        source_documents=[
            SourceDocument(
                form_type=filing.form_type,
                filing_url=filing.filing_url,
                filed_at=filed_at,
            )
        ],
        confidence=confidence,  # type: ignore[arg-type]
    )


class EarningsPipelineRunner:
    def __init__(
        self,
        *,
        fetcher: EarningsFetcher,
        xbrl: SecXbrlFetcher,
        agent: EarningsAgent,
        store: EarningsReportStore,
        watchlist: EarningsWatchlist,
        cik_map: TickerCikMap,
    ):
        self.fetcher = fetcher
        self.xbrl = xbrl
        self.agent = agent
        self.store = store
        self.watchlist = watchlist
        self.cik_map = cik_map

    def run(self) -> tuple[list[EarningsReport], list[EarningsOutput]]:
        filings = self.fetcher.fetch_recent_filings()
        filings = sorted(
            filings,
            key=lambda f: self.watchlist.sort_key(
                f.ticker or self.cik_map.resolve_ticker(f.company, f.form_type)
            ),
        )

        reports: list[EarningsReport] = []
        legacy_outputs: list[EarningsOutput] = []
        sec_calls = 0
        full_count = 0
        broad_count = 0

        for filing in filings:
            if sec_calls >= MAX_SEC_API_CALLS_PER_RUN:
                logger.warning("SEC API cap reached (%d)", MAX_SEC_API_CALLS_PER_RUN)
                break

            ticker = filing.ticker or self.cik_map.resolve_ticker(filing.company, filing.form_type)
            if not ticker:
                logger.debug("Skip filing without ticker: %s", filing.company)
                continue

            cik = filing.cik or self.cik_map.cik_for(ticker)
            if not cik:
                logger.warning("No CIK for ticker %s (%s)", ticker, filing.company)
                continue

            tier = self.watchlist.tier(ticker)
            on_watchlist = tier is not None

            try:
                company_facts = self.xbrl.get_company_facts(cik)
                sec_calls += 1
            except Exception as exc:
                logger.warning("XBRL fetch failed for %s: %s", ticker, exc)
                continue

            report = build_report_from_filing(
                filing,
                ticker=ticker,
                cik=cik,
                tier=tier,
                company_facts=company_facts,
                xbrl=self.xbrl,
            )
            if not report:
                continue

            if on_watchlist and full_count < MAX_EARNINGS_FILINGS:
                filing = self.fetcher.enrich_with_text(filing)
                llm_out = self.agent.extract(filing)
                if llm_out:
                    report.key_quotes = llm_out.key_quotes
                    if llm_out.revenue.estimate is not None or llm_out.eps.estimate is not None:
                        report.estimates = {
                            "revenue": llm_out.revenue.model_dump(),
                            "eps": llm_out.eps.model_dump(),
                        }
                self.store.save(report)
                reports.append(report)
                legacy = report_to_legacy_output(report)
                if tier is not None and tier <= EARNINGS_TELEGRAM_MIN_TIER:
                    legacy_outputs.append(legacy)
                full_count += 1
            elif not on_watchlist and broad_count < MAX_EARNINGS_FILINGS_BROAD:
                self.store.save(report)
                reports.append(report)
                broad_count += 1

        logger.info(
            "Earnings pipeline: reports=%d telegram=%d full=%d broad=%d sec_calls=%d",
            len(reports),
            len(legacy_outputs),
            full_count,
            broad_count,
            sec_calls,
        )
        return reports, legacy_outputs
