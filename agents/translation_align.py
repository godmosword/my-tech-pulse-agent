"""Deterministic EN/ZH alignment check (numbers + tickers). No LLM."""

from __future__ import annotations

import re

from agents.extractor_agent import ArticleSummary
from llm.localization import has_cjk

_NUM_RE = re.compile(r"\d+(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+")


def _norm_num(token: str) -> str:
    return token.replace(",", "")


def _numbers(text: str) -> set[str]:
    return {_norm_num(m.group(0)) for m in _NUM_RE.finditer(text or "")}


def translation_is_aligned(summary: ArticleSummary) -> bool:
    """True when usable CJK exists and EN numbers/tickers also appear in ZH."""
    en = " ".join(
        part
        for part in (
            summary.title or "",
            summary.summary or "",
            summary.what_happened or "",
        )
        if part
    )
    zh = " ".join(
        part
        for part in (summary.zh_title or "", summary.zh_summary or "")
        if part
    )
    if not en.strip() or not has_cjk(zh):
        return False
    en_nums = _numbers(en)
    zh_nums = _numbers(zh)
    if en_nums and not en_nums.issubset(zh_nums):
        return False
    zh_upper = zh.upper()
    en_upper = en.upper()
    for raw in summary.tickers or []:
        ticker = str(raw or "").strip().upper()
        if not ticker:
            continue
        if ticker in en_upper and ticker not in zh_upper:
            return False
    return True


def apply_translation_alignment(summaries: list[ArticleSummary]) -> list[ArticleSummary]:
    for summary in summaries:
        summary.translation_aligned = translation_is_aligned(summary)
    return summaries
