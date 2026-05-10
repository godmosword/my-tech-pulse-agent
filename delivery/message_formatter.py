"""HTML message formatter for #科技脈搏 Telegram channel."""

import os
import re
from datetime import datetime, timezone
from html import escape as _html_escape
from statistics import mean
from typing import Optional
from zoneinfo import ZoneInfo

from agents.earnings_agent import EarningsOutput
from agents.deep_insight_agent import InsightBrief
from agents.extractor_agent import ArticleSummary
from agents.synthesizer_agent import DigestOutput, StoryInsight

# Canonical Telegram digest: 📡 header, 🗞️ headline, 🧭 / 📈 / 🧠, themed ⭐ blocks, footer counts.
CANONICAL_DIGEST_FORMAT = "v1"
EXPERIMENTAL_DIGEST_FORMAT = "v2"

MAX_ITEMS_PER_DIGEST = int(os.getenv("MAX_ITEMS_PER_DIGEST", "6"))
MAX_SUMMARY_CHARS = int(os.getenv("MAX_SUMMARY_CHARS", "340"))
MAX_PER_CATEGORY = int(os.getenv("MAX_PER_CATEGORY", "3"))
UNSCORED_ALERT_RATIO = float(os.getenv("UNSCORED_ALERT_RATIO", "0.5"))
MAX_UNSCORED_TAIL = int(os.getenv("MAX_UNSCORED_TAIL", "3"))

MAX_THEMES_PER_DIGEST = int(os.getenv("MAX_THEMES_PER_DIGEST", "4"))
MAX_ITEMS_PER_THEME = int(os.getenv("MAX_ITEMS_PER_THEME", "3"))
MIN_ITEMS_PER_THEME = int(os.getenv("MIN_ITEMS_PER_THEME", "2"))
EARNINGS_THEME_RATIO_CAP = float(os.getenv("EARNINGS_THEME_RATIO_CAP", "0.4"))
TRANSLATION_TAG = "[📝 原文為英文，已由 Q-Silicon 深度編譯]"

_THEME_EMOJI: dict[str, str] = {
    "AI 基礎設施": "🧠",
    "技術研發": "🔬",
    "財報焦點": "💰",
    "雲端與企業軟體": "☁️",
    "消費電子": "📱",
    "電動車供應鏈": "⚡",
    "資本與投資": "💵",
    "產品與策略": "🚀",
    "政策與監管": "⚖️",
    "併購與整併": "🤝",
}


def _digest_header_display_dt(now: Optional[datetime]) -> datetime:
    """Pipeline instant shown in digest header as channel-local wall clock (default Taipei)."""
    if now is None:
        dt = datetime.now(timezone.utc)
    else:
        dt = now
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    tz_name = (os.getenv("DIGEST_HEADER_TIMEZONE", "Asia/Taipei") or "Asia/Taipei").strip()
    try:
        loc = ZoneInfo(tz_name)
    except Exception:
        loc = ZoneInfo("Asia/Taipei")
    return dt.astimezone(loc)


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
    if any("一" <= char <= "鿿" for char in keyword):
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


def escape(text: str) -> str:
    """HTML-escape dynamic text for Telegram HTML parse_mode."""
    return _html_escape(str(text), quote=False)


def _truncate(text: str, max_chars: int = MAX_SUMMARY_CHARS) -> str:
    if len(text) > max_chars:
        cut = text[:max_chars]
        last_space = cut.rfind(" ")
        if last_space > max_chars * 0.6:
            cut = cut[:last_space]
        return cut.rstrip(" ,.;:-") + "…"
    return text


def _truncate_words(text: str, max_words: int = 80) -> str:
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]) + "…"
    return text


def _confidence_badge(summary: ArticleSummary) -> str:
    status = getattr(summary, "score_status", "ok")
    if status in {"unscored", "fallback"}:
        return "⚠️ 待補驗證"
    if status == "low_score_fallback":
        return "🔴 低信心"
    why = getattr(summary, "why_it_matters", "") or ""
    if "[INFERRED]" in why:
        return "🔍 推測"
    confidence = getattr(summary, "confidence", "low")
    if confidence == "high":
        return "✅ 高信心"
    if confidence == "medium":
        return "🟡 中信心"
    return "🔴 低信心"


