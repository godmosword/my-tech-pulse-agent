"""RSS feed fetcher with source registry, fallback support, and KOL feeds."""

import html
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Literal, Optional

import httpx
import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent / "source_registry.yaml"
KOL_REGISTRY_PATH = Path(__file__).parent / "kol_registry.yaml"
MAX_ARTICLES_PER_FEED = 20


def _env_max_attempts() -> int:
    try:
        return max(1, int(os.getenv("RSS_MAX_ATTEMPTS", "2")))
    except ValueError:
        return 2


# RSS/KOL fetch retry budget. Intentionally distinct from SecClient.get_json
# (3 paced attempts, 429 exponential): RSS sources default to 2 attempts with
# short linear backoff. 1 disables retry.
RSS_MAX_ATTEMPTS = _env_max_attempts()
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_RETRY_AFTER_CAP_SEC = 5.0


def _retry_backoff_sec(attempt: int) -> float:
    return 0.5 * (attempt + 1)


def _retry_after_sec(resp: httpx.Response) -> Optional[float]:
    """Honor a numeric Retry-After header, capped to avoid stalling the pipeline."""
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return min(float(int(raw)), _RETRY_AFTER_CAP_SEC)
    except (TypeError, ValueError):
        return None

# RSS / Atom namespaces
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

_POST_FOOTER_RE = re.compile(
    r"\bThe post\b.*?\bappeared first on\b.*?(?:\.|$)",
    flags=re.IGNORECASE | re.DOTALL,
)

# XML 1.0 document; feeds sometimes emit raw control chars or bare & in titles/links.
_ILLEGAL_XML_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Reference production rule [67]; permissive enough for numeric + named entities.
_BARE_AMPERSAND_RE = re.compile(
    r"&(?!(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9._-]*);)"
)


def _prepare_feed_xml(text: str) -> str:
    """Strip BOM / UTF-8 BOM and characters illegal in XML 1.0."""
    if not text:
        return text
    t = text.lstrip("\ufeff\u200b\u2060")
    return _ILLEGAL_XML_CHAR_RE.sub("", t)


def _escape_bare_ampersands_outside_cdata(xml_text: str) -> str:
    """Escape & that are not entity references — WordPress / feeds often omit &amp; in text."""
    out: list[str] = []
    pos = 0
    while pos < len(xml_text):
        start = xml_text.find("<![CDATA[", pos)
        if start == -1:
            out.append(_BARE_AMPERSAND_RE.sub("&amp;", xml_text[pos:]))
            break
        out.append(_BARE_AMPERSAND_RE.sub("&amp;", xml_text[pos:start]))
        end = xml_text.find("]]>", start)
        if end == -1:
            out.append(xml_text[start:])
            break
        out.append(xml_text[start : end + 3])
        pos = end + 3
    return "".join(out)


