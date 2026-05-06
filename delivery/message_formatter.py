"""MarkdownV2 message formatter for #科技脈搏 Telegram channel."""

import os
import re
from datetime import datetime, timezone
from statistics import mean
from typing import Optional

from agents.earnings_agent import EarningsOutput
from agents.deep_insight_agent import InsightBrief
from agents.extractor_agent import ArticleSummary
from agents.synthesizer_agent import DigestOutput, StoryInsight

MAX_ITEMS_PER_DIGEST = int(os.getenv("MAX_ITEMS_PER_DIGEST", "6"))
# Raised default (340) reduces mid-sentence cuts in Telegram; split fact/impact lines were skipped to keep formatting simple.
MAX_SUMMARY_CHARS = int(os.getenv("MAX_SUMMARY_CHARS", "340"))
MAX_PER_CATEGORY = int(os.getenv("MAX_PER_CATEGORY", "3"))
UNSCORED_ALERT_RATIO = float(os.getenv("UNSCORED_ALERT_RATIO", "0.5"))
MAX_UNSCORED_TAIL = int(os.getenv("MAX_UNSCORED_TAIL", "3"))

MAX_THEMES_PER_DIGEST = int(os.getenv("MAX_THEMES_PER_DIGEST", "4"))
MAX_ITEMS_PER_THEME = int(os.getenv("MAX_ITEMS_PER_THEME", "3"))
MIN_ITEMS_PER_THEME = int(os.getenv("MIN_ITEMS_PER_THEME", "2"))
EARNINGS_THEME_RATIO_CAP = float(os.getenv("EARNINGS_THEME_RATIO_CAP", "0.4"))
TRANSLATION_TAG = "[📝 原文為英文，已由 Q-Silicon 深度編譯]"

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
        if any(_contains_theme_keyword(corpus, k) for k in keywords):
            return theme

    cat_map = {
        "product_launch": "產品與策略",
        "funding": "資本與投資",
        "acquisition": "併購與整併",
        "regulation": "政策與監管",
        "research": "技術研發",
    }
    return cat_map.get(summary.category, "其他焦點")


def _contains_theme_keyword(corpus: str, keyword: str) -> bool:
    keyword = keyword.lower()
    if any("\u4e00" <= char <= "\u9fff" for char in keyword):
        return keyword in corpus
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", corpus) is not None


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
    """Return `⭐ 8.3 *Title*` or `📊 8.3 *Title*` for earnings."""
    title = escape(getattr(summary, "title", "") or summary.entity)
    if getattr(summary, "score_status", "ok") in {"unscored", "fallback"} or summary.score <= 0:
        return f"⚪ 未評分 *{title}*"
    score_str = escape(f"{summary.score:.1f}")
    prefix = "📊" if summary.category == "earnings" else "⭐"
    return f"{prefix} {score_str} *{title}*"


def _verification_status(summary: ArticleSummary) -> str:
    if getattr(summary, "score_status", "ok") in {"unscored", "fallback"} or summary.score <= 0:
        return "⚠️ 待補驗證：模型評分缺失"
    confidence = getattr(summary, "confidence", "low")
    if confidence == "high":
        return "✅ 已驗證：高信心"
    if confidence == "medium":
        return "⚠️ 部分驗證：中信心"
    return "⚠️ 待補驗證：低信心"


def _published_line(summary: ArticleSummary) -> str:
    ts = (getattr(summary, "published_at", "") or "").strip()
    if not ts:
        return "🕒 發布時間：待補"
    return f"🕒 發布時間：{escape(ts[:19].replace('T', ' '))} UTC"


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
    if fact:
        return fact
    return summary.summary


def _source_link(summary: ArticleSummary) -> str:
    name = escape(getattr(summary, "source_display_name", "") or summary.source_name or "source")
    url = summary.source_url or ""
    if url:
        return f"[{name}]({url})"
    return name


def _is_english_source(language: str) -> bool:
    return (language or "en").lower().startswith("en")


