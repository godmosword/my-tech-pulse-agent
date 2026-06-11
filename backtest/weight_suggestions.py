"""Suggest signal factor weight adjustments from backtest calibration records."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backtest.metrics import BEARISH_RATINGS, BULLISH_RATINGS, _spearman
from scoring.signal_engine import DEFAULT_CONFIG_PATH, FACTOR_LABELS_ZH, load_signal_config

FACTOR_NAMES = (
    "fundamental_momentum",
    "surprise",
    "market_confirmation",
    "quality",
)

ADJUSTMENT_STRENGTH = 0.5


def extract_factor_score(record: dict[str, Any], factor: str) -> float | None:
    factor_scores = record.get("factor_scores")
    if isinstance(factor_scores, dict) and factor in factor_scores:
        value = factor_scores[factor]
        return float(value) if value is not None else None

    factors = record.get("factors")
    if isinstance(factors, list):
        for row in factors:
            if not isinstance(row, dict):
                continue
            if row.get("name") != factor:
                continue
            if not row.get("available"):
                return None
            score = row.get("score")
            return float(score) if score is not None else None

    flat_key = f"factor_{factor}"
    if flat_key in record and record[flat_key] is not None:
        return float(record[flat_key])
    return None


def outcome_excess(record: dict[str, Any], horizon_days: int) -> float | None:
    returns = record.get("returns")
    key = f"excess_{horizon_days}d"
    if isinstance(returns, dict) and key in returns:
        value = returns[key]
        return float(value) if value is not None else None
    if key in record and record[key] is not None:
        return float(record[key])
    return None


def outcome_hit(record: dict[str, Any], horizon_days: int) -> int | None:
    excess = outcome_excess(record, horizon_days)
    if excess is None:
        return None
    rating = str(record.get("rating") or "")
    if rating in BULLISH_RATINGS:
        return 1 if excess > 0 else 0
    if rating in BEARISH_RATINGS:
        return 1 if excess < 0 else 0
    return None


def _has_variance(values: list[float]) -> bool:
    if len(values) < 2:
        return False
    first = values[0]
    return any(v != first for v in values[1:])


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _hit_rate(hits: list[int]) -> float | None:
    if not hits:
        return None
    return round(sum(hits) / len(hits), 4)


def _top_bottom_tertile_means(
    scores: list[float],
    outcomes: list[float],
) -> tuple[float | None, float | None]:
    if len(scores) != len(outcomes) or len(scores) < 3:
        return None, None
    paired = sorted(zip(scores, outcomes, strict=True), key=lambda p: p[0])
    third = max(len(paired) // 3, 1)
    low = [o for _, o in paired[:third]]
    high = [o for _, o in paired[-third:]]
    return _mean(low), _mean(high)


def analyze_factor(
    records: list[dict[str, Any]],
    *,
    factor: str,
    horizon_days: int,
    min_samples: int,
) -> dict[str, Any]:
    scores: list[float] = []
    excesses: list[float] = []
    hits: list[int] = []

    for record in records:
        score = extract_factor_score(record, factor)
        excess = outcome_excess(record, horizon_days)
        hit = outcome_hit(record, horizon_days)
        if score is None or excess is None:
            continue
        scores.append(score)
        excesses.append(excess)
        if hit is not None:
            hits.append(hit)

    n = len(scores)
    base: dict[str, Any] = {
        "factor": factor,
        "label_zh": FACTOR_LABELS_ZH.get(factor, factor),
        "n": n,
        "min_samples": min_samples,
    }

    if n < min_samples:
        return {
            **base,
            "status": "insufficient_data",
            "message": "資料不足，不出建議",
        }

    if not _has_variance(scores):
        return {
            **base,
            "status": "no_variance",
            "message": "因子分數無變異，無法計算相關性",
            "mean_hit_rate": _hit_rate(hits),
            "mean_excess_pct": _mean(excesses),
        }

    spearman_excess = _spearman(scores, excesses)
    spearman_hit = _spearman(scores, [float(h) for h in hits]) if hits else None
    low_excess, high_excess = _top_bottom_tertile_means(scores, excesses)

    return {
        **base,
        "status": "ok",
        "spearman_vs_excess": spearman_excess,
        "spearman_vs_hit": spearman_hit,
        "mean_hit_rate": _hit_rate(hits),
        "mean_excess_pct": _mean(excesses),
        "bottom_tertile_mean_excess_pct": low_excess,
        "top_tertile_mean_excess_pct": high_excess,
        "hit_n": len(hits),
    }


def suggest_weights(
    factor_analyses: dict[str, dict[str, Any]],
    current_weights: dict[str, float],
    *,
    min_samples: int,
) -> dict[str, Any]:
    """Derive normalized weight suggestions from factor correlation stats."""
    adjustable: dict[str, float] = {}
    rationales: dict[str, str] = {}

    for factor in FACTOR_NAMES:
        current = float(current_weights.get(factor, 0.0))
        analysis = factor_analyses[factor]
        status = analysis.get("status")

        if status == "insufficient_data":
            rationales[factor] = (
                f"僅 {analysis.get('n', 0)} 筆有效樣本（門檻 {min_samples}），資料不足，不出建議；"
                f"維持現行權重 {current:.2f}。"
            )
            adjustable[factor] = current
            continue

        if status == "no_variance":
            rationales[factor] = (
                f"樣本數 {analysis.get('n')}，但因子分數全同值，無法估計相關性；維持現行權重 {current:.2f}。"
            )
            adjustable[factor] = current
            continue

        corr = analysis.get("spearman_vs_excess")
        hit_rate = analysis.get("mean_hit_rate")
        mean_excess = analysis.get("mean_excess_pct")
        top_excess = analysis.get("top_tertile_mean_excess_pct")
        bottom_excess = analysis.get("bottom_tertile_mean_excess_pct")

        if corr is None:
            rationales[factor] = (
                f"樣本數 {analysis.get('n')}，相關性無法計算；維持現行權重 {current:.2f}。"
            )
            adjustable[factor] = current
            continue

        delta_hint = corr * ADJUSTMENT_STRENGTH
        proposed = max(0.0, current * (1.0 + delta_hint))
        adjustable[factor] = proposed
        direction = "上調" if proposed > current else ("下調" if proposed < current else "維持")
        rationales[factor] = (
            f"樣本 n={analysis.get('n')}；Spearman(因子分, 超額報酬)={corr:+.3f}，"
            f"命中率={hit_rate if hit_rate is not None else '—'}，"
            f"平均超額={mean_excess if mean_excess is not None else '—'}%；"
            f"高/低分位超額={top_excess if top_excess is not None else '—'}/"
            f"{bottom_excess if bottom_excess is not None else '—'}%。"
            f"建議{direction}權重 {current:.2f} → {proposed:.2f}（未正規化）。"
        )

    total = sum(adjustable.values())
    if total <= 0:
        normalized = {name: float(current_weights.get(name, 0.0)) for name in FACTOR_NAMES}
    else:
        normalized = {name: round(adjustable[name] / total, 4) for name in FACTOR_NAMES}

    suggestions: dict[str, dict[str, Any]] = {}
    for factor in FACTOR_NAMES:
        current = round(float(current_weights.get(factor, 0.0)), 4)
        suggested = normalized[factor]
        suggestions[factor] = {
            "current_weight": current,
            "suggested_weight": suggested,
            "weight_delta": round(suggested - current, 4),
            "rationale": rationales[factor],
            "analysis": factor_analyses[factor],
        }

    return {
        "adjustment_strength": ADJUSTMENT_STRENGTH,
        "factors": suggestions,
        "suggested_weights_normalized": normalized,
    }


def build_weight_suggestion_report(
    records: list[dict[str, Any]],
    *,
    horizon_days: int = 20,
    min_samples: int = 20,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    cfg = load_signal_config(config_path or DEFAULT_CONFIG_PATH)
    current_weights = {name: float(cfg["weights"][name]) for name in FACTOR_NAMES}

    valid_records = [
        row
        for row in records
        if outcome_excess(row, horizon_days) is not None and row.get("rating")
    ]
    overall_n = len(valid_records)

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon_days": horizon_days,
        "min_samples": min_samples,
        "current_weights": current_weights,
        "n_records_input": len(records),
        "n_records_with_returns": overall_n,
    }

    if overall_n < min_samples:
        report["status"] = "insufficient_data"
        report["message"] = "資料不足，不出建議"
        report["weight_suggestions"] = None
        return report

    factor_analyses = {
        factor: analyze_factor(
            records,
            factor=factor,
            horizon_days=horizon_days,
            min_samples=min_samples,
        )
        for factor in FACTOR_NAMES
    }
    suggestions = suggest_weights(
        factor_analyses,
        current_weights,
        min_samples=min_samples,
    )

    actionable = [
        factor
        for factor, analysis in factor_analyses.items()
        if analysis.get("status") == "ok" and analysis.get("spearman_vs_excess") is not None
    ]
    if not actionable:
        report["status"] = "insufficient_data"
        report["message"] = "資料不足，不出建議（無因子通過樣本與變異檢定）"
        report["factor_analyses"] = factor_analyses
        report["weight_suggestions"] = None
        return report

    report["status"] = "ok"
    report["message"] = "以下為建議值，請人工審閱後手動更新 scoring/signal_config.yaml（腳本不會自動寫入）。"
    report["factor_analyses"] = factor_analyses
    report["weight_suggestions"] = suggestions
    return report


def render_weight_suggestion_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Signal 因子權重建議報告",
        "",
        f"生成時間：{report.get('generated_at', '')}",
        f"評估 horizon：{report.get('horizon_days')} 交易日",
        f"樣本門檻：{report.get('min_samples')} 筆",
        f"輸入筆數：{report.get('n_records_input')}（含超額報酬 {report.get('n_records_with_returns')} 筆）",
        "",
    ]

    status = report.get("status")
    message = report.get("message") or ""
    if status != "ok":
        lines.append(f"## ⚠ {message}")
        lines.append("")
        analyses = report.get("factor_analyses") or {}
        if analyses:
            lines.append("### 因子診斷（僅供參考）")
            lines.append("")
            for factor in FACTOR_NAMES:
                row = analyses.get(factor) or {}
                lines.append(
                    f"- **{FACTOR_LABELS_ZH.get(factor, factor)}** (`{factor}`)："
                    f"{row.get('message', row.get('status', '—'))}（n={row.get('n', 0)}）"
                )
            lines.append("")
        lines.append("> 本報告不會修改 `scoring/signal_config.yaml`。")
        return "\n".join(lines)

    lines.append(f"## {message}")
    lines.append("")
    current = report.get("current_weights") or {}
    suggested = (report.get("weight_suggestions") or {}).get("suggested_weights_normalized") or {}

    lines.append("## 權重對照（正規化後）")
    lines.append("")
    lines.append("| 因子 | 現行 | 建議 | Δ |")
    lines.append("| --- | ---: | ---: | ---: |")
    for factor in FACTOR_NAMES:
        cur = current.get(factor, 0.0)
        sug = suggested.get(factor, cur)
        lines.append(
            f"| {FACTOR_LABELS_ZH.get(factor, factor)} | {cur:.2f} | {sug:.2f} | {sug - cur:+.2f} |"
        )
    lines.append("")

    lines.append("## 各因子依據")
    lines.append("")
    factors = (report.get("weight_suggestions") or {}).get("factors") or {}
    for factor in FACTOR_NAMES:
        block = factors.get(factor) or {}
        analysis = block.get("analysis") or {}
        lines.append(f"### {FACTOR_LABELS_ZH.get(factor, factor)} (`{factor}`)")
        lines.append("")
        lines.append(f"- {block.get('rationale', '—')}")
        if analysis.get("status") == "ok":
            lines.append(
                f"- Spearman vs 超額：{analysis.get('spearman_vs_excess')}；"
                f"vs 命中：{analysis.get('spearman_vs_hit')}"
            )
        lines.append("")

    lines.append("> 請人工審閱後手動更新 `scoring/signal_config.yaml`。")
    return "\n".join(lines)


def load_records_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("records", "rows", "data"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(f"Unsupported records JSON shape: {path}")


def load_records_csv(path: Path) -> list[dict[str, Any]]:
    import csv

    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row: dict[str, Any] = dict(raw)
            returns: dict[str, float] = {}
            factor_scores: dict[str, float] = {}
            for key, val in row.items():
                if not val:
                    continue
                if key.startswith("excess_") and key.endswith("d"):
                    try:
                        returns[key] = float(val)
                    except ValueError:
                        continue
                if key.startswith("factor_"):
                    try:
                        factor_scores[key.removeprefix("factor_")] = float(val)
                    except ValueError:
                        continue
            if returns:
                row["returns"] = returns
            if factor_scores:
                row["factor_scores"] = factor_scores
            if row.get("score") not in (None, ""):
                try:
                    row["score"] = float(row["score"])
                except ValueError:
                    pass
            rows.append(row)
    return rows


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        return load_records_csv(path)
    if path.suffix.lower() == ".json":
        return load_records_json(path)
    raise ValueError(f"Unsupported records format: {path}")


def write_report_outputs(
    report: dict[str, Any],
    *,
    out_json: Path,
    out_md: Path,
) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_weight_suggestion_markdown(report), encoding="utf-8")
