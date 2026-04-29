"""MarkdownV2 message formatter for #科技脈搏 Telegram channel."""

import os
import re
from datetime import datetime, timezone
from statistics import mean
from typing import Optional

from agents.earnings_agent import EarningsOutput
from agents.extractor_agent import ArticleSummary
from agents.synthesizer_agent import DigestOutput

MAX_ITEMS_PER_DIGEST = int(os.getenv("MAX_ITEMS_PER_DIGEST", "10"))
MAX_SUMMARY_CHARS = int(os.getenv("MAX_SUMMARY_CHARS", "150"))
MAX_PER_CATEGORY = int(os.getenv("MAX_PER_CATEGORY", "3"))

MAX_THEMES_PER_DIGEST = int(os.getenv("MAX_THEMES_PER_DIGEST", "4"))
MAX_ITEMS_PER_THEME = int(os.getenv("MAX_ITEMS_PER_THEME", "3"))
MIN_ITEMS_PER_THEME = int(os.getenv("MIN_ITEMS_PER_THEME", "2"))
EARNINGS_THEME_RATIO_CAP = float(os.getenv("EARNINGS_THEME_RATIO_CAP", "0.4"))

_THEME_KEYWORDS: dict[str, list[str]] = {
    "AI 基礎設施": ["ai", "gpu", "chip", "晶片", "資料中心", "datacenter", "nvidia", "amd", "hbm"],
    "雲端與企業軟體": ["cloud", "saas", "雲端", "azure", "aws", "gcp", "oracle", "enterprise", "crm"],
    "消費電子": ["iphone", "android", "pc", "wearable", "consumer", "手機", "筆電", "平板", "耳機"],
    "電動車供應鏈": ["ev", "electric vehicle", "battery", "tesla", "自駕", "電動車", "車用", "充電", "鋰電"],
}


def _theme_key(summary: ArticleSummary) -> str:
    if summary.category == "earnings":
        return "財報焦點"

    corpus = " ".join([summary.entity, summary.summary, getattr(summary, "title", "")]).lower()
    for theme, keywords in _THEME_KEYWORDS.items():
        if any(k.lower() in corpus for k in keywords):
            return theme

    cat_map = {
        "product_launch": "產品與策略",
        "funding": "資本與投資",
        "acquisition": "併購與整併",
        "regulation": "政策與監管",
        "research": "技術研發",
    }
    return cat_map.get(summary.category, "其他焦點")


def _theme_rank_score(items: list[ArticleSummary]) -> float:
    avg_score = mean(s.score for s in items)
    max_score = max(s.score for s in items)
    size_weight = min(len(items), MAX_ITEMS_PER_THEME) / MAX_ITEMS_PER_THEME
    return avg_score * 0.45 + max_score * 0.35 + size_weight * 10 * 0.20


def _select_by_theme(ranked: list[ArticleSummary]) -> list[tuple[str, list[ArticleSummary]]]:
    grouped: dict[str, list[ArticleSummary]] = {}
    for item in ranked:
        key = _theme_key(item)
        grouped.setdefault(key, []).append(item)

    ordered_themes = sorted(grouped.items(), key=lambda kv: _theme_rank_score(kv[1]), reverse=True)
    ordered_themes = ordered_themes[:MAX_THEMES_PER_DIGEST]

    max_total = min(MAX_ITEMS_PER_DIGEST, MAX_THEMES_PER_DIGEST * MAX_ITEMS_PER_THEME)
    earnings_cap = max(1, int(max_total * EARNINGS_THEME_RATIO_CAP))

    selected: list[tuple[str, list[ArticleSummary]]] = []
    total_used = 0
    for theme, items in ordered_themes:
        ordered_items = sorted(items, key=lambda s: s.score, reverse=True)
        allowance = min(MAX_ITEMS_PER_THEME, len(ordered_items), max_total - total_used)
        if allowance <= 0:
            break
        if theme == "財報焦點":
            allowance = min(allowance, earnings_cap)

        min_allowance = min(MIN_ITEMS_PER_THEME, len(ordered_items), allowance)
        allowance = max(min_allowance, allowance)
        chosen = ordered_items[:allowance]
        if not chosen:
            continue
        selected.append((theme, chosen))
        total_used += len(chosen)
        if total_used >= max_total:
            break

    return selected

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


def format_items_digest(
    summaries: list[ArticleSummary],
    total_fetched: int,
    total_after_filter: int,
    digest: Optional[DigestOutput] = None,
    now: Optional[datetime] = None,
) -> str:
    """Format a ranked digest of ArticleSummary items."""
    if now is None:
        now = datetime.now(timezone.utc)
    date_str = escape(now.strftime("%Y/%m/%d %H:%M"))

    ranked = sorted(summaries, key=lambda s: s.score, reverse=True)
    themed_items = _select_by_theme(ranked)

    lines: list[str] = [
        f"📡 *科技脈搏 · {date_str}*",
        "",
    ]

    for theme, items in themed_items:
        lines.append(f"## {escape(theme)}")
        lines.append("")
        for s in items:
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
