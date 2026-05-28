"""Investment signal synthesis from existing report fields (read-only, no recompute)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from agents.earnings_models import EarningsReport
from agents.earnings_v3_models import (
    EarningsTrend,
    InvestmentSignal,
    MetricTrend,
    SignalFactor,
)

DEFAULT_CONFIG_PATH = Path(__file__).parent / "signal_config.yaml"

FACTOR_LABELS_ZH = {
    "fundamental_momentum": "基本面動能",
    "surprise": "財報驚喜度",
    "market_confirmation": "市場確認",
    "quality": "財務品質",
}


def load_signal_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _saturate(
    value: float,
    strong: float,
    *,
    floor: float = 0.0,
    center: float = 0.0,
) -> float:
    """Map value to 0..100: center→50, center+strong→100, center-strong→0."""
    if strong == 0:
        return 50.0
    raw = 50.0 + (value - center) / strong * 50.0
    return max(floor, min(100.0, raw))


def _trend_metric(trend: EarningsTrend | None, metric: str) -> MetricTrend | None:
    if not trend:
        return None
    for row in trend.trends:
        if row.metric == metric:
            return row
    return None


def _direction_offset(direction: str) -> float:
    if direction == "擴張":
        return 15.0
    if direction == "收縮":
        return -15.0
    return 0.0


def factor_fundamental_momentum(report: EarningsReport, cfg: dict[str, Any]) -> SignalFactor:
    name = "fundamental_momentum"
    weight = float(cfg["weights"][name])
    norm = cfg["normalization"]
    trend = report.trend
    rev_t = _trend_metric(trend, "revenue")
    eps_t = _trend_metric(trend, "eps_diluted") or _trend_metric(trend, "eps")

    scores: list[float] = []
    parts: list[str] = []
    if rev_t and rev_t.yoy_pct is not None:
        s = _saturate(float(rev_t.yoy_pct), float(norm["rev_yoy_strong_pct"]), center=0.0)
        s = max(0.0, min(100.0, s + _direction_offset(rev_t.direction)))
        scores.append(s)
        parts.append(f"營收 YoY {rev_t.yoy_pct:.1f}%（{rev_t.direction}）")
    if eps_t and eps_t.yoy_pct is not None:
        s = _saturate(float(eps_t.yoy_pct), float(norm["eps_yoy_strong_pct"]), center=0.0)
        s = max(0.0, min(100.0, s + _direction_offset(eps_t.direction)))
        scores.append(s)
        parts.append(f"EPS YoY {eps_t.yoy_pct:.1f}%（{eps_t.direction}）")

    if not scores:
        return SignalFactor(
            name=name,
            weight=weight,
            available=False,
            detail_zh="缺少 trend 營收/EPS YoY",
        )
    score = sum(scores) / len(scores)
    return SignalFactor(
        name=name,
        score=round(score, 1),
        weight=weight,
        available=True,
        detail_zh="；".join(parts),
    )


def factor_surprise(report: EarningsReport, cfg: dict[str, Any]) -> SignalFactor:
    name = "surprise"
    weight = float(cfg["weights"][name])
    strong = float(cfg["normalization"]["surprise_strong_pct"])
    sc = report.scorecard
    if not sc:
        return SignalFactor(name=name, weight=weight, available=False, detail_zh="缺少 scorecard")

    surprises: list[tuple[str, float]] = []
    if sc.revenue and sc.revenue.surprise_pct is not None:
        surprises.append(("營收", float(sc.revenue.surprise_pct)))

    eps_ok = sc.headline_verdict != "無法判定" and (
        sc.eps is None or sc.eps.accounting_basis != "Mixed"
    )
    if eps_ok and sc.eps and sc.eps.surprise_pct is not None:
        surprises.append(("EPS", float(sc.eps.surprise_pct)))

    if not surprises:
        detail = "無法判定或缺少 surprise_pct"
        if sc.headline_verdict == "無法判定":
            detail = "headline 無法判定，略過 EPS surprise"
        return SignalFactor(name=name, weight=weight, available=False, detail_zh=detail)

    scores = [_saturate(sp, strong, center=0.0) for _, sp in surprises]
    score = sum(scores) / len(scores)
    parts = [f"{label} surprise {sp:+.1f}%" for label, sp in surprises]
    return SignalFactor(
        name=name,
        score=round(score, 1),
        weight=weight,
        available=True,
        detail_zh="；".join(parts),
    )


def factor_market_confirmation(report: EarningsReport, cfg: dict[str, Any]) -> SignalFactor:
    name = "market_confirmation"
    weight = float(cfg["weights"][name])
    strong = float(cfg["normalization"]["excess_strong_pct"])
    pr = report.price_reaction
    if not pr:
        return SignalFactor(name=name, weight=weight, available=False, detail_zh="缺少 price_reaction")

    excess = pr.excess_5d_pct if pr.excess_5d_pct is not None else pr.excess_1d_pct
    if excess is None:
        return SignalFactor(name=name, weight=weight, available=False, detail_zh="缺少超額報酬")

    score = _saturate(float(excess), strong, center=0.0)
    label = pr.reaction_label or ""
    if label == "利多不漲":
        score = max(0.0, score - 10.0)
    elif label == "利空出盡":
        score = min(100.0, score + 5.0)

    window = "5 日" if pr.excess_5d_pct is not None else "1 日"
    return SignalFactor(
        name=name,
        score=round(score, 1),
        weight=weight,
        available=True,
        detail_zh=f"vs {pr.bench_symbol} 超額 {window} {excess:+.2f}%（{label or '—'}）",
    )


def factor_quality(report: EarningsReport, cfg: dict[str, Any]) -> SignalFactor:
    name = "quality"
    weight = float(cfg["weights"][name])
    norm = cfg["normalization"]
    ratios = report.ratios
    fh = report.financial_health

    sub_scores: list[float] = []
    parts: list[str] = []

    if ratios and ratios.roic is not None:
        sub_scores.append(_saturate(float(ratios.roic), float(norm["roic_strong_pct"]), center=0.0))
        parts.append(f"ROIC {ratios.roic:.1f}%")
    if ratios and ratios.fcf_margin is not None:
        sub_scores.append(
            _saturate(float(ratios.fcf_margin), float(norm["fcf_margin_strong_pct"]), center=0.0)
        )
        parts.append(f"FCF margin {ratios.fcf_margin:.1f}%")
    if ratios and ratios.debt_to_equity is not None:
        de = float(ratios.debt_to_equity)
        high = float(norm["debt_equity_high"])
        sub_scores.append(_saturate(high - de, high, center=0.0))
        parts.append(f"負債比 {de:.2f}")

    if not sub_scores:
        return SignalFactor(name=name, weight=weight, available=False, detail_zh="缺少 ratios 品質指標")

    score = sum(sub_scores) / len(sub_scores)
    if fh and fh.source_conflicts:
        score = max(0.0, score - 5.0)
        parts.append("SEC/FMP 現金流不一致")

    return SignalFactor(
        name=name,
        score=round(score, 1),
        weight=weight,
        available=True,
        detail_zh="；".join(parts),
    )


def _conviction(avail_count: int, cfg: dict[str, Any]) -> str:
    conv = cfg.get("conviction") or {}
    high_min = int(conv.get("high_min_factors", 4))
    med_min = int(conv.get("medium_min_factors", 2))
    if avail_count >= high_min:
        return "high"
    if avail_count >= med_min:
        return "medium"
    return "low"


def _rating_from_score(score: float, buckets: dict[str, Any], conviction: str) -> str:
    if score >= float(buckets["strong_buy"]):
        rating = "強力看多"
    elif score >= float(buckets["buy"]):
        rating = "看多"
    elif score >= float(buckets["neutral"]):
        rating = "中性"
    elif score >= float(buckets["sell"]):
        rating = "看空"
    else:
        rating = "強力看空"

    if conviction == "low":
        if rating == "強力看多":
            return "看多"
        if rating == "強力看空":
            return "看空"
    return rating


def _build_rationale(factors: list[SignalFactor], score: float, conviction: str) -> str:
    avail = [f for f in factors if f.available and f.score is not None]
    if not avail:
        return "可用因子不足，無法形成綜合訊號。"

    ranked = sorted(avail, key=lambda f: (f.score or 0) * f.weight, reverse=True)
    top = ranked[:2]
    parts = [
        f"{FACTOR_LABELS_ZH.get(f.name, f.name)} {f.score:.0f} 分（{f.detail_zh}）"
        for f in top
    ]
    lead = f"綜合分 {score:.1f}，主要受 {'、'.join(parts)} 影響。"
    disclaimer = "此為系統綜合訊號，非投資建議。"
    if conviction == "low":
        return f"{lead} 資料不足，訊號參考性有限。{disclaimer}"
    return f"{lead}{disclaimer}"


BACKTEST_EXCLUDED_DETAIL = "回測停用（避免 post-filing 價格循環洩漏）"


def build_investment_signal(
    report: EarningsReport,
    *,
    config_path: str | Path | None = None,
    exclude_factors: frozenset[str] | None = None,
) -> InvestmentSignal:
    cfg = load_signal_config(config_path)
    raw_weights = cfg["weights"]
    excluded = exclude_factors or frozenset()

    def _maybe_factor(name: str, fn: Any) -> SignalFactor:
        if name in excluded:
            return SignalFactor(
                name=name,
                weight=float(raw_weights[name]),
                available=False,
                detail_zh=BACKTEST_EXCLUDED_DETAIL,
            )
        return fn(report, cfg)

    factors = [
        _maybe_factor("fundamental_momentum", factor_fundamental_momentum),
        _maybe_factor("surprise", factor_surprise),
        _maybe_factor("market_confirmation", factor_market_confirmation),
        _maybe_factor("quality", factor_quality),
    ]

    avail = [f for f in factors if f.available and f.score is not None]
    if not avail:
        return InvestmentSignal(
            rating="資料不足",
            conviction="low",
            factors=factors,
            rationale_zh="四項因子皆缺資料，無法計算綜合訊號。",
            as_of=date.today().isoformat(),
        )

    total_w = sum(float(raw_weights[f.name]) for f in avail)
    for f in factors:
        if f.available and f.score is not None:
            f.weight = float(raw_weights[f.name]) / total_w
        else:
            f.weight = 0.0

    score = sum((f.score or 0.0) * f.weight for f in avail)
    conviction = _conviction(len(avail), cfg)
    rating = _rating_from_score(score, cfg["rating_buckets"], conviction)
    rationale = _build_rationale(factors, score, conviction)

    return InvestmentSignal(
        score=round(score, 1),
        rating=rating,  # type: ignore[arg-type]
        conviction=conviction,  # type: ignore[arg-type]
        factors=factors,
        rationale_zh=rationale,
        as_of=date.today().isoformat(),
    )
