"""One-line Traditional Chinese investment takeaway for scored news items."""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

from agents.news_takeaway_models import NewsTakeaway, TakeawayLLMOutput
from agents.relationship_extractor import resolve_counterparty_ticker
from llm.gemini_client import GEMINI_FLASH_MODEL, generate_json, make_client

if TYPE_CHECKING:
    from agents.extractor_agent import ArticleSummary

logger = logging.getLogger(__name__)

MAX_TAKEAWAY_CHARS = 40

SYSTEM = """\
You are an investment-savvy tech analyst writing ONE-LINE Traditional Chinese (zh-TW) takeaways for a news feed.
For each news item, write a single sentence (<=40 Chinese chars) capturing WHY an investor should care:
the supply-chain / competitive / demand / regulatory / tech / capital angle.
RULES:
- Base ONLY on the article content. Do NOT invent causation or predict stock prices.
- Do NOT restate the headline. Add the investment angle the headline doesn't say.
- No phrases like "這篇文章" or "報導指出". Start with the substance.
- Identify which companies are materially involved (for ticker tagging).
- Output JSON: {takeaway_zh, angle, involved_companies, confidence}.
- angle must be one of: 供應鏈, 競爭格局, 需求訊號, 政策監管, 技術突破, 資本動向, 其他.
"""

_RETRY_PROMPT_SUFFIX = (
    "\n\nIMPORTANT: takeaway_zh MUST be at most 40 Chinese characters. Shorten aggressively."
)


def _zh_char_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _item_id(summary: "ArticleSummary") -> str:
    url = (summary.source_url or "").strip()
    if url:
        return url
    return f"{summary.source_name}:{summary.title}"


def _article_body(summary: "ArticleSummary", *, max_chars: int = 4000) -> str:
    parts = [
        summary.title or "",
        (summary.zh_summary or "").strip(),
        (summary.zh_body or "").strip(),
        (summary.what_happened or "").strip(),
        (summary.why_it_matters or "").strip(),
        (summary.summary or "").strip(),
    ]
    text = "\n\n".join(p for p in parts if p)
    return text[:max_chars]


def _resolve_tickers(companies: list[str], aliases: dict[str, str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in companies:
        ticker = resolve_counterparty_ticker(name, aliases)
        if not ticker:
            continue
        sym = ticker.strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            out.append(sym)
    return out


class NewsTakeawayAgent:
    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = make_client()
        return self._client

    def generate_takeaway(
        self,
        item: "ArticleSummary",
        *,
        aliases: dict[str, str | None] | None = None,
    ) -> NewsTakeaway:
        empty = NewsTakeaway(item_id=_item_id(item))
        try:
            body = _article_body(item)
            if not body.strip():
                return empty

            prompt = (
                f"Title: {item.title or item.entity}\n"
                f"Source: {item.source_name or 'unknown'}\n\n"
                f"Article content:\n{body}"
            )
            model = os.getenv("NEWS_TAKEAWAY_MODEL", GEMINI_FLASH_MODEL)
            max_tokens = int(os.getenv("NEWS_TAKEAWAY_MAX_OUTPUT_TOKENS", "512"))

            data, _raw = generate_json(
                self.client,
                model=model,
                system_instruction=SYSTEM,
                prompt=prompt,
                max_output_tokens=max_tokens,
                response_schema=TakeawayLLMOutput,
            )
            parsed = TakeawayLLMOutput.model_validate(data)
            takeaway_zh = (parsed.takeaway_zh or "").strip()

            if _zh_char_len(takeaway_zh) > MAX_TAKEAWAY_CHARS:
                data2, _ = generate_json(
                    self.client,
                    model=model,
                    system_instruction=SYSTEM,
                    prompt=prompt + _RETRY_PROMPT_SUFFIX,
                    max_output_tokens=max_tokens,
                    response_schema=TakeawayLLMOutput,
                )
                parsed = TakeawayLLMOutput.model_validate(data2)
                takeaway_zh = (parsed.takeaway_zh or "").strip()

            confidence = parsed.confidence
            if _zh_char_len(takeaway_zh) > MAX_TAKEAWAY_CHARS:
                takeaway_zh = takeaway_zh[:MAX_TAKEAWAY_CHARS]
                confidence = "low"

            tickers = _resolve_tickers(parsed.involved_companies, aliases or {})
            if not tickers and item.tickers:
                tickers = [t.strip().upper() for t in item.tickers if t.strip()][:5]

            return NewsTakeaway(
                item_id=_item_id(item),
                takeaway_zh=takeaway_zh,
                angle=parsed.angle,
                tickers=tickers,
                confidence=confidence,
            )
        except Exception as exc:
            logger.warning("News takeaway failed for %s: %s", item.title, exc)
            return empty


def news_takeaway_enabled() -> bool:
    return os.getenv("NEWS_TAKEAWAY_MODE", "off").strip().lower() == "on"
