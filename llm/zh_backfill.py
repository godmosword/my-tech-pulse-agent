"""Lightweight zh_* extraction for Firestore backfill (Flash, small JSON schema)."""

from __future__ import annotations

import logging
import os
from typing import Optional

from pydantic import BaseModel, Field

from llm.gemini_client import GEMINI_FLASH_MODEL, generate_json, make_client
from llm.localization import derive_zh_title, has_cjk, strip_weak_summary_openers, to_traditional_zh_tw

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a Taiwan tech news editor. "
    "Return exactly one JSON object with Traditional Chinese (繁體中文) reader fields only."
)

_PROMPT = """\
English headline:
{title}

English summary:
{summary}

Key facts (if any):
{facts}

Output JSON fields:
- zh_title: ≤28 characters; name the primary company/product; no hype words; null only if truly no facts
- zh_summary: exactly 2 sentences; each under 60 Chinese characters; cite at least one concrete detail from above
- hook: ≤24 characters; punchy teaser; may be empty string

Write zh_title, zh_summary, and hook in Traditional Chinese only. Do not output English in these fields.
"""


class ZhBackfillResult(BaseModel):
    zh_title: Optional[str] = None
    zh_summary: Optional[str] = None
    hook: str = ""


def _clean_zh_title(raw: str | None) -> str | None:
    t = to_traditional_zh_tw((raw or "").strip().strip("「」\"'“”"))
    if not t or not has_cjk(t):
        return None
    return t[:40].rstrip() if len(t) > 40 else t


def _clean_zh_summary(raw: str | None) -> str | None:
    s = strip_weak_summary_openers(to_traditional_zh_tw((raw or "").strip()))
    if not s or not has_cjk(s) or len(s) < 8:
        return None
    return s


def _clean_hook(raw: str | None) -> str:
    h = to_traditional_zh_tw((raw or "").strip().strip("「」\"'“”。"))
    if not h or not has_cjk(h):
        return ""
    return h[:24].rstrip() if len(h) > 24 else h


def extract_zh_backfill(
    *,
    title: str,
    summary: str,
    what_happened: str = "",
) -> ZhBackfillResult | None:
    """Generate zh_title / zh_summary / hook without the full ArticleSummary payload."""
    title = (title or "").strip()
    summary = (summary or "").strip()
    if not title or not summary:
        return None

    facts = (what_happened or "").strip()[:1200]
    prompt = _PROMPT.format(title=title[:500], summary=summary[:3000], facts=facts or "(none)")

    model = os.getenv("BACKFILL_GEMINI_MODEL", GEMINI_FLASH_MODEL)
    token_budgets = [
        int(os.getenv("BACKFILL_ZH_OUTPUT_TOKENS", "1536")),
        int(os.getenv("BACKFILL_ZH_RETRY_OUTPUT_TOKENS", "2048")),
    ]
    result: ZhBackfillResult | None = None
    last_exc: Exception | None = None
    for attempt, max_output_tokens in enumerate(token_budgets, start=1):
        try:
            data, _raw = generate_json(
                make_client(),
                model=model,
                system_instruction=_SYSTEM,
                prompt=prompt,
                max_output_tokens=max_output_tokens,
                response_schema=ZhBackfillResult,
            )
            result = ZhBackfillResult(**data)
            break
        except Exception as exc:
            last_exc = exc
            if attempt < len(token_budgets):
                logger.info(
                    "zh_backfill retry for '%s' with max_output_tokens=%d (%s)",
                    title[:60],
                    token_budgets[attempt],
                    exc,
                )
    if result is None:
        logger.warning("zh_backfill extract failed for '%s': %s", title[:80], last_exc)
        return None

    zh_title = _clean_zh_title(result.zh_title)
    zh_summary = _clean_zh_summary(result.zh_summary)
    hook = _clean_hook(result.hook)
    if not zh_title:
        for source in (zh_summary, hook):
            if source:
                zh_title = derive_zh_title(source)
                if zh_title:
                    break

    if not zh_title and not zh_summary and not hook:
        return None

    return ZhBackfillResult(zh_title=zh_title, zh_summary=zh_summary, hook=hook)
