"""Fallback IR page scraper for companies not well-covered by SEC EDGAR RSS."""

import logging
import re

import io

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

IR_PAGES: dict[str, str] = {
    "apple": "https://investor.apple.com/sec-filings/annual-reports/default.aspx",
    "microsoft": "https://www.microsoft.com/en-us/investor/sec-filings.aspx",
    "google": "https://abc.xyz/investor/",
    "meta": "https://investor.fb.com/financials/sec-filings/default.aspx",
    "amazon": "https://ir.aboutamazon.com/sec-filings/default.aspx",
    "nvidia": "https://investor.nvidia.com/financial-info/sec-filings/default.aspx",
}


class IRDocument(BaseModel):
    company: str
    document_url: str
    raw_text: str = ""
    source: str = "IR page"


class IRScraper:
    """Scrapes investor-relations pages as a fallback when SEC EDGAR is stale."""

    def __init__(self):
        self._headers = {
            "User-Agent": "tech-pulse/0.1 research@example.com",
            "Accept": "text/html,application/pdf",
        }

    def fetch(self, company_key: str) -> IRDocument | None:
        url = IR_PAGES.get(company_key.lower())
        if not url:
            logger.warning("No IR page registered for %s", company_key)
            return None

        try:
            with httpx.Client(timeout=20, headers=self._headers, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")

                if "pdf" in content_type:
                    text = self._extract_pdf(resp.content)
                else:
                    text = self._extract_html(resp.text)

            return IRDocument(company=company_key, document_url=url, raw_text=text[:15000])

        except Exception as exc:
            logger.warning("IR scrape failed for %s: %s", company_key, exc)
            return None

    def _extract_pdf(self, content: bytes) -> str:
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages[:20]:
                parts.append(page.extract_text() or "")
        return "\n".join(parts)

    def _extract_html(self, html: str) -> str:
        html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s{2,}", " ", html).strip()