def _score_line(summary: ArticleSummary) -> str:
    """Return score + confidence badge line."""
    status = getattr(summary, "score_status", "ok")
    if status in {"unscored", "fallback"} or summary.score <= 0:
        return "⚪ 未評分  ·  ⚠️ 待補驗證"
    score_str = f"{summary.score:.1f}"
    badge = _confidence_badge(summary)
    if status == "low_score_fallback":
        return f"🟡 {score_str}  ·  {badge}"
    prefix = "📊" if summary.category == "earnings" else "⭐"
    return f"{prefix} {score_str}  ·  {badge}"


def _published_line(summary: ArticleSummary) -> str:
    ts = (getattr(summary, "published_at", "") or "").strip()
    if not ts:
        return "🕒 —"
    return f"🕒 {escape(ts[:16].replace('T', ' '))}"


def _tags(summary: ArticleSummary) -> str:
    parts: list[str] = [f"#{summary.category}"]
    raw_tag = re.sub(r"[^A-Za-z0-9]", "", summary.entity.replace(" ", ""))[:20]
    if raw_tag:
        parts.append(f"#{raw_tag}")
    return " ".join(parts)


def _source_link(summary: ArticleSummary) -> str:
    url = summary.source_url or ""
    name = escape(getattr(summary, "source_display_name", "") or summary.source_name or "source")
    if url:
        return f'<a href="{url}">{name}</a>'
    return name


def _compose_structured_summary(summary: ArticleSummary) -> str:
    """Compose display summary using structured fields with backward-compatible fallback."""
    fact = (getattr(summary, "what_happened", "") or "").strip()
    impact = (getattr(summary, "why_it_matters", "") or "").strip()

    if fact and impact:
        return f"{fact} {impact}"
    if fact:
        return fact
    return summary.summary


def _is_english_source(language: str) -> bool:
    return (language or "en").lower().startswith("en")


def _translation_tag_line(language: str) -> str:
    return escape(TRANSLATION_TAG) if _is_english_source(language) else ""


def _theme_section_header(theme: str) -> str:
    emoji = _THEME_EMOJI.get(theme, "📡")
    return f"\n━━━ {emoji} {escape(theme)} ━━━\n"


