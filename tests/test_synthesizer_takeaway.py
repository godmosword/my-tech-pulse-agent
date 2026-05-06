"""Tests for market takeaway vs headline deduplication."""

from agents.synthesizer_agent import DigestOutput, SynthesizerAgent, Theme


def test_takeaway_skips_line_similar_to_headline():
    digest = DigestOutput(
        date="2026-05-06",
        headline="輝達資料中心需求強勁推升營收展望",
        narrative=(
            "輝達資料中心需求強勁推升營收展望，股價反映預期。\n\n"
            "第二段：供應鏈瓶頸集中在 CoWoS，終端 CSP 資本支出分化。"
        ),
        themes=[],
    )
    out = SynthesizerAgent.build_market_takeaway(digest)
    assert "第二段" in out or "供應鏈" in out
    assert out != digest.narrative.splitlines()[0][:180]


def test_takeaway_falls_back_to_themes_when_all_lines_match():
    h = "完全一樣的標題"
    digest = DigestOutput(
        date="2026-05-06",
        headline=h,
        narrative=f"{h}\n{h}",
        themes=[Theme(theme="主題A", description="d", confidence="high")],
    )
    out = SynthesizerAgent.build_market_takeaway(digest)
    assert "主題A" in out
