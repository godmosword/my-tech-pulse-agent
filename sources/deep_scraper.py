"""Public full-text fetcher for deep-tier articles."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Literal

import httpx

logger = logging.getLogger(__name__)


class _ArticleTextParser(HTMLParser):
    """Small dependency-free HTML text extractor for article-like pages."""

    _TEXT_TAGS = {"article", "main", "section", "p", "li", "h1", "h2", "h3", "blockquote"}
    _SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "svg"}

    def __init__(self):
        super().__init__()
        self._depth = 0
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag in self._TEXT_TAGS:
            self._depth += 1

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in self._TEXT_TAGS and self._depth:
            self._depth -= 1
            self._chunks.append("\n")

    def handle_data(self, data: str):
        if self._skip_depth or self._depth <= 0:
            return
        text = unescape(data).strip()
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        raw = " ".join(self._chunks)
        raw = re.sub(r"\s+", " ", raw)
        raw = re.sub(r"\s+([,.!?;:])", r"\1", raw)
        return raw.strip()


@dataclass(frozen=True)
class DeepScrapeResult:
    url: str
    text: str
    word_count: int
    status: Literal["ok", "too_short", "empty", "fetch_failed"]


class DeepScraper:
    """Fetches publicly readable article text for deep-tier analysis."""

    def __init__(self, min_words: int = 800, timeout_seconds: int = 15):
        self.min_words = min_words
        self.timeout_seconds = timeout_seconds

    def fetch(self, url: str, min_words: int | None = None) -> DeepScrapeResult:
        min_words = min_words if min_words is not None else self.min_words
        try:
            with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = client.get(url, headers={"User-Agent": "tech-pulse/0.1"})
                response.raise_for_status()
        except Exception as exc:
            logger.warning("Deep scrape fetch failed for %s: %s", url, exc)
            return DeepScrapeResult(url=url, text="", word_count=0, status="fetch_failed")

        text = self.extract_text(response.text)
        if not text:
            return DeepScrapeResult(url=url, text="", word_count=0, status="empty")

        words = count_mixed_words(text)
        status: Literal["ok", "too_short"] = "ok" if words >= min_words else "too_short"
        return DeepScrapeResult(url=url, text=text, word_count=words, status=status)

    @staticmethod
    def extract_text(html: str) -> str:
        parser = _ArticleTextParser()
        try:
            parser.feed(html)
        except Exception as exc:
            logger.debug("HTML parser recovered from malformed input: %s", exc)
        return parser.text()


def count_mixed_words(text: str) -> int:
    """Count CJK characters plus latin/number tokens for mixed Chinese-English text."""
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    latin_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-_.:/]*", text)
    return len(cjk) + len(latin_tokens)
