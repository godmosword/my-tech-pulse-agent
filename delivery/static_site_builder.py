"""Phase 2: generate a daily static HTML report for GitHub Pages.

Writes docs/{YYYY-MM-DD}.html and updates docs/index.html redirect.
Activate by setting GITHUB_PAGES_URL in .env.
"""

import html
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.earnings_agent import EarningsOutput
from agents.extractor_agent import ArticleSummary

logger = logging.getLogger(__name__)

DOCS_DIR = Path(os.getenv("OUTPUT_DIR", "output")).parent / "docs"

_CATEGORY_EMOJI = {
    "product_launch": "🚀",
    "funding": "💰",
    "acquisition": "🤝",
    "earnings": "📊",
    "regulation": "⚖️",
    "research": "🔬",
    "other": "📰",
}

_SENTIMENT_COLOR = {
    "positive": "#22c55e",
    "negative": "#ef4444",
    "neutral": "#6b7280",
}


class StaticSiteBuilder:
    def __init__(self, docs_dir: Path = DOCS_DIR):
        self._docs_dir = Path(docs_dir)

    def build(
        self,
        summaries: list[ArticleSummary],
        earnings: list[EarningsOutput],
        date: datetime | None = None,
    ) -> Path:
        """Write daily HTML report. Returns the path written."""
        if date is None:
            date = datetime.now(timezone.utc)
        date_slug = date.strftime("%Y-%m-%d")
        self._docs_dir.mkdir(parents=True, exist_ok=True)
        out_path = self._docs_dir / f"{date_slug}.html"
        prev_date = (date - timedelta(days=1)).strftime("%Y-%m-%d")

        sorted_summaries = sorted(summaries, key=lambda s: s.score, reverse=True)
        grouped: dict[str, list[ArticleSummary]] = {}
        for s in sorted_summaries:
            grouped.setdefault(s.category, []).append(s)

        body_parts: list[str] = []

        # Earnings section
        if earnings:
            body_parts.append(_section_header("📊", "財報速報"))
            for e in earnings:
                body_parts.append(_earnings_card(e))

        # News sections grouped by category
        for category, items in grouped.items():
            emoji = _CATEGORY_EMOJI.get(category, "📰")
            label = category.replace("_", " ").title()
            body_parts.append(_section_header(emoji, label))
            for s in items:
                body_parts.append(_summary_card(s))

        body_html = "\n".join(body_parts)
        date_display = html.escape(date.strftime("%Y/%m/%d"))
        total = len(summaries) + len(earnings)

        page = _PAGE_TEMPLATE.format(
            date_display=date_display,
            date_slug=html.escape(date_slug),
            total=total,
            body=body_html,
            prev_date=html.escape(prev_date),
        )
        out_path.write_text(page, encoding="utf-8")
        logger.info("Static site written: %s", out_path)

        self._write_index(date_slug)
        return out_path

    def _write_index(self, latest_slug: str) -> None:
        index = self._docs_dir / "index.html"
        index.write_text(
            f'<!DOCTYPE html><html><head>'
            f'<meta http-equiv="refresh" content="0; url={html.escape(latest_slug)}.html">'
            f'</head><body><a href="{html.escape(latest_slug)}.html">今日報告</a></body></html>',
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

def _section_header(emoji: str, label: str) -> str:
    return f'<h2 class="section-header">{emoji} {html.escape(label)}</h2>'


def _score_badge(score: float) -> str:
    color = "#22c55e" if score >= 8 else "#f59e0b" if score >= 6 else "#6b7280"
    return f'<span class="score-badge" style="background:{color}">⭐ {score:.1f}</span>'


def _summary_card(s: ArticleSummary) -> str:
    title = getattr(s, "title", "") or s.entity
    url = s.source_url or "#"
    sentiment_color = _SENTIMENT_COLOR.get(s.sentiment, "#6b7280")
    cross_ref_tag = '<span class="cross-ref">🔗 投資日報</span>' if s.cross_ref else ""
    tags_html = " ".join(
        f'<span class="tag">#{html.escape(t)}</span>'
        for t in [s.category, s.entity[:20]] if t
    )
    facts_html = ""
    if s.key_facts:
        items = "".join(f"<li>{html.escape(f)}</li>" for f in s.key_facts[:3])
        facts_html = f"<ul class='key-facts'>{items}</ul>"

    return f"""
<div class="card">
  <div class="card-header">
    {_score_badge(s.score)}
    <span class="sentiment-dot" style="background:{sentiment_color}" title="{html.escape(s.sentiment)}"></span>
    <a href="{html.escape(url)}" target="_blank" rel="noopener" class="card-title">{html.escape(title)}</a>
    {cross_ref_tag}
  </div>
  <p class="summary">{html.escape(s.summary)}</p>
  {facts_html}
  <div class="card-footer">{tags_html}</div>
</div>"""


def _earnings_card(e: EarningsOutput) -> str:
    rev = ""
    if e.revenue.actual is not None:
        rev = f"<strong>營收</strong> ${e.revenue.actual:,.2f}B"
        if e.revenue.estimate is not None:
            rev += f" / 預期 ${e.revenue.estimate:,.2f}B"
        if e.revenue.beat_pct is not None:
            color = "#22c55e" if e.revenue.beat_pct >= 0 else "#ef4444"
            sign = "+" if e.revenue.beat_pct >= 0 else ""
            rev += f' <span style="color:{color}">({sign}{e.revenue.beat_pct:.1f}%)</span>'

    eps = ""
    if e.eps.actual is not None:
        eps = f"<strong>EPS</strong> ${e.eps.actual:.2f}"
        if e.eps.estimate is not None:
            eps += f" / 預期 ${e.eps.estimate:.2f}"

    quotes_html = ""
    if e.key_quotes:
        items = "".join(f"<blockquote>{html.escape(q)}</blockquote>" for q in e.key_quotes[:2])
        quotes_html = items

    confidence_color = "#22c55e" if e.confidence == "high" else "#f59e0b" if e.confidence == "medium" else "#ef4444"

    return f"""
<div class="card earnings-card">
  <div class="card-header">
    <span class="score-badge" style="background:#3b82f6">📊 {html.escape(e.company)}</span>
    <span class="quarter">{html.escape(e.quarter)}</span>
    <span class="confidence" style="color:{confidence_color}">信心: {html.escape(e.confidence)}</span>
  </div>
  <div class="financials">{rev}{"  " if rev and eps else ""}{eps}</div>
  {quotes_html}
  <div class="card-footer"><span class="tag">#earnings</span> <span class="source">{html.escape(e.source)}</span></div>
</div>"""


_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>科技脈搏 · {date_display}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           max-width: 860px; margin: 0 auto; padding: 1rem 1.5rem;
           background: #f8fafc; color: #1e293b; }}
    h1 {{ font-size: 1.6rem; margin-bottom: 0.25rem; }}
    .subtitle {{ color: #64748b; margin-bottom: 2rem; font-size: 0.9rem; }}
    .section-header {{ margin-top: 2rem; border-bottom: 2px solid #e2e8f0;
                       padding-bottom: 0.4rem; font-size: 1.15rem; }}
    .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
             padding: 1rem 1.25rem; margin: 0.75rem 0; }}
    .card-header {{ display: flex; align-items: center; gap: 0.5rem;
                    flex-wrap: wrap; margin-bottom: 0.5rem; }}
    .card-title {{ font-weight: 600; color: #0f172a; text-decoration: none; }}
    .card-title:hover {{ text-decoration: underline; }}
    .score-badge {{ font-size: 0.75rem; padding: 2px 8px; border-radius: 12px;
                    color: #fff; font-weight: 600; white-space: nowrap; }}
    .sentiment-dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
    .cross-ref {{ font-size: 0.75rem; color: #7c3aed; font-weight: 600; }}
    .summary {{ color: #334155; margin: 0.25rem 0 0.5rem; font-size: 0.95rem; }}
    .key-facts {{ color: #475569; font-size: 0.88rem; padding-left: 1.25rem; margin: 0.25rem 0; }}
    .card-footer {{ display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;
                    margin-top: 0.5rem; }}
    .tag {{ font-size: 0.75rem; background: #f1f5f9; color: #475569;
            padding: 2px 8px; border-radius: 4px; }}
    .source {{ font-size: 0.75rem; color: #94a3b8; }}
    .earnings-card {{ border-left: 4px solid #3b82f6; }}
    .financials {{ font-size: 0.95rem; margin: 0.5rem 0; }}
    .quarter {{ font-size: 0.85rem; color: #64748b; }}
    .confidence {{ font-size: 0.8rem; font-weight: 600; }}
    blockquote {{ border-left: 3px solid #e2e8f0; margin: 0.5rem 0;
                  padding-left: 0.75rem; color: #475569; font-style: italic;
                  font-size: 0.9rem; }}
    .footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e2e8f0;
               color: #94a3b8; font-size: 0.85rem; display: flex; gap: 1rem; }}
  </style>
</head>
<body>
  <h1>📡 科技脈搏</h1>
  <div class="subtitle">{date_display} &nbsp;·&nbsp; {total} 篇報導</div>
  {body}
  <div class="footer">
    <span>科技脈搏 daily digest</span>
    <a href="{prev_date}.html">← 昨日報告</a>
  </div>
</body>
</html>
"""
