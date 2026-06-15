"""Tests for the canonical search-token contract (scoring/search_tokens.py).

The same cases are mirrored in dashboard/lib/search-tokens.test.ts; if you change
behavior here, update that file too.
"""

from __future__ import annotations

from scoring.search_tokens import (
    build_search_tokens,
    search_tokens_for_payload,
    tokenize_query,
)


def test_latin_words_lowercased_and_min_length():
    tokens = build_search_tokens(core_texts=["Nvidia Q1 AI a"])
    assert "nvidia" in tokens
    assert "q1" in tokens
    assert "ai" in tokens
    # single-character runs are dropped as noise
    assert "a" not in tokens


def test_cjk_runs_become_bigrams():
    tokens = build_search_tokens(core_texts=["輝達財報"])
    assert "輝達" in tokens
    assert "達財" in tokens
    assert "財報" in tokens
    # not stored as the whole run
    assert "輝達財報" not in tokens


def test_single_cjk_char_kept():
    assert "台" in build_search_tokens(core_texts=["台"])


def test_tickers_lowercased_and_deduped():
    tokens = build_search_tokens(core_texts=["Nvidia"], tickers=["NVDA", "nvda", ""])
    assert "nvda" in tokens
    assert tokens == sorted(set(tokens))


def test_result_is_sorted_and_deduped():
    tokens = build_search_tokens(core_texts=["beta alpha alpha", "BETA"])
    assert tokens == ["alpha", "beta"]


def test_core_tokens_retained_over_extra_when_budget_tight():
    tokens = build_search_tokens(
        core_texts=["zzz"],
        extra_texts=["aaa bbb ccc"],
        max_tokens=1,
    )
    # core fills the whole budget; extra is excluded
    assert tokens == ["zzz"]


def test_extra_fills_remaining_budget():
    tokens = build_search_tokens(
        core_texts=["zzz"],
        extra_texts=["aaa"],
        max_tokens=5,
    )
    assert set(tokens) == {"zzz", "aaa"}


def test_mid_title_word_is_searchable():
    # The original prefix search could not find this; token search can.
    payload = {"title": "Why Nvidia earnings beat", "tickers": ["NVDA"]}
    tokens = search_tokens_for_payload(payload)
    query = tokenize_query("nvidia")
    assert query == ["nvidia"]
    assert any(token in tokens for token in query)


def test_payload_uses_identity_fields():
    payload = {
        "title": "Apple ships chip",
        "zh_title": "蘋果出貨晶片",
        "entity": "Apple",
        "hook": "供應鏈",
        "zh_summary": "這是一段摘要",
        "tickers": ["AAPL"],
    }
    tokens = search_tokens_for_payload(payload)
    assert "aapl" in tokens
    assert "apple" in tokens
    assert "晶片" in tokens  # from zh_title bigram
    assert "供應" in tokens  # from hook


def test_payload_includes_summary_and_zh_body_extra_tokens():
    payload = {
        "title": "Daily wrap",
        "summary": "TSMC fab utilization rises",
        "zh_body": "台積電產能利用率提升帶動供應鏈",
        "tickers": [],
    }
    tokens = search_tokens_for_payload(payload)
    assert "tsmc" in tokens
    assert "台積" in tokens  # from zh_body bigram


def test_tokenize_query_limit():
    long_query = " ".join(f"w{i}" for i in range(50))
    assert len(tokenize_query(long_query)) == 30


def test_tokenize_query_empty():
    assert tokenize_query("") == []
    assert tokenize_query("   ") == []
