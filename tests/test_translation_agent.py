"""Tests for translation agent fallback zh fields."""

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.extractor_agent import ArticleSummary
from agents.translation_agent import (
    apply_zh_backfill_to_summary,
    needs_zh_translation,
    translation_agent_enabled,
)
from agents.translation_align import apply_translation_alignment, translation_is_aligned
from llm.zh_backfill import ZhBackfillResult


def _summary(**kwargs) -> ArticleSummary:
    base = dict(
        entity="CoinDesk",
        title="Bitcoin quantum risk study",
        summary="An expert argues large BTC holdings need migration planning.",
        what_happened="A researcher published a paper on quantum threats.",
        why_it_matters="",
        category="research",
        key_facts=[],
        sentiment="neutral",
        confidence="medium",
    )
    base.update(kwargs)
    return ArticleSummary(**base)


def test_needs_zh_translation_when_title_and_summary_missing_cjk():
    s = _summary(zh_title=None, zh_summary=None)
    assert needs_zh_translation(s) is True


def test_needs_zh_translation_false_when_both_present():
    s = _summary(
        zh_title="專家示警量子運算威脅比特幣",
        zh_summary="研究指出大額持倉需提前規劃遷移。投資人應關注保管方案更新。",
    )
    assert needs_zh_translation(s) is False


def test_apply_zh_backfill_fills_missing_fields():
    s = _summary(zh_title=None, zh_summary=None)
    zh = ZhBackfillResult(
        zh_title="專家示警量子運算威脅比特幣",
        zh_summary="研究指出大額持倉需提前規劃遷移。投資人應關注保管方案更新。",
        hook="量子風險再評估",
    )
    assert apply_zh_backfill_to_summary(s, zh) is True
    assert "比特幣" in (s.zh_title or "")
    assert "遷移" in (s.zh_summary or "")


@patch.dict("os.environ", {"TRANSLATION_AGENT_ENABLED": "0"})
def test_translation_agent_disabled_by_env():
    assert translation_agent_enabled() is False


def test_translate_batch_skips_when_disabled():
    from agents.translation_agent import TranslationAgent

    with patch.dict("os.environ", {"TRANSLATION_AGENT_ENABLED": "0"}):
        agent = TranslationAgent()
        out, filled = agent.translate_batch([_summary()])
    assert filled == 0
    assert len(out) == 1


def test_translation_aligned_when_numbers_and_ticker_match():
    s = _summary(
        title="NVDA revenue rose 20%",
        summary="NVDA posted 20% growth.",
        what_happened="NVDA reported 20% revenue growth.",
        tickers=["NVDA"],
        zh_title="NVDA 營收增 20%",
        zh_summary="NVDA 公布營收成長 20%。",
    )
    assert translation_is_aligned(s) is True


def test_translation_not_aligned_when_number_missing_in_zh():
    s = _summary(
        title="Revenue rose 20%",
        summary="Growth was 20%.",
        what_happened="The company reported 20% growth.",
        zh_title="營收成長",
        zh_summary="公司公布成長。",
    )
    assert translation_is_aligned(s) is False


def test_apply_translation_alignment_sets_flag():
    s = _summary(
        title="Quiet update",
        summary="No figures.",
        what_happened="The vendor shipped a patch.",
        zh_title="靜默更新",
        zh_summary="供應商釋出修補。",
    )
    apply_translation_alignment([s])
    assert s.translation_aligned is True
