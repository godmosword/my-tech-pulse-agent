"""Tests for news takeaway agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agents.extractor_agent import ArticleSummary
from agents.news_takeaway_agent import NewsTakeawayAgent, news_takeaway_enabled
from agents.news_takeaway_models import NewsTakeaway


def _summary(**kwargs) -> ArticleSummary:
    base = dict(
        entity="NVIDIA",
        summary="NVIDIA announced new chips.",
        what_happened="NVIDIA unveiled Blackwell GPUs.",
        why_it_matters="Strengthens AI accelerator lead.",
        category="product_launch",
        key_facts=["Blackwell launch"],
        sentiment="positive",
        confidence="high",
        title="NVIDIA launches Blackwell",
        source_url="https://example.com/nvda",
        source_name="Example",
        tickers=["NVDA"],
    )
    base.update(kwargs)
    return ArticleSummary(**base)


@patch("agents.news_takeaway_agent.make_client")
@patch("agents.news_takeaway_agent.generate_json")
def test_generate_takeaway_normal(mock_gen_json, _mock_client):
    mock_gen_json.return_value = (
        {
            "takeaway_zh": "Blackwell 強化 AI 加速器護城河",
            "angle": "技術突破",
            "involved_companies": ["Nvidia"],
            "confidence": "high",
        },
        "{}",
    )
    aliases = {"nvidia": "NVDA", "nvidia corp": "NVDA"}
    agent = NewsTakeawayAgent()
    agent._client = MagicMock()
    out = agent.generate_takeaway(_summary(), aliases=aliases)

    assert out.takeaway_zh
    assert len(out.takeaway_zh.replace(" ", "")) <= 40
    assert out.angle == "技術突破"
    assert "NVDA" in out.tickers


@patch("agents.news_takeaway_agent.make_client")
@patch("agents.news_takeaway_agent.generate_json")
def test_unknown_company_skipped(mock_gen_json, _mock_client):
    mock_gen_json.return_value = (
        {
            "takeaway_zh": "新創融資反映邊緣 AI 需求",
            "angle": "資本動向",
            "involved_companies": ["Unknown Widgets Inc."],
            "confidence": "medium",
        },
        "{}",
    )
    agent = NewsTakeawayAgent()
    agent._client = MagicMock()
    out = agent.generate_takeaway(_summary(entity="Startup"), aliases={"nvidia": "NVDA"})

    assert out.takeaway_zh
    assert out.tickers == ["NVDA"] or out.tickers == []


@patch("agents.news_takeaway_agent.make_client")
@patch("agents.news_takeaway_agent.generate_json")
def test_overlong_takeaway_retries_then_truncates(mock_gen_json, _mock_client):
    long_line = "這是一個超過四十個中文字的超長投資短評句子需要被截斷或重試處理才符合規格要求必須更長"
    mock_gen_json.side_effect = [
        (
            {
                "takeaway_zh": long_line,
                "angle": "其他",
                "involved_companies": [],
                "confidence": "high",
            },
            "{}",
        ),
        (
            {
                "takeaway_zh": long_line,
                "angle": "其他",
                "involved_companies": [],
                "confidence": "high",
            },
            "{}",
        ),
    ]
    agent = NewsTakeawayAgent()
    agent._client = MagicMock()
    out = agent.generate_takeaway(_summary(), aliases={})

    assert len(out.takeaway_zh.replace(" ", "")) <= 40
    assert out.confidence == "low"


def test_news_takeaway_mode_off(monkeypatch):
    monkeypatch.setenv("NEWS_TAKEAWAY_MODE", "off")
    assert news_takeaway_enabled() is False
    monkeypatch.setenv("NEWS_TAKEAWAY_MODE", "on")
    assert news_takeaway_enabled() is True


@patch("agents.news_takeaway_agent.make_client")
@patch("agents.news_takeaway_agent.generate_json")
def test_gemini_failure_returns_empty(mock_gen_json, _mock_client):
    mock_gen_json.side_effect = RuntimeError("api down")
    agent = NewsTakeawayAgent()
    agent._client = MagicMock()
    out = agent.generate_takeaway(_summary(), aliases={})

    assert isinstance(out, NewsTakeaway)
    assert out.takeaway_zh == ""
