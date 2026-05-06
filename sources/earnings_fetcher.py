"""SEC EDGAR RSS + IR page PDF parser for earnings filings."""

import io
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import httpx
import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent / "source_registry.yaml"
SEC_HEADERS = {
    "User-Agent": "tech-pulse/0.1 research@example.com",
    "Accept-Encoding": "gzip, deflate",
}


class EarningsFiling(BaseModel):
    company: str
    ticker: Optional[str] = None
    form_type: str                   # "8-K", "10-Q", "10-K"
    filed_at: Optional[datetime] = None
    filing_url: str
    raw_text: str = ""               # extracted text, pre-LLM
    source: str                      # "SEC 10-Q" | "SEC 8-K" | "IR page"


class EarningsFetcher:
    def __init__(self, registry_path: Path = REGISTRY_PATH):
        self._sources: list[dict] = []
        self._load_registry(registry_path)

    def _load_registry(self, path: Path) -> None:
        with open(path) as f:
            data = yaml.safe_load(f)
        self._sources = [s for s in data["sources"] if s.get("type") == "earnings"]

    def fetch_recent_filings(
        self, form_types: tuple[str, ...] = ("8-K", "10-Q", "10-K")
    ) -> list[EarningsFiling]:
        filings: list[EarningsFiling] = []
        for source in self._sources:
            url = self._inject_rolling_date(source["url"])
            filings.extend(self._fetch_edgar_rss(url, form_types))
        return filings

    def _inject_rolling_date(self, url: str, days_back: int = 7) -> str:
        """Replace or append startdt with a rolling window from today."""
        startdt = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        if "startdt=" in url:
            return re.sub(r"startdt=[^&]*", f"startdt={startdt}", url)
        if "dateRange=custom" in url:
            return f"{url}&startdt={startdt}"
        return url

    def _fetch_edgar_rss(self, url: str, form_types: tuple[str, ...]) -> list[EarningsFiling]:
        try:
            with httpx.Client(timeout=20, headers=SEC_HEADERS, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                text = resp.text

            # SEC occasionally returns HTML/rate-limit bodies; strip BOM / whitespace for XML.
            if text.startswith("\ufeff"):
                text = text.lstrip("\ufeff")
            text = text.strip()
            if not text:
                logger.warning("EDGAR RSS empty response body from %s", url[:120])
                return []

            try:
                root = ET.fromstring(text)
            except ET.ParseError as exc:
                head = text[:220].replace("\n", " ").replace("\r", "")
                logger.warning(
                    "EDGAR RSS XML parse failed (%s) len=%d url=%s head=%r",
                    exc,
                    len(text),
                    url[:160],
                    head,
                )
                return []

            filings = []

            # Handle Atom feeds from EDGAR
            ns = ""
            if "}" in root.tag:
                ns = root.tag.split("}")[0].lstrip("{")
            prefix = f"{{{ns}}}" if ns else ""

            entries = root.findall(f"{prefix}entry") or root.findall(".//item")

            for entry in entries[:40]:
                title_el = entry.find(f"{prefix}title") or entry.find("title")
                link_el = entry.find(f"{prefix}link") or entry.find("link")
                updated_el = entry.find(f"{prefix}updated") or entry.find("pubDate")

                title = (title_el.text or "") if title_el is not None else ""
                link = ""
                if link_el is not None:
                    link = link_el.get("href") or link_el.text or ""

                form_type = self._extract_form_type(title)
                if form_type not in form_types:
                    continue

                filed_at = None
                if updated_el is not None and updated_el.text:
                    filed_at = self._parse_date(updated_el.text)

                filing = EarningsFiling(
                    company=self._extract_company(title),
                    form_type=form_type,
                    filed_at=filed_at,
                    filing_url=link,
                    source=f"SEC {form_type}",
                )
                filings.append(filing)

            logger.info("Fetched %d earnings filings from EDGAR", len(filings))
            return filings

        except Exception as exc:
            logger.warning("EDGAR RSS fetch failed: %s", exc)
            return []

    def enrich_with_text(self, filing: EarningsFiling) -> EarningsFiling:
        """Download and extract raw text from a filing URL (HTML or PDF)."""
        try:
            with httpx.Client(timeout=30, headers=SEC_HEADERS, follow_redirects=True) as client:
                resp = client.get(filing.filing_url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")

                if "pdf" in content_type:
                    text = self._extract_pdf_text(resp.content)
                else:
                    text = self._strip_html(resp.text)

            filing.raw_text = text[:20000]
            return filing

        except Exception as exc:
            logger.warning("Text extraction failed for %s: %s", filing.filing_url, exc)
            return filing

    def _extract_pdf_text(self, content: bytes) -> str:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages[:30]:
                text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)

    def _strip_html(self, html: str) -> str:
        html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s{2,}", " ", html).strip()

    def _extract_form_type(self, title: str) -> str:
        for form in ("10-K", "10-Q", "8-K"):
            if form in title:
                return form
        return "OTHER"

    def _extract_company(self, title: str) -> str:
        match = re.search(r"-\s+(.+?)\s+\(", title)
        if match:
            return match.group(1).strip()
        return title.split("-")[-1].strip() if "-" in title else title

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            pass
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None
