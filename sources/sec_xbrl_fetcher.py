"""SEC XBRL company facts → normalized quarterly earnings facts."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
import re
from typing import Any

from sources.earnings_fetcher import EarningsFiling
from sources.sec_client import SEC_BASE, SecClient
from sources.sec_concept_map import HEADLINE_CONCEPTS, QUARTERLY_FP, ConceptSpec
from sources.ticker_cik_map import format_cik

logger = logging.getLogger(__name__)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None



def _accession_digits(accession: str | None) -> str:
    if not accession:
        return ""
    return re.sub(r"[^0-9]", "", accession)


def _pick_quarterly_for_accession(entries: list[dict], accession: str | None) -> dict | None:
    """Pick quarterly row matching SEC accession when possible."""
    key = _accession_digits(accession)
    if not key:
        return _pick_latest_quarterly(entries)
    candidates = [
        e for e in entries
        if str(e.get("fp", "")).upper() in QUARTERLY_FP
        and e.get("val") is not None
        and _accession_digits(str(e.get("accn") or "")) == key
    ]
    if candidates:
        return max(candidates, key=lambda e: (str(e.get("filed") or ""), str(e.get("end") or "")))
    return _pick_latest_quarterly(entries)


def _pick_latest_quarterly(entries: list[dict]) -> dict | None:
    """Prefer quarterly fp with latest filed date."""
    candidates = [
        e for e in entries
        if str(e.get("fp", "")).upper() in QUARTERLY_FP and e.get("val") is not None
    ]
    if not candidates:
        return None

    def sort_key(e: dict) -> tuple[str, str]:
        filed = str(e.get("filed") or "")
        end = str(e.get("end") or "")
        return (filed, end)

    return max(candidates, key=sort_key)


class SecXbrlFetcher:
    def __init__(self, client: SecClient | None = None):
        self._client = client or SecClient()

    def get_company_facts(self, cik: str) -> dict:
        cik_padded = format_cik(cik)
        url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik_padded}.json"
        data = self._client.get_json(url)
        return data if isinstance(data, dict) else {}

    def extract_concept_entries(self, company_facts: dict, spec: ConceptSpec) -> list[dict]:
        facts = company_facts.get("facts") or {}
        taxonomy = facts.get(spec.taxonomy) or {}
        for tag in spec.tags:
            node = taxonomy.get(tag)
            if not isinstance(node, dict):
                continue
            units = node.get("units") or {}
            for unit_entries in units.values():
                if isinstance(unit_entries, list):
                    return unit_entries
        return []

    def normalize_quarter_facts(
        self,
        company_facts: dict,
        *,
        accession: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        """
        Return (period_meta, facts_list) for a quarterly period.

        When accession is set (backfill), prefer XBRL rows with matching accn.
        """
        period_rows: dict[tuple[Any, ...], dict[str, dict]] = {}

        for spec in HEADLINE_CONCEPTS:
            entries = self.extract_concept_entries(company_facts, spec)
            row = _pick_quarterly_for_accession(entries, accession)
            if not row:
                continue
            key = (row.get("fy"), row.get("fp"), row.get("end"))
            period_rows.setdefault(key, {})[spec.metric] = {**row, "metric": spec.metric, "label_zh": spec.label_zh}

        if not period_rows:
            return None

        def period_sort_key(item: tuple[tuple, dict]) -> tuple[str, str]:
            _, metrics = item
            any_row = next(iter(metrics.values()))
            return (str(any_row.get("filed") or ""), str(any_row.get("end") or ""))

        _, metrics = max(period_rows.items(), key=period_sort_key)
        anchor = metrics.get("revenue") or metrics.get("eps_diluted") or next(iter(metrics.values()))

        period_meta = {
            "fiscal_year": anchor.get("fy"),
            "fiscal_period": str(anchor.get("fp") or ""),
            "period_end": anchor.get("end"),
            "filed_at": _parse_date(str(anchor.get("filed") or "")),
            "form_type": anchor.get("form"),
            "accession": anchor.get("accn"),
        }
        facts_list = list(metrics.values())
        return period_meta, facts_list

    def normalize_latest_quarter_facts(
        self, company_facts: dict
    ) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        return self.normalize_quarter_facts(company_facts)

    def build_facts_from_xbrl(
        self,
        company_facts: dict,
        *,
        source_url: str = "",
        accession: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized = self.normalize_quarter_facts(company_facts, accession=accession)
        if not normalized:
            return []
        _, rows = normalized
        out: list[dict[str, Any]] = []
        for row in rows:
            val = row.get("val")
            if val is None:
                continue
            out.append({
                "metric": row["metric"],
                "label_zh": row["label_zh"],
                "value": float(val),
                "unit": "USD" if row["metric"] != "eps_diluted" and row["metric"] != "eps_basic" else "USD/share",
                "period": f"FY{row.get('fy')}{row.get('fp')}",
                "fiscal_year": row.get("fy"),
                "fiscal_period": str(row.get("fp") or ""),
                "form_type": row.get("form"),
                "source_type": "sec_xbrl",
                "source_url": source_url,
                "source_tag": f"us-gaap:{row.get('metric')}",
                "confidence": "high",
            })
        return out