def _format_three_part_insight(
    *,
    insight: str,
    tech_rationale: str,
    implication: str,
    source_language: str = "en",
) -> list[str]:
    lines = [
        "<b>【核心洞見】</b>",
        escape(insight),
        "",
        "<b>【底層邏輯】</b>",
        escape(tech_rationale),
        "",
        "<b>【生態影響】</b>",
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
    source = f'<a href="{source_url}">{source_name}</a>' if source_url else source_name
    return [
        f"🧠 <b>{title}</b>",
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
    """Format one deep-tier InsightBrief as a standalone Telegram HTML message."""
    confidence = " <i>(低信心度)</i>" if brief.confidence == "low" else ""
    title = escape(brief.title)
    author = escape(brief.author or "unknown")
    source = escape(getattr(brief, "source_display_name", "") or brief.source_name)
    domain = escape(brief.domain)
    word_count = brief.word_count

    lines = [
        f"🧠 <b>{title}</b>{confidence}",
        f"<i>{author} · {source}</i>",
        "",
        *_format_three_part_insight(
            insight=brief.insight,
            tech_rationale=brief.tech_rationale,
            implication=brief.implication,
            source_language=getattr(brief, "source_language", "en"),
        ),
        "",
        f'#{domain}  <a href="{brief.url}">原文</a>  <i>{word_count}字</i>',
    ]
    if brief.cross_ref:
        lines.append("🔗 投資日報")
    return "\n".join(lines)


def _format_article_card(s: ArticleSummary) -> list[str]:
    """Format one article as an HTML card."""
    lines: list[str] = []
    lines.append(_score_line(s))
    title = escape(getattr(s, "title", "") or s.entity)
    lines.append(f"<b>{title}</b>")

    zh_summary = getattr(s, "zh_summary", None)
    if zh_summary:
        lines.append(f"\n💡 <i>{escape(zh_summary)}</i>")

    lines.append("")
    body = _truncate_words(_compose_structured_summary(s))
    lines.append(escape(body))
    if getattr(s, "history_context", ""):
        lines.append(f"↳ {escape(_truncate_words(s.history_context, 20))}")

    meta = f"{_published_line(s)}  {_tags(s)}"
    lines.append(meta)
    url = s.source_url or ""
    if url:
        lines.append(f'🔗 <a href="{url}">原文連結</a>')
    if s.cross_ref:
        lines.append("📌 投資日報")

    return lines


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
    """Format a curated digest of ArticleSummary items grouped by theme (HTML)."""
    date_str = _digest_header_display_dt(now).strftime("%Y/%m/%d %H:%M")

    ranked = sorted(summaries, key=lambda s: s.score, reverse=True)
    valid_ranked = [
        s for s in ranked
        if s.score > 0 and getattr(s, "score_status", "ok") not in {"fallback", "low_score_fallback"}
    ]
    low_score_fallbacks = [
        s for s in ranked if getattr(s, "score_status", "ok") == "low_score_fallback"
    ]
    unscored = [s for s in ranked if getattr(s, "score_status", "ok") in {"fallback", "unscored"}]
    fallback_items = low_score_fallbacks + unscored
    display_pool = valid_ranked[:MAX_ITEMS_PER_DIGEST * 2]

    groups = _select_by_theme(display_pool) if display_pool else []

    degradation = (len(fallback_items) / len(summaries)) if summaries else 0.0
    header = f"📡 <b>科技脈搏 · {escape(date_str)}</b>"
    if degradation > UNSCORED_ALERT_RATIO:
        header += "\n⚠️ 模型評分降級"

    lines: list[str] = [header, ""]

    if headline:
        lines.append(f"<b>🗞️ {escape(headline)}</b>")
        lines.append("")
    if narrative_excerpt:
        lines.append(escape(narrative_excerpt))
        lines.append("")

    if themes:
        lines.append("<b>🧭 今日主線</b>")
        for theme in themes[:3]:
            lines.append(f"• {escape(theme)}")
        lines.append("")

    # Skip market_takeaway if it's merely the start of narrative_excerpt
    _effective_market_takeaway = market_takeaway
    if market_takeaway and narrative_excerpt:
        prefix_len = min(50, len(market_takeaway))
        if narrative_excerpt.startswith(market_takeaway[:prefix_len]):
            _effective_market_takeaway = None
    if _effective_market_takeaway:
        lines.append("<b>📈 市場含義</b>")
        lines.append(escape(_effective_market_takeaway))
        lines.append("")

    if story_insights:
        lines.append("<b>🧠 深度洞察</b>")
        lines.append("")
        for story in story_insights[:3]:
            lines.extend(_format_story_insight(story))
            lines.append("")

    shown_items: list[ArticleSummary] = []
    for theme, items in groups:
        lines.append(_theme_section_header(theme))
        for s in items:
            lines.extend(_format_article_card(s))
            lines.append("")
            shown_items.append(s)

    shown_unscored: list[ArticleSummary] = []
    fallback_allowance = max(0, min(MAX_UNSCORED_TAIL, MAX_ITEMS_PER_DIGEST - len(shown_items)))
    if fallback_items and fallback_allowance:
        lines.append("<b>其他快訊</b>")
        for s in fallback_items[:fallback_allowance]:
            lines.extend(_format_article_card(s))
            lines.append("")
            shown_unscored.append(s)

    if shown_items:
        avg = mean(s.score for s in shown_items)
        n_total = len(shown_items) + len(shown_unscored)
        lines.append("─────────────────")
        lines.append(f"📊 本期共 {n_total} 則  ·  平均分數 {avg:.1f}")
        if groups:
            cat_str = "　".join(f"{theme} ×{len(items)}" for theme, items in groups)
            lines.append(f"📂 {cat_str}")
    elif shown_unscored:
        n = len(shown_unscored)
        if any(getattr(s, "score_status", "") == "low_score_fallback" for s in shown_unscored):
            lines.append(f"📊 本期低信心快訊 {n} 則")
        else:
            lines.append(f"📊 本期快訊 {n} 則")
    else:
        lines.append(f"今日 {total_fetched} 篇 → 過濾後 {total_after_filter} 篇")

    return "\n".join(lines)


def format_digest_v2(
    summaries: list[ArticleSummary],
    total_fetched: int,
    total_after_filter: int,
    story_insights: Optional[list[StoryInsight]] = None,
    now: Optional[datetime] = None,
) -> str:
    """Format digest in fixed v2 layout for Telegram HTML."""
    ranked = sorted(summaries, key=lambda s: s.score, reverse=True)
    top = ranked[:MAX_ITEMS_PER_DIGEST]

    quality = 0.0
    if total_fetched > 0:
        quality = min(100.0, max(0.0, (total_after_filter / total_fetched) * 100))

    date_str = _digest_header_display_dt(now).strftime("%Y/%m/%d %H:%M")
    header = [
        f"🧭 <b>科技脈搏 Digest v2 · {escape(date_str)}</b>",
        f"總篇數: {total_fetched}",
        f"過濾後篇數: {total_after_filter}",
        f"資料品質指標: {quality:.1f}%",
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
        takeaways.append(f"• {title} ({escape(item.category)})")
    while len(takeaways) < 3:
        takeaways.append("• 暫無更多高信號條目，持續追蹤中。")

    theme_groups: dict[str, list[ArticleSummary]] = {}
    for item in top:
        theme_groups.setdefault(item.category, []).append(item)

    themes = sorted(theme_groups.items(), key=lambda kv: max(x.score for x in kv[1]), reverse=True)[:4]
    theme_lines = ["<b>3) 主題區</b>"]
    for theme, items in themes:
        theme_lines.append(f"• <b>{escape(theme.replace('_', ' ').title())}</b>")
        for item in items[:2]:
            title = escape(getattr(item, "title", "") or item.entity)
            src = _source_link(item)
            theme_lines.append(f"  - {title} ｜ {src}")
    if len(theme_lines) == 1:
        theme_lines.append("• 今日主題資料不足。")

    cross_ref_items = [s for s in top if s.cross_ref]
    focus_lines = ["<b>4) 焦點追蹤</b>"]
    if cross_ref_items:
        for item in cross_ref_items[:5]:
            title = escape(getattr(item, "title", "") or item.entity)
            focus_lines.append(f"• {title} - 跨日延續議題")
    else:
        focus_lines.append("• 未偵測到跨日延續議題。")

    tomorrow_lines = [
        "<b>5) 尾段：明日觀察指標</b>",
        "• 財報節點：關注大型科技財報與指引變化。",
        "• 供應鏈訊號：關注 AI 伺服器與關鍵零組件交期。",
        "• 政策節點：追蹤監管與出口政策更新。",
    ]

    deep_lines: list[str] = []
    if story_insights:
        deep_lines.extend(["<b>深度洞察</b>", ""])
        for story in story_insights[:3]:
            deep_lines.extend(_format_story_insight(story))
            deep_lines.append("")

    return "\n".join(
        header
        + ["<b>1) Header</b>", "", "<b>2) 今日總覽</b>", headline, *takeaways, ""]
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
    """Format digest with env-based version switch (v1 default / v2 opt-in)."""
    fmt = os.getenv("DIGEST_FORMAT", CANONICAL_DIGEST_FORMAT).strip().lower()
    if fmt == EXPERIMENTAL_DIGEST_FORMAT:
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
    """Format an EarningsOutput for Telegram HTML."""
    lines = [
        f"<b>💰 財報速報 — {escape(earnings.company)}</b>",
        f"季度: {escape(earnings.quarter)}",
        "",
    ]

    if earnings.revenue.actual is not None:
        rev_line = f"營收: ${escape(f'{earnings.revenue.actual:,.2f}')}B"
        if earnings.revenue.estimate is not None:
            rev_line += f" (預期 ${escape(f'{earnings.revenue.estimate:,.2f}')}B)"
        if earnings.revenue.beat_pct is not None:
            beat = "超出" if earnings.revenue.beat_pct >= 0 else "低於"
            rev_line += f" {beat} {escape(f'{abs(earnings.revenue.beat_pct):.1f}')}%"
        lines.append(rev_line)

    if earnings.eps.actual is not None:
        eps_line = f"EPS: ${escape(f'{earnings.eps.actual:.2f}')}"
        if earnings.eps.estimate is not None:
            eps_line += f" (預期 ${escape(f'{earnings.eps.estimate:.2f}')})"
        lines.append(eps_line)

    if earnings.guidance_next_q is not None:
        lines.append(f"下季指引: ${escape(f'{earnings.guidance_next_q:,.2f}')}B")

    if earnings.key_quotes:
        lines.append("")
        lines.append("<b>重要引述:</b>")
        for quote in earnings.key_quotes[:2]:
            lines.append(f"> {escape(quote)}")

    lines.append("")
    lines.append(f"<i>來源: {escape(earnings.source)} | 信心: {escape(earnings.confidence)}</i>")

    if earnings.cross_ref:
        lines.append("<i>cross_ref: true — 已同步 #投資日報</i>")

    return "\n".join(lines)
