"""Canonical search-token generation for the dashboard keyword search.

This module is the single source of truth for how `search_tokens` are derived
from a memory item. The exact same algorithm is mirrored in the dashboard at
``dashboard/lib/search-tokens.ts`` — the write side (here / the backfill script)
and the read side (the search API query) MUST agree token-for-token, otherwise
queries silently match nothing.

Token rules (stable, deterministic):
- Latin / digit runs are lower-cased and split on non-alphanumerics; runs of
  length >= 2 are kept (single characters are dropped as noise).
- CJK runs are turned into character bigrams (e.g. "輝達財報" ->
  輝達 / 達財 / 財報) so that any 2-character substring of a headline matches.
  A length-1 CJK run is kept as-is.
- Ticker symbols are lower-cased and added verbatim.
- The result is de-duplicated and sorted; identity tokens (title / zh_title /
  entity / hook / tickers) are always retained, with summary-derived tokens
  filling whatever budget remains up to ``max_tokens``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

# Keep these patterns identical to the TypeScript mirror.
_LATIN_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[一-鿿㐀-䶿]+")

DEFAULT_MAX_TOKENS = 80
# Firestore caps `array-contains-any` at 30 disjuncts.
QUERY_TOKEN_LIMIT = 30


def _tokens_from_text(text: str | None) -> set[str]:
    """Return the canonical token set for a single text field."""
    if not text:
        return set()
    out: set[str] = set()
    for match in _LATIN_RE.findall(text.lower()):
        if len(match) >= 2:
            out.add(match)
    for run in _CJK_RE.findall(text):
        if len(run) == 1:
            out.add(run)
            continue
        for i in range(len(run) - 1):
            out.add(run[i : i + 2])
    return out


def _ticker_tokens(tickers: Iterable[Any]) -> set[str]:
    out: set[str] = set()
    for ticker in tickers or []:
        cleaned = str(ticker).strip().lower()
        if cleaned:
            out.add(cleaned)
    return out


def build_search_tokens(
    *,
    core_texts: Iterable[str | None],
    extra_texts: Iterable[str | None] = (),
    tickers: Iterable[Any] = (),
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[str]:
    """Build a bounded, deterministic token list for a memory item.

    Core tokens (identity fields) are always kept; extra tokens (longer prose
    such as the summary) only fill the remaining budget, so a headline's words
    are never evicted by a verbose summary.
    """
    core: set[str] = set(_ticker_tokens(tickers))
    for text in core_texts:
        core |= _tokens_from_text(text)

    extra: set[str] = set()
    for text in extra_texts:
        extra |= _tokens_from_text(text)
    extra -= core

    result = sorted(core)[:max_tokens]
    remaining = max_tokens - len(result)
    if remaining > 0 and extra:
        result.extend(sorted(extra)[:remaining])
    return result


def search_tokens_for_payload(
    payload: Mapping[str, Any],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[str]:
    """Derive ``search_tokens`` from a memory-item Firestore payload."""
    return build_search_tokens(
        core_texts=[
            payload.get("title"),
            payload.get("zh_title"),
            payload.get("entity"),
            payload.get("hook"),
        ],
        extra_texts=[payload.get("zh_summary")],
        tickers=payload.get("tickers") or [],
        max_tokens=max_tokens,
    )


def tokenize_query(query: str, *, limit: int = QUERY_TOKEN_LIMIT) -> list[str]:
    """Tokenize a raw user query the same way item tokens are built."""
    return sorted(_tokens_from_text((query or "").strip()))[:limit]
