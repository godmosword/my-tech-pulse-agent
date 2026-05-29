"""Fetch latest SEC 10-K primary document text for a ticker."""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

import httpx

from sources.earnings_fetcher import EarningsFetcher, SEC_HEADERS
from sources.sec_submissions import SecSubmissionsClient

logger = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 400_000


def _strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s{2,}", " ", html).strip()


def download_filing_text(url: str, *, max_chars: int = _MAX_TEXT_CHARS) -> str:
    try:
        with httpx.Client(timeout=60, headers=SEC_HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "pdf" in content_type:
                fetcher = EarningsFetcher()
                text = fetcher._extract_pdf_text(resp.content)  # noqa: SLF001
            else:
                text = _strip_html(resp.text)
        return text[:max_chars]
    except Exception as exc:
        logger.warning("download_filing_text failed %s: %s", url[:80], exc)
        return ""


def fetch_latest_10k(
    *,
    ticker: str,
    company: str,
    cik: str,
    submissions: SecSubmissionsClient,
    years_back: int = 3,
) -> tuple[str, dict]:
    """Return (raw_text, metadata) for the newest 10-K/A or 10-K filing."""
    until = date.today()
    since = until - timedelta(days=365 * years_back)
    forms = frozenset({"10-K", "10-K/A"})
    filings = submissions.list_filings_in_range(
        ticker=ticker,
        company=company,
        cik=cik,
        since=since,
        until=until,
        forms=forms,
    )
    ten_k = [f for f in filings if f.form_type.startswith("10-K")]
    if not ten_k:
        return "", {}

    latest = ten_k[-1]
    filing = submissions.to_earnings_filing(latest)
    text = download_filing_text(filing.filing_url)
    fiscal_year = None
    if latest.report_date and len(latest.report_date) >= 4:
        try:
            fiscal_year = int(latest.report_date[:4])
        except ValueError:
            fiscal_year = None
    meta = {
        "form_type": latest.form_type,
        "filed": latest.filed_at.date().isoformat(),
        "fiscal_year": fiscal_year,
        "accession": latest.accession,
        "filing_url": filing.filing_url,
    }
    return text, meta
