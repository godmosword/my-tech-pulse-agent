"""Optional supplemental ingest via NewsAPI (https://newsapi.org)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from sources.rss_fetcher import Article

logger = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2"
DEFAULT_PAGE_SIZE = int(os.getenv("NEWSAPI_PAGE_SIZE", "20"))
DEFAULT_TIMEOUT = float(os.getenv("NEWSAPI_TIMEOUT_SECONDS", "15"))


class NewsApiFetcher:
    """Fetch English technology headlines when NEWSAPI_KEY is configured."""

    def __init__(self, api_key: str | None = None):
        self._api_key = (api_key if api_key is not None else os.getenv("NEWSAPI_KEY", "")).strip()

    def fetch(self, *, limit: int | None = None) -> list[Article]:
        if not self._api_key:
            logger.info("NEWSAPI_KEY not set; skipping NewsAPI ingest")
            return []

        page_size = min(limit or DEFAULT_PAGE_SIZE, 100)
        params = {
            "category": "technology",
            "language": "en",
            "pageSize": page_size,
            "apiKey": self._api_key,
        }
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                response = client.get(f"{NEWSAPI_BASE}/top-headlines", params=params)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.warning("NewsAPI fetch failed: %s", exc)
            return []

        if payload.get("status") != "ok":
            logger.warning("NewsAPI error: %s", payload.get("message", payload))
            return []

        articles: list[Article] = []
        for row in payload.get("articles") or []:
            if not isinstance(row, dict):
                continue
            parsed = self._to_article(row)
            if parsed:
                articles.append(parsed)

        logger.info("NewsAPI returned %d technology headline(s)", len(articles))
        return articles

    @staticmethod
    def _to_article(row: dict) -> Article | None:
        title = (row.get("title") or "").strip()
        url = (row.get("url") or "").strip()
        if not title or not url or title == "[Removed]":
            return None

        description = (row.get("description") or "").strip()
        content = (row.get("content") or description or title).strip()
        source_name = "newsapi"
        source_obj = row.get("source")
        if isinstance(source_obj, dict):
            source_name = (source_obj.get("name") or source_name).strip() or source_name

        published_at = None
        published_raw = row.get("publishedAt")
        if published_raw:
            try:
                published_at = parsedate_to_datetime(published_raw)
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                try:
                    published_at = datetime.fromisoformat(
                        str(published_raw).replace("Z", "+00:00")
                    )
                except ValueError:
                    published_at = None

        return Article(
            title=title,
            url=url,
            source=source_name,
            source_display_name=source_name,
            source_language="en",
            published_at=published_at,
            summary=description,
            content=content,
            label="news",
            tier="instant",
        )
