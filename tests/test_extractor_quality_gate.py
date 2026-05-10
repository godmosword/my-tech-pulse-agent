"""Prompt-level quality gate: roundup/advisory rejection + zh_summary specificity."""

from agents.extractor_agent import EXTRACTION_PROMPT


def test_extractor_prompt_contains_roundup_filter():
    text = EXTRACTION_PROMPT
    assert "Quality gate" in text
    assert "roundup" in text.lower()
    assert "community wisdom" in text.lower()


def test_extractor_prompt_zh_summary_requires_specific_entity():
    text = EXTRACTION_PROMPT
    # Must explicitly forbid the generic openers we observed in production
    assert "實用見解" in text
    assert "重要討論" in text
    # Must allow null when source is too thin
    assert "set zh_summary to null" in text
