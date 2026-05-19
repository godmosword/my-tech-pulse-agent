"""Layer 1 agent: per-article structured summary with confidence scoring."""

import json
import logging
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from llm.gemini_client import GEMINI_MODEL, generate_json, make_client
from llm.localization import strip_weak_summary_openers, to_traditional_zh_tw

logger = logging.getLogger(__name__)

MODEL = GEMINI_MODEL


def _extractor_input_char_limit() -> int:
    return int(os.getenv("EXTRACTOR_MAX_INPUT_CHARS", "6000"))


SYSTEM_PROMPT = """\
You are a tech news extractor. Your only job is to extract structured information from a given article.

Rules:
- Only summarize what is explicitly stated in the source. Do not infer or add context.
- Never fabricate quotes, statistics, or claims not present in the article.
- Use confidence = "high" when all fields are directly supported by the text.
- Use confidence = "medium" when some fields require mild interpretation.
- Use confidence = "low" when the source is thin or ambiguous.
- Output valid JSON only. No markdown, no explanation.
"""

EXTRACTION_PROMPT = """\
Extract the following fields from the article below and return a single JSON object.

Fields:
- entity: primary company or technology mentioned (string)
- summary: max 2 sentence factual summary, no editorializing (string, fallback compatibility)
- what_happened: up to 3 concise sentences with objective facts only (numbers, timing, concrete actions) (string)
- why_it_matters: second sentence describing impact on industry/supply chain/valuation when supported; empty if insufficient info (string)
- category: one of ["product_launch", "funding", "acquisition", "earnings", "regulation", "research", "other"]
- key_facts: list of up to 5 specific factual claims (list of strings)
- sentiment: one of ["positive", "negative", "neutral"]
- confidence: one of ["high", "medium", "low"]
- cross_ref: true if this story is likely relevant to investment decisions (bool)
- tldr_tier: one of ["headline", "deep_dive", "tool_or_repo", "number", "standard"].
  Use "headline" for the day's top news (major announcement, earnings beat, product launch).
  Use "deep_dive" for analysis/explainer pieces with multi-step reasoning.
  Use "tool_or_repo" for new open-source projects, libraries, dev tools, SDKs, GitHub releases.
  Use "number" when the core news is a striking standalone statistic / chart / benchmark result.
  Use "standard" for everything else. When in doubt, "standard".
- hook: one-sentence reader hook in Traditional Chinese (繁體中文), ≤24 characters.
  Should answer "為什麼今天要讀這篇？" — the punchline, not a category label.
  Empty string when the article is too thin to support a hook.

Formatting constraints for structured summary fields:
- what_happened must be one sentence of objective facts only, and MUST include at least one verifiable anchor from the article (company or product name, or a number/date that appears verbatim in the text). If the source truly lacks all three, write the shortest faithful fact sentence and set confidence to "low".
- why_it_matters should be one sentence on implications for industry/supply chain/valuation only when the article supports it.
- If implication evidence is insufficient, set why_it_matters to an empty string.
- Keep summary as a compatible fallback narrative.
- Keep every field concise so the JSON object can complete within the token limit.

Quality gate (CRITICAL — set confidence="low" and why_it_matters="" if ANY apply):
- Article is a newsletter roundup, link collection, "what we're reading", "community wisdom", or weekly digest of other people's posts.
- Article is purely advisory / opinion ("how to", "what to do when", "thoughts on") with no original facts, numbers, or named decisions.
- key_facts cannot include at least 1 specific number, company name, or product version pulled directly from the article body (not the title alone).
- Title contains any of: "roundup", "wisdom", "best of", "this week in", "what we learned", "what we're reading".

Additionally, generate Traditional Chinese reader-facing copy:
- Field name: zh_title
- A concise Traditional Chinese (繁體中文) headline, ≤ 28 characters, that conveys the same news as the original title.
- Must mention the primary entity (company / product / person) when present in the article.
- No trailing punctuation, no quote marks, no editorializing adjectives ("驚爆", "重磅"). Write like a serious tech editor.
- If the source title is already in Traditional Chinese and reads naturally, you may reuse it verbatim.
- If the article is too thin to support a faithful headline, set zh_title to null.

- Field name: zh_summary
- Exactly 2 sentences in Traditional Chinese (繁體中文)
- Sentence 1: Explain WHAT was achieved and WHY it is technically significant. MUST cite at least one specific entity, number, or product mentioned in the article body — not generic phrases like "實用見解" or "重要討論".
- Sentence 2: Explain the practical implication for engineers or investors
- Each sentence must be under 60 Chinese characters
- If the article lacks concrete facts (e.g. it is a roundup or pure opinion), set BOTH zh_summary and zh_body to null (do not invent).
- Do NOT translate the title; write naturally as a tech editor would

- Field name: zh_body
- Full Traditional Chinese translation of the article's factual narrative for a professional reader.
- Translate and weave together: what_happened, why_it_matters (if non-empty), and the most important key_facts (do not omit contradictory facts when present).
- Use 2–5 short paragraphs separated by a single blank line (\\n\\n). Total roughly 350–900 Chinese characters unless the source is very thin.
- Preserve English product names, tickers, units, and URLs when translation would reduce precision.
- Must not introduce facts absent from the English fields above.

Article title: {title}
Article source: {source}
Article text:
{text}
"""


