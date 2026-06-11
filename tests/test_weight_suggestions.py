"""Tests for backtest → signal weight suggestion logic."""

from __future__ import annotations

import json

from backtest.weight_suggestions import (
    analyze_factor,
    build_weight_suggestion_report,
    load_records_csv,
    render_weight_suggestion_markdown,
)


def _record(
    *,
    score: float,
    rating: str,
    excess: float,
    factors: dict[str, float],
) -> dict:
    return {
        "score": score,
        "rating": rating,
        "returns": {"excess_20d": excess},
        "factor_scores": factors,
    }


def _synthetic_records(n: int = 30) -> list[dict]:
    rows: list[dict] = []
    for i in range(n):
        fundamental = 40.0 + i * 1.5
        surprise = 80.0 - i * 0.5
        excess = (fundamental - 60.0) * 0.2
        rows.append(
            _record(
                score=fundamental,
                rating="看多",
                excess=excess,
                factors={
                    "fundamental_momentum": fundamental,
                    "surprise": surprise,
                    "quality": 50.0,
                },
            )
        )
    return rows


def test_analyze_factor_insufficient_samples():
    rows = [_record(score=80, rating="看多", excess=1.0, factors={"fundamental_momentum": 70})]
    out = analyze_factor(rows, factor="fundamental_momentum", horizon_days=20, min_samples=20)
    assert out["status"] == "insufficient_data"
    assert "資料不足" in out["message"]


def test_analyze_factor_no_variance():
    rows = [
        _record(score=80, rating="看多", excess=1.0, factors={"fundamental_momentum": 70})
        for _ in range(25)
    ]
    out = analyze_factor(rows, factor="fundamental_momentum", horizon_days=20, min_samples=20)
    assert out["status"] == "no_variance"
    assert "因子分數無變異" in out["message"]


def test_build_report_positive_correlation_suggests_higher_fundamental_weight():
    report = build_weight_suggestion_report(
        _synthetic_records(30),
        horizon_days=20,
        min_samples=20,
    )
    assert report["status"] == "ok"
    suggestions = report["weight_suggestions"]["factors"]["fundamental_momentum"]
    assert suggestions["suggested_weight"] > suggestions["current_weight"]
    assert suggestions["analysis"]["spearman_vs_excess"] is not None
    assert suggestions["analysis"]["spearman_vs_excess"] > 0


def test_build_report_insufficient_overall_samples():
    report = build_weight_suggestion_report(
        _synthetic_records(10),
        horizon_days=20,
        min_samples=20,
    )
    assert report["status"] == "insufficient_data"
    assert report["message"] == "資料不足，不出建議"
    assert report["weight_suggestions"] is None


def test_build_report_skips_rows_without_returns():
    rows = _synthetic_records(25)
    rows.extend([
        {"rating": "看多", "factor_scores": {"fundamental_momentum": 90.0}},
        {"rating": "看多", "returns": {"excess_20d": None}, "factor_scores": {"fundamental_momentum": 80.0}},
    ])
    report = build_weight_suggestion_report(rows, horizon_days=20, min_samples=20)
    assert report["n_records_with_returns"] == 25


def test_render_markdown_includes_rationale():
    report = build_weight_suggestion_report(_synthetic_records(30), horizon_days=20, min_samples=20)
    md = render_weight_suggestion_markdown(report)
    assert "基本面動能" in md
    assert "signal_config.yaml" in md
    assert "Spearman" in md


def test_load_records_csv_flattens_factor_columns(tmp_path):
    csv_path = tmp_path / "records.csv"
    csv_path.write_text(
        "symbol,rating,score,excess_20d,factor_fundamental_momentum\n"
        "NVDA,看多,80,1.5,72.5\n",
        encoding="utf-8",
    )
    rows = load_records_csv(csv_path)
    assert rows[0]["returns"]["excess_20d"] == 1.5
    assert rows[0]["factor_scores"]["fundamental_momentum"] == 72.5


def test_report_json_roundtrip():
    report = build_weight_suggestion_report(_synthetic_records(30), horizon_days=20, min_samples=20)
    payload = json.loads(json.dumps(report, default=str))
    assert payload["status"] == "ok"
    assert payload["weight_suggestions"]["suggested_weights_normalized"]
