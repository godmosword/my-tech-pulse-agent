"""RSS feed fetcher with source registry, fallback support, and KOL feeds."""

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
KOL_REGISTRY_PATH = Path(__file__).parent / "kol_registry.yaml"
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
    base_score: float = 0.0  # cheap pre-LLM heuristic score, 0.0-1.0
    base_score_status: str = "not_run"
    score: float = 0.0  # set by Scorer; 0.0 = unscored or below-threshold fallback
    score_status: str = "ok"  # "ok" or "fallback" when scorer fails open
    label: str = "news"   # "news" | "kol" — controls Telegram rendering prefix
    author: str = ""      # populated for KOL items from kol_registry.yaml


class SourceConfig(BaseModel):
    name: str
    url: str
    priority: int
    fallback: Optional[str] = None
    last_success: Optional[datetime] = None
    health_check: bool = True
    type: str = "news"
    enabled: bool = True
    weight: float = 1.0


class KOLConfig(BaseModel):
    name: str
    author: str
    url: str
    focus: list[str] = Field(default_factory=list)
    priority: int = 99
    enabled: bool = True


class RSSFetcher:
    def __init__(
        self,
        registry_path: Path = REGISTRY_PATH,
        kol_registry_path: Path = KOL_REGISTRY_PATH,
    ):
        self._registry: dict[str, SourceConfig] = {}
        self._kol_registry: dict[str, KOLConfig] = {}
        # ETag and Last-Modified cache keyed by source name (in-process, per-run)
        self._etag_cache: dict[str, str] = {}
        self._last_modified_cache: dict[str, str] = {}
        self._load_registry(registry_path)
        self._load_kol_registry(kol_registry_path)

    def _load_registry(self, path: Path) -> None:
        with open(path) as f:
            data = yaml.safe_load(f)
        for entry in data["sources"]:
            cfg = SourceConfig(**entry)
            if cfg.type == "news":
                self._registry[cfg.name] = cfg

    def _load_kol_registry(self, path: Path) -> None:
        if not path.exists():
            return
        with open(path) as f:
            data = yaml.safe_load(f)
        for entry in data.get("kol_sources", []):
            cfg = KOLConfig(**entry)
            self._kol_registry[cfg.name] = cfg

    def fetch_all(self) -> list[Article]:
        """Fetch articles from all enabled news and KOL sources, sorted by priority."""
        sources = sorted(
            (s for s in self._registry.values() if s.enabled),
            key=lambda s: s.priority,
        )
        articles: list[Article] = []
        seen_urls: set[str] = set()

        for source in sources:
            fetched = self._fetch_source(source)
            for article in fetched:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    articles.append(article)

        kol_sources = sorted(
            (k for k in self._kol_registry.values() if k.enabled),
            key=lambda k: k.priority,
        )
        for kol in kol_sources:
            fetched = self._fetch_kol_source(kol)
            for article in fetched:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    articles.append(article)

        return articles

    def _fetch_kol_source(self, kol: KOLConfig) -> list[Article]:
        """Fetch and label articles from a KOL Substack/blog feed."""
        try:
            headers = {"User-Agent": "tech-pulse/0.1"}
            if kol.name in self._etag_cache:
                headers["If-None-Match"] = self._etag_cache[kol.name]
            elif kol.name in self._last_modified_cache:
                headers["If-Modified-Since"] = self._last_modified_cache[kol.name]

            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(kol.url, headers=headers)

            if resp.status_code == 304:
                logger.debug("KOL feed %s not modified (304); skipping", kol.name)
                return []

            resp.raise_for_status()

            if etag := resp.headers.get("ETag"):
                self._etag_cache[kol.name] = etag
            elif lm := resp.headers.get("Last-Modified"):
                self._last_modified_cache[kol.name] = lm

            articles = self._parse_feed(resp.text, kol.name)
            for article in articles:
                article.label = "kol"
                article.author = kol.author
            logger.info("Fetched %d KOL articles from %s (%s)", len(articles), kol.name, kol.author)
            return articles

        except Exception as exc:
            logger.warning("Failed to fetch KOL feed %s: %s", kol.name, exc)
            return []

    def _fetch_source(self, source: SourceConfig) -> list[Article]:
        try:
            headers = {"User-Agent": "tech-pulse/0.1"}
            if source.name in self._etag_cache:
                headers["If-None-Match"] = self._etag_cache[source.name]
            elif source.name in self._last_modified_cache:
                headers["If-Modified-Since"] = self._last_modified_cache[source.name]

            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(source.url, headers=headers)

            if resp.status_code == 304:
                logger.debug("Feed %s not modified (304); skipping parse", source.name)
                return []

            resp.raise_for_status()

            # Cache conditional-GET validators for next run
            if etag := resp.headers.get("ETag"):
                self._etag_cache[source.name] = etag
            elif lm := resp.headers.get("Last-Modified"):
                self._last_modified_cache[source.name] = lm

            articles = self._parse_feed(resp.text, source.name)
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