class ArticleSummary(BaseModel):
    entity: str
    summary: str
    what_happened: str = ""
    why_it_matters: str = ""
    category: Literal["product_launch", "funding", "acquisition", "earnings", "regulation", "research", "other"]
    key_facts: list[str] = Field(default_factory=list)
    sentiment: Literal["positive", "negative", "neutral"]
    confidence: Literal["high", "medium", "low"]
    cross_ref: bool = False
    source_url: str = ""
    source_name: str = ""
    source_display_name: str = ""
    source_language: str = "en"
    title: str = ""
    score: float = 0.0  # propagated from Scorer; 0.0 = unscored
    score_status: str = "ok"  # propagated from Scorer; "fallback" means score unavailable
    label: str = "news"   # "news" | "kol" — propagated from Article
    author: str = ""      # KOL author name; empty for standard news
    published_at: str = ""  # ISO timestamp propagated from source article when available
    history_context: str = ""  # optional retrieval-memory hint for downstream synthesis/display
    semantic_duplicate: bool = False
    semantic_distance: Optional[float] = None
    source_text: str = Field(default="", exclude=True)  # raw article text for reviewer; not serialized
    zh_title: Optional[str] = None  # 繁體中文標題，≤28 字
    zh_summary: Optional[str] = None  # 繁體中文導讀，2句，由 LLM 生成
    zh_body: Optional[str] = None  # 繁體中文全文譯寫
    tldr_tier: Literal["headline", "deep_dive", "tool_or_repo", "number", "standard"] = "standard"
    hook: str = ""  # ≤24 字繁中 reader hook（formatter 會回退到 zh_summary 第一句）
    allowed_themes: list[str] = Field(default_factory=list)  # theme whitelist propagated from KOL registry


