"""SEC company submissions API — list filings in a date range."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from sources.earnings_fetcher import EarningsFiling
from sources.sec_client import SEC_BASE, SecClient
from sources.ticker_cik_map import cik_int, format_cik

logger = logging.getLogger(__name__)

EARNINGS_FORMS = frozenset({"8-K", "10-Q", "10-K", "8-K/A", "10-Q/A", "10-K/A"})


def _is_earnings_form(form: str, allowed: frozenset[str]) -> bool:
    form = form.strip().upper()
    if form in allowed:
        return True
    for base in ("8-K", "10-Q", "10-K"):
        if form.startswith(base):
            return True
    return False


@dataclass(frozen=True)
class SubmissionFiling:
    ticker: str
    company: str
    cik: str
    form_type: str
    filed_at: datetime
    accession: str
    primary_document: str
    report_date: str | None = None


def _parse_filing_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _accession_folder(accession: str) -> str:
    return re.sub(r"[^0-9]", "", accession)


def filing_archive_url(cik: str, accession: str, primary_document: str) -> str:
    """Canonical SEC Archives URL for a primary document."""
    cik_num = cik_int(cik)
    folder = _accession_folder(accession)
    doc = primary_document or f"{accession}.txt"
    return f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{folder}/{doc}"


class SecSubmissionsClient:
    def __init__(self, client: SecClient | None = None):
        self._client = client or SecClient()

    def get_submissions(self, cik: str) -> dict:
        cik_padded = format_cik(cik)
        url = f"{SEC_BASE}/submissions/CIK{cik_padded}.json"
        data = self._client.get_json(url)
        return data if isinstance(data, dict) else {}

    def iter_recent_filings(self, submissions: dict) -> Iterable[dict]:
        recent = submissions.get("filings", {}).get("recent") or {}
        forms = recent.get("form") or []
        n = len(forms)
        keys = (
            "accessionNumber",
            "filingDate",
            "reportDate",
            "primaryDocument",
            "primaryDocDescription",
        )
        columns = {k: recent.get(k) or [] for k in keys}
        for i in range(n):
            row = {k: (columns[k][i] if i < len(columns[k]) else None) for k in keys}
            row["form"] = forms[i] if i < len(forms) else None
            yield row

    def list_filings_in_range(
        self,
        *,
        ticker: str,
        company: str,
        cik: str,
        since: date,
        until: date,
        forms: frozenset[str] = EARNINGS_FORMS,
    ) -> list[SubmissionFiling]:
        submissions = self.get_submissions(cik)
        out: list[SubmissionFiling] = []
        for row in self.iter_recent_filings(submissions):
            form = str(row.get("form") or "").strip().upper()
            if not _is_earnings_form(form, forms):
                continue
            filed = _parse_filing_date(str(row.get("filingDate") or ""))
            if not filed:
                continue
            filed_day = filed.date()
            if filed_day < since or filed_day > until:
                continue
            accession = str(row.get("accessionNumber") or "").strip()
            if not accession:
                continue
            primary = str(row.get("primaryDocument") or "").strip()
            out.append(
                SubmissionFiling(
                    ticker=ticker.upper(),
                    company=company or ticker,
                    cik=format_cik(cik),
                    form_type=form,
                    filed_at=filed,
                    accession=accession,
                    primary_document=primary,
                    report_date=str(row.get("reportDate") or "") or None,
                )
            )
        out.sort(key=lambda f: f.filed_at)
        return out

    def to_earnings_filing(self, sub: SubmissionFiling) -> EarningsFiling:
        url = filing_archive_url(sub.cik, sub.accession, sub.primary_document)
        return EarningsFiling(
            company=sub.company,
            ticker=sub.ticker,
            cik=sub.cik,
            form_type=sub.form_type,
            accession=sub.accession,
            filed_at=sub.filed_at,
            filing_url=url,
            source=f"SEC {sub.form_type}",
        )
