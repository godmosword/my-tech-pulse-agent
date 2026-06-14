"""Multi-quarter earnings trend series from SEC XBRL company facts."""

from __future__ import annotations

from typing import Optional

from agents.earnings_v3_models import EarningsTrend, MetricTrend, QuarterPoint
from agents.scorecard_builder import compute_yoy_pct
from sources.sec_xbrl_fetcher import SecXbrlFetcher


def _to_point(row: dict) -> QuarterPoint:
    return QuarterPoint(
        fiscal_year=int(row["fy"]),
        fiscal_period=str(row.get("fp") or "").upper(),
        period_end=str(row.get("end")) if row.get("end") else None,
        value=float(row["val"]) if row.get("val") is not None else None,
        filed=str(row.get("filed")) if row.get("filed") else None,
    )


def _direction(points: list[QuarterPoint]) -> str:
    vals = [p.value for p in points[-3:] if p.value is not None]
    if len(vals) < 3:
        return "資料不足"
    if vals[2] > vals[1] > vals[0]:
        return "擴張"
    if vals[2] < vals[1] < vals[0]:
        return "收縮"
    return "持平"


def _find_prior_year_same_q(points: list[QuarterPoint], latest: QuarterPoint) -> Optional[float]:
    for p in points:
        if p.fiscal_year == latest.fiscal_year - 1 and p.fiscal_period == latest.fiscal_period:
            return p.value
    return None


def build_metric_trend(metric: str, label_zh: str, rows: list[dict]) -> MetricTrend:
    points = [_to_point(r) for r in rows]
    yoy = qoq = None
    direction = _direction(points)
    if points:
        latest = points[-1]
        prior_y = _find_prior_year_same_q(points, latest)
        if latest.value is not None and prior_y is not None:
            yoy = compute_yoy_pct(latest.value, prior_y)
        if len(points) >= 2 and latest.value is not None and points[-2].value is not None:
            qoq = compute_yoy_pct(latest.value, points[-2].value)
    return MetricTrend(
        metric=metric,
        label_zh=label_zh,
        points=points,
        yoy_pct=yoy,
        qoq_pct=qoq,
        direction=direction,  # type: ignore[arg-type]
    )


def _gross_margin_trend(series: dict[str, list[dict]]) -> MetricTrend | None:
    gp = {str(r.get("end")): r for r in series.get("gross_profit", [])}
    rev = {str(r.get("end")): r for r in series.get("revenue", [])}
    rows: list[dict] = []
    for end in sorted(set(gp) & set(rev)):
        g, r = gp[end], rev[end]
        if r.get("val") in (None, 0):
            continue
        rows.append({
            "fy": g.get("fy"),
            "fp": g.get("fp"),
            "end": end,
            "filed": g.get("filed"),
            "val": round(float(g["val"]) / float(r["val"]) * 100.0, 2),
        })
    if not rows:
        return None
    return build_metric_trend("gross_margin", "毛利率(%)", rows)


def build_earnings_trend(
    xbrl: SecXbrlFetcher, company_facts: dict, *, max_quarters: int = 8
) -> EarningsTrend:
    series = xbrl.normalize_quarter_series(company_facts, max_quarters=max_quarters)
    trends: list[MetricTrend] = []
    for metric in ("revenue", "eps_diluted", "net_income", "operating_income"):
        rows = series.get(metric)
        if rows:
            trends.append(build_metric_trend(metric, rows[0]["label_zh"], rows))
    gm = _gross_margin_trend(series)
    if gm:
        trends.append(gm)
    covered = max((len(t.points) for t in trends), default=0)
    return EarningsTrend(trends=trends, quarters_covered=covered)
