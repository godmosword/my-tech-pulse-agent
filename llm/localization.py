"""Localization helpers for LLM outputs."""

from __future__ import annotations

import re
from typing import Any

try:
    from opencc import OpenCC
except Exception:  # pragma: no cover - exercised only when optional dependency is absent
    OpenCC = None


_OPENCC = OpenCC("s2tw") if OpenCC else None
_FALLBACK_REPLACEMENTS = {
    "这": "這",
    "个": "個",
    "认": "認",
    "为": "為",
    "认为": "認為",
    "報道": "報導",
    "报道": "報導",
    "报导": "報導",
    "数据": "資料",
    "质量": "品質",
    "內存": "記憶體",
    "内存": "記憶體",
    "带宽": "頻寬",
    "网络": "網路",
    "协议": "協議",
    "通過": "透過",
    "通过": "透過",
    "产业": "產業",
    "生态": "生態",
    "影响": "影響",
    "底层": "底層",
    "逻辑": "邏輯",
    "态": "態",
    "扩": "擴",
    "链": "鏈",
    "芯片": "晶片",
}

_WEAK_OPENERS = (
    r"^(?:這篇文章|这篇文章|本文|文章)(?:報導|报道|报导|指出|說明|说明|提到|表示)(?:了|，|,|：|:|\s)*",
    r"^(?:作者|原文作者)(?:認為|认为|指出|表示)(?:，|,|：|:|\s)*",
)


def to_traditional_zh_tw(text: str) -> str:
    """Convert text to Traditional Chinese with a tiny fallback when OpenCC is absent."""
    if not text:
        return text
    converted = _OPENCC.convert(text) if _OPENCC else text
    ordered_replacements = sorted(
        _FALLBACK_REPLACEMENTS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for source, target in ordered_replacements:
        converted = converted.replace(source, target)
    return converted


def strip_weak_summary_openers(text: str) -> str:
    """Remove weak summarization lead-ins that dilute the thesis."""
    stripped = text.strip()
    for pattern in _WEAK_OPENERS:
        stripped = re.sub(pattern, "", stripped).lstrip()
    return stripped


def normalize_llm_payload(value: Any) -> Any:
    """Recursively normalize LLM JSON payloads to zh-TW and stronger thesis starts."""
    if isinstance(value, str):
        return strip_weak_summary_openers(to_traditional_zh_tw(value))
    if isinstance(value, list):
        return [normalize_llm_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_llm_payload(item) for key, item in value.items()}
    return value
