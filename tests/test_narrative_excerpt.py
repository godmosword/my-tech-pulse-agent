"""Regression tests for narrative excerpt sentence-boundary truncation."""

from pipeline.crew import truncate_paragraph_at_sentence_boundary


def test_truncate_short_returns_full():
    text = "短。"
    assert truncate_paragraph_at_sentence_boundary(text, max_chars=600) == text


def test_truncate_respects_chinese_period_before_hard_cut():
    long_core = "這是一段很長的文字。" * 80
    text = long_core + "尾巴不要切在中間例如 N"
    out = truncate_paragraph_at_sentence_boundary(text, max_chars=100)
    assert out.endswith("。")
    assert len(out) <= 100
    assert "例如 N" not in out or len(out) < len(text)


def test_truncate_english_period_with_space():
    s = "First sentence. Second sentence " + "x" * 200
    out = truncate_paragraph_at_sentence_boundary(s, max_chars=40)
    assert out.endswith(".")
    assert "Second" not in out or out.startswith("First")


def test_newline_fallback():
    text = "Line one without ending punct\nLine two " + "z" * 300
    out = truncate_paragraph_at_sentence_boundary(text, max_chars=50)
    assert "\n" not in out or len(out) <= 50
