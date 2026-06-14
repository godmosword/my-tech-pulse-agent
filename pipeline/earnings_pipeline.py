"""Earnings sub-pipeline: RSS → XBRL → narrative + analysis → report store → Telegram."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from agents.earnings_analyzer import EarningsAnalyzer
from agents.earnings_fact_guard import apply_fact_guard_v2
from agents.earnings_models import (
    EarningsFact,
    EarningsReport,
    SourceDocument,
    build_report_id,
    quarter_label_zh,
)
from agents.earnings_deep_render import render_deep_report_markdown
from agents.earnings_narrative_extractor import EarningsNarrativeExtractor
from agents.earnings_v3_enrich import enrich_earnings_v3, finalize_conclusion
from agents.scorecard_builder import apply_scorecard_v3
from scoring.earnings_report_store import EarningsReportStore
from sources.earnings_fetcher import EarningsFetcher, EarningsFiling
from sources.sec_xbrl_fetcher import SecXbrlFetcher
from sources.ticker_cik_map import TickerCikMap
from sources.vendor_earnings_provider import VendorEarningsProvider
from sources.watchlist import EarningsWatchlist

logger = logging.getLogger(__name__)

MAX_EARNINGS_FILINGS = int(os.getenv("MAX_EARNINGS_FILINGS", "8"))
MAX_EARNINGS_FILINGS_BROAD = int(os.getenv("MAX_EARNINGS_FILINGS_BROAD", "30"))
MAX_SEC_API_CALLS_PER_RUN = int(os.getenv("MAX_SEC_API_CALLS_PER_RUN", "60"))
EARNINGS_TELEGRAM_MIN_TIER = int(os.getenv("EARNINGS_TELEGRAM_MIN_TIER", "2"))


@dataclass
class EarningsRunStats:
    filings_seen: int = 0
    xbrl_facts_loaded: int = 0
    reports_archived: int = 0
    sec_only_count: int = 0
    vendor_enriched_count: int = 0
    vendor_calls: int = 0
    telegram_candidates: int = 0
    sec_api_calls: int = 0
    full_pipeline_count: int = 0
    broad_archive_count: int = 0



def _try_attach_price_reaction(
    report: EarningsReport,
    finnhub: Any | None,
) -> EarningsReport:
    from agents.price_reaction_builder import build_price_reaction

    try:
        mc = report.market_context
        if finnhub and mc and mc.earnings_date:
            pr = build_price_reaction(
                finnhub,
                report.ticker,
                earnings_date=mc.earnings_date,
                session=mc.session or "unknown",
                headline_verdict=(
                    report.scorecard.headline_verdict if report.scorecard else None
                ),
            )
            return report.model_copy(update={"price_reaction": pr})
    except Exception:
        logger.warning("price_reaction failed for %s", report.ticker, exc_info=True)
    return report


def _try_fundamental_enrich(
    report: EarningsReport,
) -> tuple[EarningsReport, dict | None]:
    from sources.fundamental_provider import (
        FundamentalProvider,
        attach_fmp_fields_to_report,
    )

    fundamentals: dict = {}
    try:
        fundamentals = FundamentalProvider().enrich_for_report(report) or {}
    except Exception:
        logger.warning("FMP enrich failed for %s", report.ticker, exc_info=True)
        fundamentals = {}
    if not fundamentals:
        return report, None
    report = attach_fmp_fields_to_report(report, fundamentals)
    return report, fundamentals


def _try_build_investment_signal(report: EarningsReport) -> EarningsReport:
    from scoring.signal_engine import build_investment_signal

    try:
        signal = build_investment_signal(report)
        return report.model_copy(update={"investment_signal": signal})
    except Exception:
        logger.warning("signal build failed for %s", report.ticker, exc_info=True)
        return report


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

    report = EarningsReport(
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
                accession=filing.accession,
                filed_at=filed_at,
            )
        ],
        confidence=confidence,  # type: ignore[arg-type]
    )
    from agents.trend_builder import build_earnings_trend

    try:
        report.trend = build_earnings_trend(xbrl, company_facts, max_quarters=8)
    except Exception:
        logger.warning("trend build failed for %s", ticker, exc_info=True)
    return report


class EarningsPipelineRunner:
    def __init__(
        self,
        *,
        fetcher: EarningsFetcher,
        xbrl: SecXbrlFetcher,
        narrative: EarningsNarrativeExtractor,
        analyzer: EarningsAnalyzer,
        store: EarningsReportStore,
        watchlist: EarningsWatchlist,
        cik_map: TickerCikMap,
        vendor: VendorEarningsProvider | None = None,
    ):
        self.fetcher = fetcher
        self.xbrl = xbrl
        self.narrative = narrative
        self.analyzer = analyzer
        self.store = store
        self.watchlist = watchlist
        self.cik_map = cik_map
        self.vendor = vendor or VendorEarningsProvider()

    def run(self) -> tuple[list[EarningsReport], list[EarningsReport], EarningsRunStats]:
        filings = self.fetcher.fetch_recent_filings()
        stats = EarningsRunStats(filings_seen=len(filings))
        filings = sorted(
            filings,
            key=lambda f: self.watchlist.sort_key(
                f.ticker or self.cik_map.resolve_ticker(f.company, f.form_type)
            ),
        )

        reports: list[EarningsReport] = []
        telegram_reports: list[EarningsReport] = []
        sec_calls = 0

        for filing in filings:
            if sec_calls >= MAX_SEC_API_CALLS_PER_RUN:
                logger.warning("SEC API cap reached (%d)", MAX_SEC_API_CALLS_PER_RUN)
                break

            ticker = filing.ticker or self.cik_map.resolve_ticker(filing.company, filing.form_type)
            if not ticker:
                logger.debug("Skip filing without ticker: %s", filing.company)
                continue

            cik = self.cik_map.cik_for(ticker)
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

            stats.xbrl_facts_loaded += 1

            if on_watchlist and stats.full_pipeline_count < MAX_EARNINGS_FILINGS:
                filing = self.fetcher.enrich_with_text(filing)
                report = self.narrative.enrich_report(report, filing)
                vendor_result = self.vendor.enrich_for_report(report)
                stats.vendor_calls += vendor_result.calls_made
                if vendor_result.estimates:
                    report = report.model_copy(update={"estimates": vendor_result.estimates})
                if vendor_result.enriched:
                    stats.vendor_enriched_count += 1
                else:
                    stats.sec_only_count += 1

                report = apply_scorecard_v3(
                    report,
                    company_facts=company_facts,
                    xbrl=self.xbrl,
                    filing_text=filing.raw_text or "",
                    vendor_estimates=vendor_result.estimates,
                    vendor_market=vendor_result.market_context,
                )
                report = _try_attach_price_reaction(report, self.vendor.finnhub)
                report, fundamentals = _try_fundamental_enrich(report)
                report = enrich_earnings_v3(
                    report,
                    filing_text=filing.raw_text or "",
                    company_facts=company_facts,
                    xbrl=self.xbrl,
                    finnhub=self.vendor.finnhub,
                    tier=tier,
                    fundamentals=fundamentals,
                )
                report = self.analyzer.analyze(report)
                report = _try_build_investment_signal(report)
                try:
                    from backtest.decision_log import log_live_signal

                    log_live_signal(report, finnhub=self.vendor.finnhub)
                except Exception:
                    logger.warning("decision_log failed for %s", report.ticker, exc_info=True)
                report = finalize_conclusion(report)
                report = report.model_copy(
                    update={"rendered_markdown_zh": render_deep_report_markdown(report)}
                )
                report = apply_fact_guard_v2(report, filing_text=filing.raw_text or "")
                self.store.save(report)
                reports.append(report)
                stats.reports_archived += 1
                stats.full_pipeline_count += 1
                if tier is not None and tier <= EARNINGS_TELEGRAM_MIN_TIER and report.confidence != "low":
                    telegram_reports.append(report)
                    stats.telegram_candidates += 1
            elif not on_watchlist and stats.broad_archive_count < MAX_EARNINGS_FILINGS_BROAD:
                report = apply_scorecard_v3(
                    report,
                    company_facts=company_facts,
                    xbrl=self.xbrl,
                    filing_text="",
                    vendor_estimates=None,
                    vendor_market=None,
                )
                report, fundamentals = _try_fundamental_enrich(report)
                report = enrich_earnings_v3(
                    report,
                    filing_text="",
                    company_facts=company_facts,
                    xbrl=self.xbrl,
                    finnhub=None,
                    tier=None,
                    fundamentals=fundamentals,
                )
                report = _try_build_investment_signal(report)
                try:
                    from backtest.decision_log import log_live_signal

                    log_live_signal(report, finnhub=self.vendor.finnhub)
                except Exception:
                    logger.warning("decision_log failed for %s", report.ticker, exc_info=True)
                report = finalize_conclusion(report)
                report = report.model_copy(
                    update={
                        "transcript_status": "skipped",
                        "rendered_markdown_zh": render_deep_report_markdown(report),
                    }
                )
                report = apply_fact_guard_v2(report, filing_text="")
                self.store.save(report)
                reports.append(report)
                stats.reports_archived += 1
                stats.broad_archive_count += 1
                stats.sec_only_count += 1

        stats.sec_api_calls = sec_calls
        logger.info(
            "Earnings pipeline: reports=%d telegram=%d full=%d broad=%d sec_calls=%d vendor=%d",
            len(reports),
            len(telegram_reports),
            stats.full_pipeline_count,
            stats.broad_archive_count,
            sec_calls,
            stats.vendor_enriched_count,
        )
        return reports, telegram_reports, stats
