"""Render earnings_v3 deep report Markdown (section §1 scorecard)."""

from __future__ import annotations

from datetime import datetime

from agents.earnings_models import EarningsReport
from agents.earnings_v3_models import MetricValue, Scorecard


def _fmt_usd_b(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1e9:
        return f"${value / 1e9:.2f}B"
    if abs(value) >= 1e6:
        return f"${value / 1e6:.2f}M"
    return f"${value:,.0f}"


def _fmt_eps(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.1f}%"


def _fmt_surprise(row: MetricValue | None) -> str:
    if row is None:
        return "—"
    if row.accounting_basis == "Mixed":
        return "基準不一致"
    if row.surprise_pct is None:
        return "—"
    icon = "🟢" if row.surprise_pct > 0 else "🔴" if row.surprise_pct < 0 else "⚪"
    return f"{icon} {row.surprise_pct:+.1f}%"


def _row_line(
    label: str,
    row: MetricValue | None,
    *,
    money: bool = False,
    pct: bool = False,
) -> str:
    if row is None:
        return f"| **{label}** | — | — | — | — |"
    actual = _fmt_usd_b(row.actual) if money else _fmt_pct(row.actual) if pct else _fmt_eps(row.actual)
    estimate = _fmt_usd_b(row.estimate) if money else _fmt_pct(row.estimate) if pct else _fmt_eps(row.estimate)
    basis_note = ""
    if row.accounting_basis == "Mixed":
        basis_note = " _(基準不一致，不計驚喜度)_"
    elif row.accounting_basis not in ("Unknown",):
        basis_note = f" _({row.accounting_basis})_"
    return (
        f"| **{label}**{basis_note} | {actual} | {estimate} | {_fmt_surprise(row)} | "
        f"{_fmt_pct(row.yoy_pct)} |"
    )


def render_scorecard_section(scorecard: Scorecard) -> str:
    lines = [
        "## 1. 核心財報數據 (The Scorecard)",
        "",
        "| 關鍵指標 | 實際公布值 (Actual) | 華爾街預期 (Estimate) | 驚喜度 (Surprise) | YoY 年增率 |",
        "| :--- | :--- | :--- | :--- | :--- |",
        _row_line("總營收 (Revenue)", scorecard.revenue, money=True),
        _row_line("每股盈餘 (EPS)", scorecard.eps, money=False),
        _row_line("毛利率 (Gross Margin)", scorecard.gross_margin_pct, pct=True),
        "",
        f"**[簡評]：** {scorecard.headline_verdict}",
        "",
    ]
    return "\n".join(lines)


def render_deep_report_markdown(report: EarningsReport) -> str:
    """Full v3 markdown; sections 2–6 filled as stubs until B–D land."""
    mc = report.market_context
    generated = (
        mc.report_generated_at.strftime("%Y-%m-%d")
        if mc
        else datetime.utcnow().strftime("%Y-%m-%d")
    )
    price = f"${mc.price_usd:.2f}" if mc and mc.price_usd is not None else "—"
    earn_date = mc.earnings_date if mc and mc.earnings_date else report.published_at.strftime("%Y-%m-%d")
    session = mc.session if mc else "unknown"
    session_zh = {"pre": "盤前", "post": "盤後", "unknown": "—"}.get(session, "—")

    header = [
        f"# {report.ticker} {report.quarter_label} 財報深度解析與投資指引",
        "",
        f"**報告生成時間：** {generated} | **當前股價：** {price} | "
        f"**財報發布日：** {earn_date} ({session_zh})",
        "",
        "---",
        "",
    ]

    body: list[str] = list(header)
    if report.scorecard:
        body.append(render_scorecard_section(report.scorecard))
    else:
        body.append("## 1. 核心財報數據\n\n（尚無 Scorecard 資料）\n")

    if report.investment_takeaway_zh:
        body.extend(["", f"**分析摘要：** {report.investment_takeaway_zh}", ""])

    if report.transcript_status == "pending":
        body.extend(
            [
                "## 4. 電話會議關鍵情報",
                "",
                "_逐字稿處理中；完成後將更新本節。_",
                "",
            ]
        )
    elif report.transcript_status in ("skipped", "timeout"):
        body.extend(
            [
                "## 4. 電話會議關鍵情報",
                "",
                "_本期未取得電話會議逐字稿。_",
                "",
            ]
        )

    return "\n".join(body).strip() + "\n"
