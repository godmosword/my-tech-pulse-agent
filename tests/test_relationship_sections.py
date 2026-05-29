"""Unit tests for 10-K section selection."""

from agents.relationship_extractor import select_relationship_sections


def test_select_sections_prefers_keyword_windows():
    text = "Intro " * 100
    text += "Item 1A. Risk Factors. We rely on a single foundry partner. "
    text += "Competition includes several large semiconductor companies. "
    text += "Filler " * 5000
    section = select_relationship_sections(text)
    assert "Risk Factors" in section
    assert "Competition" in section
    assert len(section) <= 28_000
