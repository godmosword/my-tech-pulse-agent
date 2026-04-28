"""RSS feed fetcher with source registry and fallback support."""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import httpx
import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent / "source_registry.yaml"
MAX_ARTICLES_PER_FEED = 20

# RSS / Atom namespaces
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class Article(BaseModel):
    title: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    summary: str = ""
    content: str = ""
    cross_ref: bool = False
    score: float = 0.0  # set by Scorer; 0.0 = unscored or below-threshold fallback


class SourceConfig(BaseModel):
    name: str
    url: str
    priority: int
    fallback: Optional[str] = None
    last_success: Optional[datetime] = None
    health_check: bool = True
    type: str = "news"


class RSSFetcher:
    def __init__(self, registry_path: Path = REGISTRY_PATH):
        self._registry: dict[str, SourceConfig] = {}
        self._load_registry(registry_path)

    def _load_registry(self, path: Path) -> None:
        with open(path) as f:
            data = yaml.safe_load(f)
        for entry in data["sources"]:
            cfg = SourceConfig(**entry)
            if cfg.type == "news":
                self._registry[cfg.name] = cfg

    def fetch_all(self) -> list[Article]:
        """Fetch articles from all news sources, sorted by priority."""
        sources = sorted(self._registry.values(), key=lambda s: s.priority)
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for source in sources:
            fetched = self._fetch_source(source)
            for article in fetched:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    articles.append(article)

        return articles

    def _fetch_source(self, source: SourceConfig) -> list[Article]:
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(source.url, headers={"User-Agent": "tech-pulse/0.1"})
                resp.raise_for_status()
                text = resp.text

            articles = self._parse_feed(text, source.name)
            logger.info("Fetched %d articles from %s", len(articles), source.name)
            return articles

        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", source.name, exc)
            if source.fallback and source.fallback in self._registry:
                logger.info("Falling back to %s", source.fallback)
                return self._fetch_source(self._registry[source.fallback])
            return []

    def _parse_feed(self, text: str, source_name: str) -> list[Article]:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            logger.warning("XML parse error for %s: %s", source_name, exc)
            return []

        # Detect RSS vs Atom
        tag = root.tag.lower()
        if "feed" in tag:  # Atom
            return self._parse_atom(root, source_name)
        else:
            return self._parse_rss(root, source_name)

    def _parse_rss(self, root: ET.Element, source_name: str) -> list[Article]:
        articles = []
        channel = root.find("channel")
        if channel is None:
            return articles

        for item in list(channel.findall("item"))[:MAX_ARTICLES_PER_FEED]:
            title = (item.findtext("title") or "").strip()
            url = (item.findtext("link") or "").strip()
            summary = (
                item.findtext(f"{{{NS['content']}}}encoded")
                or item.findtext("description")
                or ""
            )
            published_at = self._parse_date(item.findtext("pubDate"))

            if title and url:
                articles.append(Article(
                    title=title,
                    url=url,
                    source=source_name,
                    published_at=published_at,
                    summary=summary[:2000],
                ))
        return articles

    def _parse_atom(self, root: ET.Element, source_name: str) -> list[Article]:
        articles = []
        ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
        prefix = f"{{{ns}}}" if ns else ""

        for entry in list(root.findall(f"{prefix}entry"))[:MAX_ARTICLES_PER_FEED]:
            title = (entry.findtext(f"{prefix}title") or "").strip()

            url = ""
            for link in entry.findall(f"{prefix}link"):
                rel = link.get("rel", "alternate")
                if rel in ("alternate", ""):
                    url = link.get("href", "")
                    break

            summary = (entry.findtext(f"{prefix}summary") or "").strip()
            published_at = self._parse_date(
                entry.findtext(f"{prefix}published") or entry.findtext(f"{prefix}updated")
            )

            if title and url:
                articles.append(Article(
                    title=title,
                    url=url,
                    source=source_name,
                    published_at=published_at,
                    summary=summary[:2000],
                ))
        return articles

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            pass
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def fetch_full_text(self, url: str) -> str:
        """Best-effort HTTP fetch of article body for thin RSS summaries."""
        try:
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                response = client.get(url, headers={"User-Agent": "tech-pulse/0.1"})
                response.raise_for_status()
                return response.text[:10000]
        except Exception as exc:
            logger.warning("Full-text fetch failed for %s: %s", url, exc)
            return ""
