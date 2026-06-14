"""Read-only watchlist coverage audit (A6)."""

from pathlib import Path

import pytest

from sources.watchlist_audit import (
    coverage_report,
    find_duplicates,
    format_report_md,
    load_observed,
    load_raw_entries,
    load_targets,
)

SAMPLE_YAML = """
entries:
  - { ticker: NVDA, tier: 1, tags: [ai_infra] }
  - { ticker: AMD, tier: 1, tags: [ai_infra] }
  - { ticker: MU, tier: 2, tags: [memory] }
  - { ticker: nvda, tier: 1, tags: [dup_same_tier] }
  - { ticker: AMD, tier: 3, tags: [conflict] }
  - { ticker: "", tier: 2 }
  - { ticker: ZZZ, tier: 9, tags: [bad_tier] }
"""


@pytest.fixture
def entries(tmp_path: Path):
    p = tmp_path / "wl.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    return load_raw_entries(p)


def test_load_raw_entries_preserves_duplicates_and_skips_blank(entries):
    tickers = [e["ticker"] for e in entries]
    # blank ticker skipped; nvda upper-cased; duplicates preserved
    assert "" not in tickers
    assert tickers.count("NVDA") == 2
    assert tickers.count("AMD") == 2
    assert len(entries) == 6


def test_find_duplicates_classifies_same_tier_and_conflict(entries):
    dup = find_duplicates(entries)
    same = {d["ticker"] for d in dup["same_tier"]}
    conflict = {d["ticker"] for d in dup["tier_conflict"]}
    assert "NVDA" in same  # both tier 1
    assert "AMD" in conflict  # tier 1 and tier 3
    assert "NVDA" not in conflict


def test_coverage_report_counts_and_out_of_range(entries):
    report = coverage_report(entries)
    assert report["total"] == 6
    assert report["unique_tickers"] == 4  # NVDA, AMD, MU, ZZZ
    assert report["tier_counts"][1] == 3
    assert report["out_of_range_tiers"] == [9]


def test_coverage_report_candidates_exclude_existing(entries):
    report = coverage_report(entries, observed=["NVDA", "foo", "BAR", "bar"])
    assert report["candidates"] == ["BAR", "FOO"]  # NVDA excluded, deduped, sorted
    assert report["candidate_count"] == 2


def test_coverage_report_targets_gap(entries):
    report = coverage_report(entries, targets={1: 5, 2: 1})
    assert report["tier_gaps"][1] == {"target": 5, "current": 3, "gap": 2}
    assert report["tier_gaps"][2] == {"target": 1, "current": 1, "gap": 0}


def test_load_observed_csv(tmp_path: Path):
    p = tmp_path / "obs.csv"
    p.write_text("symbol,note\nNVDA,x\nfoo,y\n", encoding="utf-8")
    assert load_observed(p) == ["NVDA", "FOO"]


def test_load_observed_json_variants(tmp_path: Path):
    p1 = tmp_path / "a.json"
    p1.write_text('["NVDA", "foo"]', encoding="utf-8")
    assert load_observed(p1) == ["NVDA", "FOO"]

    p2 = tmp_path / "b.json"
    p2.write_text('{"items": [{"ticker": "NVDA"}, {"symbol": "foo"}]}', encoding="utf-8")
    assert load_observed(p2) == ["NVDA", "FOO"]


def test_load_observed_bad_format_raises(tmp_path: Path):
    p = tmp_path / "bad.csv"
    p.write_text("name,note\nNVDA,x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_observed(p)


def test_load_targets(tmp_path: Path):
    p = tmp_path / "t.json"
    p.write_text('{"3": 10, "5": 10}', encoding="utf-8")
    assert load_targets(p) == {3: 10, 5: 10}


def test_format_report_md_includes_sections(entries):
    md = format_report_md(coverage_report(entries, observed=["FOO"], targets={1: 5}))
    assert "# Watchlist 覆蓋稽核" in md
    assert "Tier 目標缺口" in md
    assert "跨 tier 衝突：AMD" in md
    assert "候選" in md and "FOO" in md
