"""MarkdownV2 message formatter for #科技脈搏 Telegram channel."""

import os
import re
from datetime import datetime, timezone
from typing import Optional

from agents.earnings_agent import EarningsOutput
from agents.extractor_agent import ArticleSummary

MAX_ITEMS_PER_DIGEST = int(os.getenv("MAX_ITEMS_PER_DIGEST", "10"))
MAX_SUMMARY_CHARS = int(os.getenv("MAX_SUMMARY_CHARS", "150"))
MAX_PER_CATEGORY = int(os.getenv("MAX_PER_CATEGORY", "3"))

# All MarkdownV2 special characters that must be escaped
_MV2_SPECIAL = r"\_*[]()~`>#+-=|{}.!"


def escape(text: str) -> str:
    """Escape MarkdownV2 special characters in dynamic text."""
    return "".join(f"\\{c}" if c in _MV2_SPECIAL else c for c in str(text))


def _truncate(text: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    if len(text) > max_chars:
        cut = text[:max_chars]
        last_space = cut.rfind(" ")
        if last_space > max_chars * 0.6:
            cut = cut[:last_space]
        return cut.rstrip(" ,.;:-") + "…"
    return text


def _score_line(summary: ArticleSummary) -> str:
    """Return `⭐ 8.3 *Title*` or `📊 *Title*` for earnings."""
    if summary.category == "earnings":
        prefix = "📊"
        title_part = f"*{escape(summary.entity)} — {escape(summary.summary[:60])}*"
        return f"{prefix} {title_part}"
    score_str = escape(f"{summary.score:.1f}")
    title = escape(getattr(summary, "title", "") or summary.entity)
    return f"⭐ {score_str} *{title}*"


def _tags(summary: ArticleSummary) -> str:
    parts: list[str] = []
    cat = summary.category.replace("_", "\\_")
    parts.append(f"\\#{cat}")
    raw_tag = summary.entity.replace(" ", "")
    entity_tag = re.sub(r"[^A-Za-z0-9]", "", raw_tag)[:20]
    if entity_tag:
        parts.append(f"\\#{escape(entity_tag)}")
    return " ".join(parts)


def _source_link(summary: ArticleSummary) -> str:
    name = escape(summary.source_name or "source")
    url = summary.source_url or ""
    if url:
        return f"[{name}]({url})"
    return name


def _format_items_digest_v1(
    summaries: list[ArticleSummary],
    total_fetched: int,
    total_after_filter: int,
    now: Optional[datetime] = None,
) -> str:
    """Format a ranked digest of ArticleSummary items."""
    if now is None:
        now = datetime.now(timezone.utc)
    date_str = escape(now.strftime("%Y/%m/%d %H:%M"))

    ranked = sorted(summaries, key=lambda s: s.score, reverse=True)
    top: list[ArticleSummary] = []
    cat_counts: dict[str, int] = {}
    for item in ranked:
        cat = item.category
        if cat_counts.get(cat, 0) >= MAX_PER_CATEGORY:
            continue
        top.append(item)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        if len(top) >= MAX_ITEMS_PER_DIGEST:
            break

    lines: list[str] = [
        f"📡 *科技脈搏 · {date_str}*",
        "",
    ]

    for s in top:
        lines.append(_score_line(s))
        summary_text = escape(_truncate(s.summary))
        lines.append(summary_text)
        tag_str = _tags(s)
        src_str = _source_link(s)
        meta = f"{tag_str}  {src_str}"
        if s.cross_ref:
            meta += "  🔗 投資日報"
        lines.append(meta)
        lines.append("")

    fetched_esc = escape(str(total_fetched))
    filtered_esc = escape(str(total_after_filter))
    lines.append(f"_今日 {fetched_esc} 篇 → 過濾後 {filtered_esc} 篇_")

    return "\n".join(lines)


def format_digest_v2(
    summaries: list[ArticleSummary],
    total_fetched: int,
    total_after_filter: int,
    now: Optional[datetime] = None,
) -> str:
    """Format digest in fixed v2 layout for Telegram MarkdownV2."""
    if now is None:
        now = datetime.now(timezone.utc)

    ranked = sorted(summaries, key=lambda s: s.score, reverse=True)
    top = ranked[:MAX_ITEMS_PER_DIGEST]

    quality = 0.0
    if total_fetched > 0:
        quality = min(100.0, max(0.0, (total_after_filter / total_fetched) * 100))

    date_str = escape(now.strftime("%Y/%m/%d %H:%M"))
    header = [
        f"🧭 *科技脈搏 Digest v2 · {date_str}*",
        f"總篇數: {escape(str(total_fetched))}",
        f"過濾後篇數: {escape(str(total_after_filter))}",
        f"資料品質指標: {escape(f'{quality:.1f}')}%",
        "",
    ]

    lead = top[0] if top else None
    headline = "今日市場焦點延續科技與供應鏈雙主軸。"
    if lead:
        title = escape(getattr(lead, "title", "") or lead.entity)
        headline = f"{title} 成為今日 headline，情緒偏 {escape(lead.sentiment)}。"

    takeaways = []
    for item in top[:3]:
        title = escape(getattr(item, "title", "") or item.entity)
        takeaways.append(f"• {title} \\({escape(item.category)}\\)")
    while len(takeaways) < 3:
        takeaways.append("• 暫無更多高信號條目，持續追蹤中。")

    theme_groups: dict[str, list[ArticleSummary]] = {}
    for item in top:
        theme_groups.setdefault(item.category, []).append(item)

    themes = sorted(theme_groups.items(), key=lambda kv: max(x.score for x in kv[1]), reverse=True)[:4]
    theme_lines = [r"*3\) 主題區*"]
    for theme, items in themes:
        theme_lines.append(f"• *{escape(theme.replace('_', ' ').title())}*")
        for item in items[:2]:
            title = escape(getattr(item, "title", "") or item.entity)
            src = _source_link(item)
            theme_lines.append(f"  - {title} ｜ {src}")
    if len(theme_lines) == 1:
        theme_lines.append("• 今日主題資料不足。")

    cross_ref_items = [s for s in top if s.cross_ref]
    focus_lines = [r"*4\) 焦點追蹤*"]
    if cross_ref_items:
        for item in cross_ref_items[:5]:
            title = escape(getattr(item, "title", "") or item.entity)
            focus_lines.append(f"• {title} \\\\- 跨日延續議題")
    else:
        focus_lines.append("• 未偵測到跨日延續議題。")

    tomorrow_lines = [
        r"*5\) 尾段：明日觀察指標*",
        "• 財報節點：關注大型科技財報與指引變化。",
        "• 供應鏈訊號：關注 AI 伺服器與關鍵零組件交期。",
        "• 政策節點：追蹤監管與出口政策更新。",
    ]

    return "\n".join(
        header
        + [r"*1\) Header*", "", r"*2\) 今日總覽*", headline, *takeaways, ""]
        + theme_lines
        + [""]
        + focus_lines
        + [""]
        + tomorrow_lines
    )


def format_items_digest(
    summaries: list[ArticleSummary],
    total_fetched: int,
    total_after_filter: int,
    now: Optional[datetime] = None,
) -> str:
    """Format digest with env-based version switch (v1 fallback / v2 opt-in)."""
    if os.getenv("DIGEST_FORMAT", "v1").lower() == "v2":
        return format_digest_v2(summaries, total_fetched, total_after_filter, now=now)
    return _format_items_digest_v1(summaries, total_fetched, total_after_filter, now=now)


def format_earnings(earnings: EarningsOutput) -> str:
    """Format an EarningsOutput for Telegram MarkdownV2."""
    lines = [
        f"*💰 財報速報 — {escape(earnings.company)}*",
        f"季度: {escape(earnings.quarter)}",
        "",
    ]

    if earnings.revenue.actual is not None:
        rev_line = f"營收: \\${escape(f'{earnings.revenue.actual:,.2f}')}B"
        if earnings.revenue.estimate is not None:
            rev_line += f" \\(預期 \\${escape(f'{earnings.revenue.estimate:,.2f}')}B\\)"
        if earnings.revenue.beat_pct is not None:
            beat = "超出" if earnings.revenue.beat_pct >= 0 else "低於"
            rev_line += f" {beat} {escape(f'{abs(earnings.revenue.beat_pct):.1f}')}%"
        lines.append(rev_line)

    if earnings.eps.actual is not None:
        eps_line = f"EPS: \\${escape(f'{earnings.eps.actual:.2f}')}"
        if earnings.eps.estimate is not None:
            eps_line += f" \\(預期 \\${escape(f'{earnings.eps.estimate:.2f}')}\\)"
        lines.append(eps_line)

    if earnings.guidance_next_q is not None:
        lines.append(f"下季指引: \\${escape(f'{earnings.guidance_next_q:,.2f}')}B")

    if earnings.key_quotes:
        lines.append("")
        lines.append("*重要引述:*")
        for quote in earnings.key_quotes[:2]:
            lines.append(f"> {escape(quote)}")

    lines.append("")
    lines.append(f"_來源: {escape(earnings.source)} \\| 信心: {escape(earnings.confidence)}_")

    if earnings.cross_ref:
        lines.append("_cross\\_ref: true \\— 已同步 \\#投資日報_")

    return "\n".join(lines)