def _translation_tag_line(language: str) -> str:
    return escape(TRANSLATION_TAG) if _is_english_source(language) else ""


def _format_three_part_insight(
    *,
    insight: str,
    tech_rationale: str,
    implication: str,
    source_language: str = "en",
) -> list[str]:
    lines = [
        "*【核心洞見】*",
        escape(insight),
        "",
        "*【底層邏輯】*",
        escape(tech_rationale),
        "",
        "*【生態影響】*",
        escape(implication),
    ]
    tag = _translation_tag_line(source_language)
    if tag:
        lines.extend(["", tag])
    return lines


def _format_story_insight(story: StoryInsight) -> list[str]:
    title = escape(story.title or story.entity or "Untitled")
    source_name = escape(story.source_display_name or story.source_name or "source")
    source_url = story.source_url or ""
    source = f"[{source_name}]({source_url})" if source_url else source_name
    return [
        f"🧠 *{title}*",
        source,
        "",
        *_format_three_part_insight(
            insight=story.insight or story.summary,
            tech_rationale=story.tech_rationale,
            implication=story.implication,
            source_language=story.source_language,
        ),
    ]


def format_insight_brief(brief: InsightBrief) -> str:
    """Format one deep-tier InsightBrief as a standalone Telegram message."""
    confidence = " _\\(低信心度\\)_" if brief.confidence == "low" else ""
    title = escape(brief.title)
    author = escape(brief.author or "unknown")
    source = escape(getattr(brief, "source_display_name", "") or brief.source_name)
    domain = escape(brief.domain)
    word_count = escape(str(brief.word_count))

    lines = [
        f"🧠 *{title}*{confidence}",
        f"_{author} · {source}_",
        "",
        *_format_three_part_insight(
            insight=brief.insight,
            tech_rationale=brief.tech_rationale,
            implication=brief.implication,
            source_language=getattr(brief, "source_language", "en"),
        ),
        "",
        f"\\#{domain}  [原文]({brief.url})  _{word_count}字_",
    ]
    if brief.cross_ref:
        lines.append("🔗 投資日報")
    return "\n".join(lines)


