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




def _compose_structured_summary(summary: ArticleSummary) -> str:
    """Compose display summary using structured fields with backward-compatible fallback."""
    fact = (getattr(summary, "what_happened", "") or "").strip()
    impact = (getattr(summary, "why_it_matters", "") or "").strip()

    if fact and impact:
        return f"{fact} {impact}"
    if fact and not impact:
        return f"{fact}（資訊不足）"
    return summary.summary


def _source_link(summary: ArticleSummary) -> str:
    name = escape(summary.source_name or "source")
    url = summary.source_url or ""
    if url:
        return f"[{name}]({url})"
    return name


def format_items_digest(
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
        composed_summary = _compose_structured_summary(s)
        summary_text = escape(_truncate(composed_summary))
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
