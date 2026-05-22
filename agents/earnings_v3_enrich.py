"""Apply earnings_v3 slices B–D to a report."""

from __future__ import annotations

import logging
import os

from agents.conclusion_agent import ConclusionAgent
from agents.earnings_models import EarningsFact, EarningsReport
from agents.financial_health_builder import build_financial_health
from agents.guidance_extractor import extract_guidance_capex
from agents.segment_extractor import extract_segments
from agents.transcript_agent import TranscriptAgent
from agents.earnings_v3_models import TranscriptStatus
from sources.finnhub_provider import FinnhubProvider
from sources.sec_xbrl_fetcher import SecXbrlFetcher

logger = logging.getLogger(__name__)

TRANSCRIPT_TIMEOUT = float(os.getenv("FINNHUB_TRANSCRIPT_TIMEOUT_SEC", "15"))
TRANSCRIPT_MAX_TIER = int(os.getenv("EARNINGS_TRANSCRIPT_MAX_TIER", "2"))


def _quarter_num(fiscal_period: str) -> int | None:
    fp = fiscal_period.upper().strip()
    if fp.startswith("Q") and fp[1:].isdigit():
        return int(fp[1:])
    return None


def _fetch_transcript(
    finnhub: FinnhubProvider,
    report: EarningsReport,
) -> tuple[TranscriptStatus, str, str | None]:
    """Returns (status, text, transcript_id)."""
    q = _quarter_num(report.fiscal_period)
    if report.fiscal_year is None or q is None:
        return "skipped", "", None
    try:
        text, tid = finnhub.fetch_transcript(
            report.ticker,
            year=int(report.fiscal_year),
            quarter=q,
            timeout=TRANSCRIPT_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("Transcript fetch failed %s: %s", report.ticker, exc)
        return "timeout", "", None
    if not text:
        return "timeout", "", tid
    return "ready", text, tid


def enrich_earnings_v3(
    report: EarningsReport,
    *,
    filing_text: str,
    company_facts: dict,
    xbrl: SecXbrlFetcher,
    finnhub: FinnhubProvider | None = None,
    tier: int | None = None,
) -> EarningsReport:
    next_q_consensus = None
    if report.estimates.get("revenue"):
        try:
            next_q_consensus = float(report.estimates["revenue"].get("value"))  # type: ignore[union-attr]
        except (TypeError, ValueError):
            next_q_consensus = None

    guidance_capex = extract_guidance_capex(
        filing_text,
        narrative_guidance=report.guidance,
        next_q_revenue_consensus=next_q_consensus,
    )
    segments = extract_segments(filing_text)
    segment_metrics: list[EarningsFact] = []
    for seg in segments:
        if seg.revenue is not None:
            segment_metrics.append(
                EarningsFact(
                    metric=f"segment_{seg.name_zh[:20].lower().replace(' ', '_')}",
                    label_zh=seg.name_zh,
                    value=seg.revenue,
                    source_type="filing_text",
                    source_tag="segment_extract",
                )
            )

    transcript_status: TranscriptStatus = "skipped"
    call_insights = report.call_insights
    transcript_id = report.transcript_id

    if tier is not None and tier <= TRANSCRIPT_MAX_TIER and finnhub is not None:
        transcript_status, transcript_text, transcript_id = _fetch_transcript(finnhub, report)
        if transcript_status == "ready" and transcript_text:
            call_insights = TranscriptAgent().analyze(transcript_text)
        elif transcript_status == "timeout":
            call_insights = None
    else:
        transcript_status = "skipped"

    financial_health = build_financial_health(
        report,
        company_facts=company_facts,
        xbrl=xbrl,
        filing_text=filing_text,
    )

    return report.model_copy(
        update={
            "guidance_capex": guidance_capex,
            "segments": segments,
            "segment_metrics": segment_metrics or report.segment_metrics,
            "transcript_status": transcript_status,
            "transcript_id": transcript_id,
            "call_insights": call_insights,
            "financial_health": financial_health,
        }
    )


def finalize_conclusion(report: EarningsReport) -> EarningsReport:
    conclusion = ConclusionAgent().build(report)
    return report.model_copy(update={"conclusion": conclusion})
