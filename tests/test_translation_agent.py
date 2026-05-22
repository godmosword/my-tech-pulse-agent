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
