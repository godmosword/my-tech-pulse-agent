"""Extract business relationships from SEC 10-K text via Gemini."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field

from agents.earnings_fact_guard import verify_quote_substring
from agents.relationship_models import CompanyRelationships, RelationshipEdge
from llm.gemini_client import GEMINI_MODEL, generate_json, make_client

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL
MAX_SECTION_CHARS = 28_000

ALIASES_PATH = Path(__file__).resolve().parent.parent / "config" / "company_aliases.yaml"

_SECTION_KEYWORDS = (
    "risk factors",
    "competition",
    "customers",
    "customer concentration",
    "concentration",
    "supplier",
    "foundry",
    "major customers",
    "significant customers",
)

SYSTEM = """\
You extract business relationships from a US SEC 10-K (zh-TW notes ok, names verbatim).
Extract ONLY relationships explicitly stated in the provided text:
- customers (especially named major/concentrated customers)
- suppliers / foundry / manufacturing dependencies
- competitors (named in Competition section)
- partners / strategic alliances explicitly stated
RULES:
- Do NOT infer or use outside knowledge. If the text doesn't name it, don't output it.
- For EACH relationship, include a SHORT verbatim quote (<=25 words) from the text as evidence.
- If a concentration figure is stated (e.g. "Customer A 19% of revenue"), capture it.
- Output JSON only: {edges: [{counterparty_name, relation, quote, concentration_note}]}.
"""


class _EdgeOut(BaseModel):
    counterparty_name: str
    relation: Literal["customer", "supplier", "competitor", "partner"]
    quote: str
    concentration_note: str = ""


class _ExtractOutput(BaseModel):
    edges: list[_EdgeOut] = Field(default_factory=list)


_client = None


def _gemini_client():
    global _client
    if _client is None:
        _client = make_client()
    return _client


def _load_aliases() -> dict[str, Optional[str]]:
    if not ALIASES_PATH.is_file():
        return {}
    with open(ALIASES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    raw = data.get("aliases") or {}
    out: dict[str, Optional[str]] = {}
    for name, ticker in raw.items():
        key = str(name).strip().lower()
        if not key:
            continue
        if ticker is None or str(ticker).strip().lower() in {"", "null", "none"}:
            out[key] = None
        else:
            out[key] = str(ticker).strip().upper()
    return out


def resolve_counterparty_ticker(name: str, aliases: dict[str, Optional[str]] | None = None) -> Optional[str]:
    table = aliases if aliases is not None else _load_aliases()
    key = name.strip().lower()
    if key in table:
        return table[key]
    for alias_key, ticker in table.items():
        if alias_key in key or key in alias_key:
            return ticker
    return None


def _window_around(text: str, idx: int, *, before: int = 2500, after: int = 4500) -> str:
    start = max(0, idx - before)
    end = min(len(text), idx + after)
    return text[start:end]


def select_relationship_sections(tenk_text: str) -> str:
    """Collect paragraphs near relationship-related headings/keywords."""
    if not tenk_text:
        return ""
    lower = tenk_text.lower()
    chunks: list[str] = []
    seen_spans: set[tuple[int, int]] = set()

    for kw in _SECTION_KEYWORDS:
        start = 0
        while True:
            idx = lower.find(kw, start)
            if idx == -1:
                break
            chunk = _window_around(tenk_text, idx)
            span = (idx, idx + len(chunk))
            if not any(abs(span[0] - s[0]) < 800 for s in seen_spans):
                chunks.append(chunk)
                seen_spans.add(span)
            start = idx + len(kw)

    if not chunks:
        return tenk_text[:MAX_SECTION_CHARS]

    combined = "\n\n---\n\n".join(chunks)
    if len(combined) > MAX_SECTION_CHARS:
        return combined[:MAX_SECTION_CHARS]
    return combined


def extract_relationships(
    ticker: str,
    *,
    tenk_text: str,
    fiscal_year: Optional[int] = None,
    filed: Optional[str] = None,
) -> CompanyRelationships:
    """Extract verified business relationships from 10-K text; never raises."""
    sym = ticker.upper().strip()
    empty = CompanyRelationships(ticker=sym, fiscal_year=fiscal_year, filed=filed)

    text = (tenk_text or "").strip()
    if len(text) < 500:
        return empty

    section = select_relationship_sections(text)
    prompt = (
        f"Ticker: {sym}\n"
        f"Form: 10-K excerpt\n\n"
        f"{section}\n\n"
        "Return JSON with edges array."
    )

    try:
        data, _ = generate_json(
            _gemini_client(),
            model=MODEL,
            max_output_tokens=4096,
            system_instruction=SYSTEM,
            prompt=prompt,
            response_schema=_ExtractOutput,
        )
        raw_edges = _ExtractOutput(**data).edges
    except Exception as exc:
        logger.warning("extract_relationships Gemini failed for %s: %s", sym, exc)
        return empty

    aliases = _load_aliases()
    verified_edges: list[RelationshipEdge] = []
    for item in raw_edges:
        quote = item.quote.strip()
        if not verify_quote_substring(quote, text):
            continue
        verified_edges.append(
            RelationshipEdge(
                counterparty_name=item.counterparty_name.strip(),
                counterparty_ticker=resolve_counterparty_ticker(item.counterparty_name, aliases),
                relation=item.relation,
                quote=quote,
                concentration_note=(item.concentration_note or "").strip(),
                verified=True,
            )
        )

    return CompanyRelationships(
        ticker=sym,
        fiscal_year=fiscal_year,
        filed=filed,
        edges=verified_edges,
        as_of=datetime.now(timezone.utc).isoformat(),
    )