def clean_feed_text(text: str) -> str:
    """Convert RSS HTML fragments to compact plain text."""
    if not text:
        return ""

    cleaned = html.unescape(text)
    cleaned = re.sub(r"(?is)<(script|style).*?</\1>", " ", cleaned)
    cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</(?:p|div|li|h[1-6]|blockquote)>", "\n", cleaned)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = _POST_FOOTER_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\bRead More\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[ \t\r\f\v]+", " ", cleaned)
    cleaned = re.sub(r"\n\s+", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip(" \n\t.-")


class Article(BaseModel):
    title: str
    url: str
    source: str
    source_display_name: str = ""
    source_language: str = "en"
    published_at: Optional[datetime] = None
    summary: str = ""
    content: str = ""
    cross_ref: bool = False
    base_score: float = 0.0  # cheap pre-LLM heuristic score, 0.0-1.0
    base_score_status: str = "not_run"
    lexicon_score: float = 5.0  # deterministic domain lexicon score, 0.0-10.0
    matched_signals: list[str] = Field(default_factory=list)
    score: float = 0.0  # set by Scorer; 0.0 = unscored or below-threshold fallback
    score_status: str = "ok"  # "ok" or "fallback" when scorer fails open
    label: str = "news"   # "news" | "kol" | "paper" — controls Telegram rendering prefix
    author: str = ""      # populated for KOL items from kol_registry.yaml
    tier: Literal["instant", "deep", "earnings"] = "instant"
    domain: list[str] = Field(default_factory=list)
    allowed_themes: list[str] = Field(default_factory=list)  # KOL theme whitelist; empty = unrestricted
    min_words: int = 800
    word_count: int = 0
    deep_status: str = "not_run"


class SourceConfig(BaseModel):
    name: str
    url: str
    priority: int
    display_name: str = ""
    language: str = "en"
    fallback: Optional[str] = None
    last_success: Optional[datetime] = None
    health_check: bool = True
    type: str = "news"
    enabled: bool = True
    weight: float = 1.0


class KOLConfig(BaseModel):
    name: str
    author: str
    url: str = ""
    display_name: str = ""
    language: str = "en"
    connector: str = "rss"
    weight: float = 1.0
    focus: list[str] = Field(default_factory=list)
    tier: Literal["deep", "instant"] = "deep"
    domain: list[str] = Field(default_factory=list)
    allowed_themes: list[str] = Field(default_factory=list)
    min_words: int = 800
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
        for entry in self._iter_chinese_kol_entries(data.get("chinese_sources", {})):
            cfg = KOLConfig(**entry)
            self._kol_registry[cfg.name] = cfg

    @staticmethod
    def _iter_chinese_kol_entries(chinese_sources: dict) -> list[dict]:
        entries: list[dict] = []
        if not isinstance(chinese_sources, dict):
            return entries
        for group, sources in chinese_sources.items():
            if not isinstance(sources, list):
                continue
            for source in sources:
                if not isinstance(source, dict):
                    continue
                normalized = {
                    "language": "zh-TW",
                    "tier": "deep",
                    "connector": "rss",
                    "priority": 20,
                    "enabled": True,
                    "domain": [group],
                    **source,
                }
                normalized.setdefault("display_name", str(normalized.get("name", "")))
                normalized.setdefault("author", str(normalized.get("display_name", normalized.get("name", ""))))
                entries.append(normalized)
        return entries

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
            (k for k in self._kol_registry.values() if k.enabled and k.connector == "rss"),
            key=lambda k: k.priority,
        )
        for kol in kol_sources:
            fetched = self._fetch_kol_source(kol)
            for article in fetched:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    articles.append(article)

        return articles

    def _get_with_retry(self, url: str, headers: dict[str, str]) -> httpx.Response:
        """GET with limited retries on transient failures (timeout/transport/5xx/429).

        Permanent responses (304, other 4xx, 2xx) return immediately. The pipeline
        deadline (PIPELINE_TIMEOUT_SECONDS) bounds total time; the fallback chain in
        _fetch_source runs its own bounded retry per source, so amplification is small.
        """
        last_exc: Optional[Exception] = None
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            for attempt in range(RSS_MAX_ATTEMPTS):
                is_last = attempt == RSS_MAX_ATTEMPTS - 1
                try:
                    resp = client.get(url, headers=headers)
                except httpx.TransportError as exc:
                    last_exc = exc
                    if is_last:
                        raise
                    logger.warning(
                        "RSS GET transient error (attempt %d/%d): %s %s",
                        attempt + 1, RSS_MAX_ATTEMPTS, url[:120], exc,
                    )
                    time.sleep(_retry_backoff_sec(attempt))
                    continue
                if resp.status_code in _RETRYABLE_STATUS and not is_last:
                    logger.warning(
                        "RSS GET status %d (attempt %d/%d): %s",
                        resp.status_code, attempt + 1, RSS_MAX_ATTEMPTS, url[:120],
                    )
                    time.sleep(_retry_after_sec(resp) or _retry_backoff_sec(attempt))
                    continue
                if attempt > 0:
                    logger.info("RSS GET recovered on attempt %d: %s", attempt + 1, url[:120])
                return resp
        # Unreachable: the final iteration always returns or raises. Guard for type-checker.
        raise last_exc or RuntimeError(f"RSS GET failed: {url}")

    def _fetch_kol_source(self, kol: KOLConfig) -> list[Article]:
        """Fetch and label articles from a KOL Substack/blog feed."""
        if kol.connector != "rss" or not kol.url:
            logger.info("Skipping non-RSS KOL source %s connector=%s", kol.name, kol.connector)
            return []
        try:
            headers = {"User-Agent": "tech-pulse/0.1"}
            if kol.name in self._etag_cache:
                headers["If-None-Match"] = self._etag_cache[kol.name]
            elif kol.name in self._last_modified_cache:
                headers["If-Modified-Since"] = self._last_modified_cache[kol.name]

            resp = self._get_with_retry(kol.url, headers)

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
                article.label = "paper" if "paper" in kol.domain or "research" in kol.domain else "kol"
                article.author = kol.author
                article.tier = kol.tier
                article.domain = kol.domain or kol.focus
                article.allowed_themes = list(kol.allowed_themes)
                article.min_words = kol.min_words
                article.source_display_name = kol.display_name or kol.name
                article.source_language = kol.language
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

            resp = self._get_with_retry(source.url, headers)

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
            for article in articles:
                article.source_display_name = source.display_name or source.name
                article.source_language = source.language
            logger.info("Fetched %d articles from %s", len(articles), source.name)
            return articles

        except Exception as exc:
            logger.warning("Failed to fetch %s: %s", source.name, exc)
            if source.fallback and source.fallback in self._registry:
                logger.info("Falling back to %s", source.fallback)
                return self._fetch_source(self._registry[source.fallback])
            return []

    def _parse_feed(self, text: str, source_name: str) -> list[Article]:
        bodies: list[str] = []
        seen: set[str] = set()
        for variant in (
            _prepare_feed_xml(text),
            _escape_bare_ampersands_outside_cdata(_prepare_feed_xml(text)),
        ):
            if variant.strip() and variant not in seen:
                bodies.append(variant)
                seen.add(variant)

        root = None
        last_exc: ET.ParseError | None = None
        for body in bodies:
            try:
                root = ET.fromstring(body)
                break
            except ET.ParseError as exc:
                last_exc = exc

        if root is None:
            logger.warning("XML parse error for %s: %s", source_name, last_exc)
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
            content_raw = (
                item.findtext(f"{{{NS['content']}}}encoded")
                or item.findtext("description")
                or ""
            )
            description_raw = item.findtext("description") or content_raw
            summary = clean_feed_text(description_raw)
            content = clean_feed_text(content_raw)
            published_at = self._parse_date(item.findtext("pubDate"))

            if title and url:
                articles.append(Article(
                    title=title,
                    url=url,
                    source=source_name,
                    published_at=published_at,
                    summary=summary[:2000],
                    content=content[:4000],
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

            summary = clean_feed_text(entry.findtext(f"{prefix}summary") or "")
            content = clean_feed_text(entry.findtext(f"{{{NS['content']}}}encoded") or "")
            published_at = self._parse_date(
                entry.findtext(f"{prefix}published") or entry.findtext(f"{prefix}updated")
            )

            if title and url:
                articles.append(Article(
                    title=title,
                    url=url,
                    source=source_name,
                    published_at=published_at,
                    summary=(summary or content)[:2000],
                    content=content[:4000],
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
