"""Fallback Traditional Chinese fields when the extractor under-produces zh_*."""

from __future__ import annotations

import logging
import os

from agents.extractor_agent import ArticleSummary, ExtractorAgent
from llm.localization import has_cjk
from llm.zh_backfill import ZhBackfillResult, extract_zh_backfill

logger = logging.getLogger(__name__)


def translation_agent_enabled() -> bool:
    raw = os.getenv("TRANSLATION_AGENT_ENABLED", "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def needs_zh_translation(summary: ArticleSummary) -> bool:
    """True when zh_title or zh_summary lacks usable Traditional Chinese."""
    zt = (summary.zh_title or "").strip()
    zs = (summary.zh_summary or "").strip()
    if zt and has_cjk(zt) and zs and has_cjk(zs):
        return False
    title = (summary.title or "").strip()
    body = (summary.summary or "").strip()
    return bool(title and body)


def apply_zh_backfill_to_summary(summary: ArticleSummary, zh: ZhBackfillResult) -> bool:
    """Merge Flash backfill into summary; returns True if any field changed."""
    changed = False
    zs = (summary.zh_summary or "").strip()
    if zh.zh_summary and has_cjk(zh.zh_summary) and (not zs or not has_cjk(zs)):
        summary.zh_summary = zh.zh_summary
        changed = True

    zt = (summary.zh_title or "").strip()
    if zh.zh_title and has_cjk(zh.zh_title) and (not zt or not has_cjk(zt)):
        summary.zh_title = zh.zh_title
        changed = True

    hook = (summary.hook or "").strip()
    if zh.hook and has_cjk(zh.hook) and not hook:
        summary.hook = zh.hook
        changed = True

    if changed:
        ExtractorAgent._normalize_zh_fields(summary)
        ExtractorAgent._enforce_zh_quality(
            summary,
            summary.title or "",
            min_summary_len=4,
            min_body_len=20,
        )
    return changed


class TranslationAgent:
    """Lightweight zh_title / zh_summary backfill using Gemini Flash (see llm/zh_backfill)."""

    def translate_batch(self, summaries: list[ArticleSummary]) -> tuple[list[ArticleSummary], int]:
        if not translation_agent_enabled() or not summaries:
            return summaries, 0

        max_articles = int(
            os.getenv(
                "MAX_TRANSLATION_ARTICLES",
                os.getenv("MAX_EXTRACTION_ARTICLES", "8"),
            )
        )
        filled = 0
        for summary in summaries[:max_articles]:
            if not needs_zh_translation(summary):
                continue
            zh = extract_zh_backfill(
                title=summary.title,
                summary=summary.summary,
                what_happened=summary.what_happened or "",
            )
            if not zh:
                logger.info(
                    "Translation agent: no zh output for '%s'",
                    (summary.title or "")[:80],
                )
                continue
            if apply_zh_backfill_to_summary(summary, zh):
                filled += 1

        if filled:
            logger.info(
                "Translation agent filled zh fields for %d/%d summaries (cap=%d)",
                filled,
                len(summaries),
                max_articles,
            )
        return summaries, filled