class ExtractorAgent:
    """Wraps the Gemini API for per-article structured extraction."""

    def __init__(self):
        self._client = None

    def extract(self, title: str, text: str, source_name: str = "", source_url: str = "") -> Optional[ArticleSummary]:
        lim = _extractor_input_char_limit()
        prompt = EXTRACTION_PROMPT.format(
            title=title,
            source=source_name,
            text=text[:lim],
        )
        try:
            data, raw = generate_json(
                self._gemini_client,
                model=MODEL,
                max_output_tokens=4096,
                system_instruction=SYSTEM_PROMPT,
                prompt=prompt,
                response_schema=ArticleSummary,
            )
            summary = ArticleSummary(**data)
            self._normalize_zh_fields(summary)
            if not self._has_required_fields(summary):
                logger.warning(
                    "Extractor returned incomplete JSON for '%s' | missing_required_field",
                    title[:80],
                )
                return None
            self._enforce_zh_quality(summary, title)
            summary.source_url = source_url
            summary.source_name = source_name
            logger.info(
                "extraction_metrics title=%s len_wh=%d len_why=%d confidence=%s",
                title[:80],
                len((summary.what_happened or "").strip()),
                len((summary.why_it_matters or "").strip()),
                summary.confidence,
            )
            return summary

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error from extractor: %s", exc)
            return None
        except Exception as exc:
            logger.error("Extractor agent failed for '%s': %s", title, exc)
            return None

    def extract_batch(self, articles: list[dict]) -> list[ArticleSummary]:
        results = []
        max_articles = int(os.getenv("MAX_EXTRACTION_ARTICLES", "12"))
        candidates = articles[:max_articles]
        if len(articles) > len(candidates):
            logger.info(
                "Extraction capped at %d/%d articles to stay within runtime budget",
                len(candidates), len(articles),
            )

        for article in candidates:
            text = article.get("content") or article.get("summary", "")
            result = self.extract(
                title=article.get("title", ""),
                text=text,
                source_name=article.get("source", ""),
                source_url=article.get("url", ""),
            )
            if result:
                result.score = float(article.get("score", 0.0))
                result.score_status = str(article.get("score_status", "ok"))
                result.title = article.get("title", "")
                result.label = str(article.get("label", "news"))
                result.author = str(article.get("author", ""))
                result.source_display_name = str(article.get("source_display_name", ""))
                result.source_language = str(article.get("source_language", "en") or "en")
                published_at = article.get("published_at")
                result.published_at = published_at.isoformat() if hasattr(published_at, "isoformat") else str(published_at or "")
                result.source_text = text[: _extractor_input_char_limit()]
                allowed = article.get("allowed_themes") or []
                if isinstance(allowed, (list, tuple)):
                    result.allowed_themes = [str(t) for t in allowed if t]
                self._postprocess_flags(result)
                results.append(result)
        return results

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client

    def _postprocess_flags(self, summary: ArticleSummary) -> None:
        corpus = " ".join([
            summary.title,
            summary.summary,
            " ".join(summary.key_facts),
        ]).lower()

        earnings_signals = [
            r"\brevenue\b", r"\beps\b", r"\bguidance\b", r"\bquarter\b",
            r"\bq[1-4]\b", r"\bprofit\b", r"\boperating income\b",
        ]
        if summary.category == "earnings":
            has_earnings_signal = any(re.search(p, corpus) for p in earnings_signals)
            if not has_earnings_signal:
                summary.category = "other"

        investment_signals = [
            r"\bearnings\b", r"\brevenue\b", r"\beps\b", r"\bguidance\b",
            r"\bacquisition\b", r"\bmerger\b", r"\binvest\b", r"\bfunding\b",
            r"\bdeal\b", r"\btax\b", r"\bregulat", r"\bfine\b", r"\bbillion\b",
            r"\bmillion\b", r"\bstock\b", r"\bshares\b",
        ]
        summary.cross_ref = any(re.search(p, corpus) for p in investment_signals)

    @staticmethod
    def _normalize_zh_fields(summary: ArticleSummary) -> None:
        for field in ("zh_summary", "zh_body"):
            raw = getattr(summary, field, None) or ""
            cleaned = strip_weak_summary_openers(to_traditional_zh_tw(str(raw).strip()))
            setattr(summary, field, cleaned or None)
        raw_hook = (getattr(summary, "hook", "") or "").strip()
        if raw_hook:
            cleaned_hook = to_traditional_zh_tw(raw_hook).strip().strip("「」\"'“”。.")
            if len(cleaned_hook) > 24:
                cleaned_hook = cleaned_hook[:24].rstrip()
            summary.hook = cleaned_hook
        else:
            summary.hook = ""

        raw_title = (getattr(summary, "zh_title", None) or "").strip()
        if raw_title:
            cleaned_title = to_traditional_zh_tw(raw_title).strip().strip("「」\"'“”")
            # Cap to a hard 40-char ceiling so a chatty LLM can't break layout.
            if len(cleaned_title) > 40:
                cleaned_title = cleaned_title[:40].rstrip()
            summary.zh_title = cleaned_title or None
        else:
            summary.zh_title = None

    @staticmethod
    def _has_required_fields(summary: ArticleSummary) -> bool:
        required = (summary.entity, summary.summary, summary.what_happened)
        return all(isinstance(value, str) and bool(value.strip()) for value in required)

    # zh fields are additive (PORTAL_CONTRACT.md): when the LLM under-produces them
    # we keep the English summary and null the zh side so the dashboard falls back
    # to English instead of dropping the article entirely.
    @staticmethod
    def _enforce_zh_quality(summary: ArticleSummary, title: str) -> None:
        zs = (summary.zh_summary or "").strip()
        zb = (summary.zh_body or "").strip()
        if len(zs) < 8:
            if zs:
                logger.info("zh_summary too short for '%s' (len=%d); dropping", title[:80], len(zs))
            summary.zh_summary = None
        if len(zb) < 40:
            if zb:
                logger.info("zh_body too short for '%s' (len=%d); dropping", title[:80], len(zb))
            summary.zh_body = None
