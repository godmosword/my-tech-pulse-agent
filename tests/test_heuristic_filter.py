"""Unit tests for cheap pre-LLM heuristic filtering (edge cases)."""

from __future__ import annotations

import pytest

from scoring.heuristic_filter import HeuristicFilter
from sources.rss_fetcher import Article


def _article(
    *,
    title: str,
    summary: str = "",
    content: str = "",
    label: str = "news",
) -> Article:
    return Article(
        title=title,
        url="https://example.com/item",
        source="test",
        summary=summary,
        content=content,
        label=label,
    )


@pytest.mark.parametrize(
    "article,reason_substr",
    [
        pytest.param(
            _article(
                title="Best streaming deals",
                summary="Coupon promo code discount gift guide.",
            ),
            "low_signal",
            id="E01_streaming_deals",
        ),
        pytest.param(
            _article(
                title="Powerful AI breakthrough deal",
                summary="Coupon promo code discount gift guide.",
            ),
            "low_signal",
            id="E02_ai_title_promo_body",
        ),
        pytest.param(
            _article(
                title="New transformer architecture on arxiv",
                summary="We propose a method in this paper. NeurIPS submission.",
            ),
            "academic",
            id="E03_academic_preprint",
        ),
        pytest.param(
            _article(
                title="Retail earnings beat expectations",
                summary="Same-store sales rose across department stores.",
            ),
            "offtopic",
            id="E04_general_finance",
        ),
        pytest.param(
            _article(
                title="Farm subsidy reform advances in Congress",
                summary="Disarmament talks continue without technology sector impact.",
            ),
            "offtopic",
            id="E05_arm_false_positive",
        ),
        pytest.param(
            _article(
                title="Nvidia mentioned in roundup",
                summary="A short blurb about the company without numbers or events.",
            ),
            "gate:needs_depth_or_specifics",
            id="E06_theme_without_depth_or_specifics",
        ),
    ],
)
def test_drop_cases(article: Article, reason_substr: str) -> None:
    result = HeuristicFilter().evaluate(article)
    assert result.passed is False
    assert reason_substr in result.reason


def test_e07_score_below_threshold() -> None:
    """Score can clear components but still fail MIN_BASE_SCORE_THRESHOLD."""
    article = _article(
        title="AI roundup",
        summary="Coupon promo code discount gift guide for gadgets.",
    )
    filt = HeuristicFilter(threshold=0.90)
    result = filt.evaluate(article)
    assert result.passed is False
    assert result.score < 0.90


@pytest.mark.parametrize(
    "article,reason_substr",
    [
        pytest.param(
            _article(
                title="Nvidia launches new AI data center GPU",
                summary="Nvidia announced a new AI data center GPU with 30% faster inference.",
            ),
            "theme:ai",
            id="P01_nvidia_gpu",
        ),
        pytest.param(
            _article(
                title="TSMC raises capex guidance",
                summary="TSMC reported $28 billion in planned fab spending for 2026.",
            ),
            "theme:semi",
            id="P02_tsmc_capex",
        ),
        pytest.param(
            _article(
                title="Spot bitcoin ETF sees inflows",
                summary="Regulators reviewed filings as bitcoin ETF inflows rose 12%.",
            ),
            "theme:crypto",
            id="P03_bitcoin_etf",
        ),
        pytest.param(
            _article(
                title="Platform strategy",
                summary="Essay on business models.",
                label="kol",
            ),
            "kol_bypass",
            id="P04_kol_bypass",
        ),
        pytest.param(
            _article(
                title="OpenAI releases frontier model",
                summary="OpenAI announced GPT-5 with benchmark gains reported by partners.",
            ),
            "depth_markers",
            id="P05_threshold_and_gate",
        ),
    ],
)
def test_pass_cases(article: Article, reason_substr: str) -> None:
    result = HeuristicFilter().evaluate(article)
    assert result.passed is True
    assert reason_substr in result.reason


def test_near_term_does_not_hit_crypto_cluster() -> None:
    article = _article(
        title="Near-term retail outlook",
        summary="Analysts discussed consumer demand across department stores.",
    )
    result = HeuristicFilter().evaluate(article)
    assert "theme:crypto" not in result.reason


def test_solution_does_not_hit_sol_token() -> None:
    article = _article(
        title="Enterprise solution roadmap",
        summary="Vendors outlined software rollout plans for IT leaders.",
    )
    result = HeuristicFilter().evaluate(article)
    assert "theme:crypto" not in result.reason


def test_filter_articles_sets_prefiltered_status() -> None:
    dropped_article = _article(
        title="Best streaming deals",
        summary="Coupon promo code discount gift guide.",
    )
    passed_article = _article(
        title="Nvidia launches new AI data center GPU",
        summary="Nvidia announced a new AI data center GPU with 30% faster inference.",
    )
    filt = HeuristicFilter()
    passed, dropped = filt.filter_articles([dropped_article, passed_article])
    assert len(passed) == 1
    assert len(dropped) == 1
    assert dropped[0].score_status == "prefiltered_out"
    assert passed[0].base_score_status
