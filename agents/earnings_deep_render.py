"""Render earnings_v3 deep report Markdown (sections 1–6)."""

from __future__ import annotations

from datetime import datetime, timezone

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


def render_guidance_section(report: EarningsReport) -> str:
    g = report.guidance_capex
    if not g:
        wording = report.guidance.get("wording") if report.guidance else None
        if not wording:
            return "## 2. 前瞻指引與資本支出 (Guidance & CapEx)\n\n_本期未抽取到結構化指引。_\n"
        return (
            "## 2. 前瞻指引與資本支出 (Guidance & CapEx)\n\n"
            f"* **管理層展望：** {wording}\n"
        )
    low = _fmt_usd_b(g.next_q_revenue_low)
    high = _fmt_usd_b(g.next_q_revenue_high)
    capex = _fmt_usd_b(g.capex_amount)
    focus = g.capex_focus_zh or "—"
    vs_note = g.vs_consensus_note or "—"
    return "\n".join(
        [
            "## 2. 前瞻指引與資本支出 (Guidance & CapEx)",
            "",
            f"* **下季營收指引：** {low} - {high}（{vs_note}）",
            f"* **資本支出計畫 (CapEx)：** {capex}，主要用於 {focus}",
            f"* **管理層展望定調：** {g.outlook_tone}",
            "",
        ]
    )


def render_segments_section(report: EarningsReport) -> str:
    if not report.segments:
        return "## 3. 核心業務拆解 (Segment Breakdown)\n\n_本期未抽取到分部營收。_\n"
    lines = ["## 3. 核心業務拆解 (Segment Breakdown)", ""]
    for seg in report.segments:
        rev = _fmt_usd_b(seg.revenue)
        yoy = _fmt_pct(seg.yoy_pct) if seg.yoy_pct is not None else "—"
        driver = seg.driver_zh or "—"
        lines.append(f"* **{seg.name_zh}：** 營收 {rev} (YoY {yoy})。{driver}")
    lines.append("")
    return "\n".join(lines)


def render_call_section(report: EarningsReport) -> str:
    lines = ["## 4. 電話會議關鍵情報 (Earnings Call Insights)", ""]
    if report.transcript_status == "pending":
        lines.append("_逐字稿處理中；完成後將更新本節。_")
    elif report.transcript_status in ("skipped", "timeout"):
        lines.append("_本期未取得電話會議逐字稿。_")
    elif report.call_insights:
        ci = report.call_insights
        lines.append("* **🎙️ 管理層亮點 (Management Highlights)：**")
        if ci.highlights:
            for h in ci.highlights:
                lines.append(f"    * {h}")
        else:
            lines.append("    * —")
        lines.append("* **⚠️ Q&A 焦點與潛在紅旗 (Red Flags)：**")
        if ci.qa_red_flags:
            for f in ci.qa_red_flags:
                lines.append(f"    * {f}")
        else:
            lines.append("    * —")
    else:
        lines.append("_本期未取得電話會議逐字稿。_")
    lines.append("")
    return "\n".join(lines)


def render_health_section(report: EarningsReport) -> str:
    h = report.financial_health
    if not h:
        return "## 5. 護城河與財務健康度 (Moat & Financial Health)\n\n_資料不足。_\n"
    fcf = _fmt_usd_b(h.fcf)
    conv = _fmt_pct(h.fcf_conversion_pct) if h.fcf_conversion_pct is not None else "—"
    returns = h.shareholder_returns_zh or "—"
    return "\n".join(
        [
            "## 5. 護城河與財務健康度 (Moat & Financial Health)",
            "",
            f"* **自由現金流 (FCF)：** 本季 {fcf}，轉換率 {conv}",
            f"* **投入資本回報率 (ROIC) 趨勢：** {h.roic_trend}",
            f"* **股東回報計畫：** {returns}",
            "",
        ]
    )


def render_conclusion_section(report: EarningsReport) -> str:
    c = report.conclusion
    if not c:
        takeaway = report.investment_takeaway_zh or "—"
        return (
            "## 6. 投資結論與風險提示 (Conclusion & Risk Profile)\n\n"
            f"* **摘要：** {takeaway}\n"
        )
    watch = "\n".join(f"    * {w}" for w in c.watch_items_zh) if c.watch_items_zh else "    * —"
    return "\n".join(
        [
            "## 6. 投資結論與風險提示 (Conclusion & Risk Profile)",
            "",
            f"* **牛市觀點 (Bull Case)：** {c.bull_case_zh or '—'}",
            f"* **熊市觀點 (Bear Case)：** {c.bear_case_zh or '—'}",
            "* **後續觀察重點：**",
            watch,
            "",
        ]
    )


def render_deep_report_markdown(report: EarningsReport) -> str:
    mc = report.market_context
    generated = (
        mc.report_generated_at.strftime("%Y-%m-%d")
        if mc
        else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
    price = f"${mc.price_usd:.2f}" if mc and mc.price_usd is not None else "—"
    earn_date = mc.earnings_date if mc and mc.earnings_date else report.published_at.strftime("%Y-%m-%d")
    session = mc.session if mc else "unknown"
    session_zh = {"pre": "盤前", "post": "盤後", "unknown": "—"}.get(session, "—")

    parts = [
        f"# {report.ticker} {report.quarter_label} 財報深度解析與投資指引",
        "",
        f"**報告生成時間：** {generated} | **當前股價：** {price} | "
        f"**財報發布日：** {earn_date} ({session_zh})",
        "",
        "---",
        "",
    ]
    if report.scorecard:
        parts.append(render_scorecard_section(report.scorecard))
    else:
        parts.append("## 1. 核心財報數據\n\n（尚無 Scorecard 資料）\n")
    parts.append(render_guidance_section(report))
    parts.append(render_segments_section(report))
    parts.append(render_call_section(report))
    parts.append(render_health_section(report))
    parts.append(render_conclusion_section(report))
    return "\n".join(parts).strip() + "\n"