def _format_items_digest_v1(
    summaries: list[ArticleSummary],
    total_fetched: int,
    total_after_filter: int,
    themes: Optional[list[str]] = None,
    market_takeaway: Optional[str] = None,
    headline: Optional[str] = None,
    narrative_excerpt: Optional[str] = None,
    story_insights: Optional[list[StoryInsight]] = None,
    now: Optional[datetime] = None,
) -> str:
    """Format a curated digest of ArticleSummary items grouped by theme."""
    if now is None:
        now = datetime.now(timezone.utc)
    date_str = escape(now.strftime("%Y/%m/%d %H:%M"))

    ranked = sorted(summaries, key=lambda s: s.score, reverse=True)
    valid_ranked = [
        s for s in ranked
        if s.score > 0 and getattr(s, "score_status", "ok") != "fallback"
    ]
    unscored = [s for s in ranked if getattr(s, "score_status", "ok") == "fallback"]
    display_pool = valid_ranked[:MAX_ITEMS_PER_DIGEST * 2]

    groups = _select_by_theme(display_pool) if display_pool else []

    degradation = (len(unscored) / len(summaries)) if summaries else 0.0
    header = f"📡 *科技脈搏 · {date_str}*"
    if degradation > UNSCORED_ALERT_RATIO:
        header += "\n⚠️ 模型評分降級"

    lines: list[str] = [header, ""]

    if headline:
        lines.append(f"*🗞️ {escape(headline)}*")
        lines.append("")
    if narrative_excerpt:
        lines.append(escape(narrative_excerpt))
        lines.append("")

    if themes:
        lines.append("*🧭 今日主線*")
        for theme in themes[:3]:
            lines.append(f"• {escape(theme)}")
        lines.append("")

    if market_takeaway:
        lines.append("*📈 市場含義*")
        lines.append(escape(market_takeaway))
        lines.append("")

    if story_insights:
        lines.append("*🧠 深度洞察*")
        lines.append("")
        for story in story_insights[:3]:
            lines.extend(_format_story_insight(story))
            lines.append("")

    shown_items: list[ArticleSummary] = []
    for theme, items in groups:
        lines.append(f"*{escape(theme)}*")
        for s in items:
            lines.append(_score_line(s))
            lines.append(_verification_status(s))
            lines.append(_published_line(s))
            lines.append(escape(_truncate(_compose_structured_summary(s))))
            if getattr(s, "history_context", ""):
                lines.append(f"↳ {escape(_truncate(s.history_context, 140))}")
            meta = f"{_tags(s)}  {_source_link(s)}"
            if s.cross_ref:
                meta += "  🔗 投資日報"
            lines.append(meta)
            lines.append("")
            shown_items.append(s)

    shown_unscored: list[ArticleSummary] = []
    fallback_allowance = max(0, min(MAX_UNSCORED_TAIL, MAX_ITEMS_PER_DIGEST - len(shown_items)))
    if unscored and fallback_allowance:
        lines.append("*其他快訊*")
        for s in unscored[:fallback_allowance]:
            lines.append(_score_line(s))
            lines.append(_verification_status(s))
            lines.append(_published_line(s))
            lines.append(escape(_truncate(_compose_structured_summary(s))))
            if getattr(s, "history_context", ""):
                lines.append(f"↳ {escape(_truncate(s.history_context, 140))}")
            lines.append(_source_link(s))
            lines.append("")
            shown_unscored.append(s)

    if shown_items:
        avg = mean(s.score for s in shown_items)
        avg_str = escape(f"{avg:.1f}")
        n_themes = len(groups)
        n_scored = len(shown_items)
        n_unscored = len(shown_unscored)
        # Footer counts must match the average: average is only over scored theme items.
        parts: list[str] = [
            f"已評分 {escape(str(n_scored))} 則（平均 {avg_str}）",
        ]
        if n_unscored > 0:
            parts.append(f"附錄未評分 {escape(str(n_unscored))} 則")
        parts.append(f"主題區 {escape(str(n_themes))} 個")
        footer = "_" + " · ".join(parts) + "_"
        lines.append(footer)
    elif shown_unscored:
        lines.append(f"_快訊 {escape(str(len(shown_unscored)))} 則_")
    else:
        fetched_esc = escape(str(total_fetched))
        filtered_esc = escape(str(total_after_filter))
        lines.append(f"_今日 {fetched_esc} 篇 → 過濾後 {filtered_esc} 篇_")

    return "\n".join(lines)


def format_digest_v2(
    summaries: list[ArticleSummary],
    total_fetched: int,
    total_after_filter: int,
    story_insights: Optional[list[StoryInsight]] = None,
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

    deep_lines: list[str] = []
    if story_insights:
        deep_lines.extend(["*深度洞察*", ""])
        for story in story_insights[:3]:
            deep_lines.extend(_format_story_insight(story))
            deep_lines.append("")

    return "\n".join(
        header
        + [r"*1\) Header*", "", r"*2\) 今日總覽*", headline, *takeaways, ""]
        + deep_lines
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
    themes: Optional[list[str]] = None,
    market_takeaway: Optional[str] = None,
    headline: Optional[str] = None,
    narrative_excerpt: Optional[str] = None,
    story_insights: Optional[list[StoryInsight]] = None,
    now: Optional[datetime] = None,
) -> str:
    """Format digest with env-based version switch (v1 fallback / v2 opt-in)."""
    if os.getenv("DIGEST_FORMAT", "v1").lower() == "v2":
        return format_digest_v2(
            summaries,
            total_fetched,
            total_after_filter,
            story_insights=story_insights,
            now=now,
        )
    return _format_items_digest_v1(
        summaries,
        total_fetched,
        total_after_filter,
        themes=themes,
        market_takeaway=market_takeaway,
        headline=headline,
        narrative_excerpt=narrative_excerpt,
        story_insights=story_insights,
        now=now,
    )


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
