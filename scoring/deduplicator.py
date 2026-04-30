"""URL + content-hash deduplication backed by a configurable state store.

Primary key   : SHA-256 of normalized URL (tracking params stripped)
Secondary key : SHA-256 of first 500 chars of title+content
TTL           : configurable, default 72 hours
Reference     : hrnrxb/AI-News-Aggregator-Bot sqlite pattern
"""

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from scoring.state_store import StateStore, make_state_store

logger = logging.getLogger(__name__)

DEFAULT_TTL_HOURS = int(os.getenv("DEDUP_TTL_HOURS", "72"))

# Common tracking/analytics parameters to strip from URLs
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "fbclid", "gclid", "ref", "referral", "source",
    "mc_cid", "mc_eid", "yclid", "twclid", "li_fat_id",
})


class Deduplicator:
    """Deduplicates news items by normalized URL and content hash with TTL expiry."""

    def __init__(
        self,
        db_path: Path | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        store: StateStore | None = None,
    ):
        self._ttl = timedelta(hours=ttl_hours)
        self._store = store or make_state_store(db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_duplicate(self, url: str, content: str = "") -> bool:
        """Return True if this URL or content body was seen within the TTL window."""
        url_hash = self._url_hash(url)
        content_hash = self._content_hash(content)
        return self._store.has_seen(url_hash, content_hash, self._cutoff_iso())

    def mark_seen(self, url: str, content: str = "") -> None:
        """Record this URL/content as seen now."""
        url_hash = self._url_hash(url)
        content_hash = self._content_hash(content)
        seen_at = datetime.now(timezone.utc)
        self._store.mark_seen(
            url_hash=url_hash,
            content_hash=content_hash,
            seen_at=seen_at,
            url=url,
            expires_at=seen_at + self._ttl,
        )

    def filter_new(self, articles: list) -> list:
        """Return only articles not seen within TTL and mark them as seen.

        Articles are checked and marked per item through the configured state
        store so production deployments can survive stateless container restarts.
        """
        new_articles = []
        for article in articles:
            body = f"{article.title}{(article.summary or '')[:500]}"
            if not self.is_duplicate(article.url, body):
                self.mark_seen(article.url, body)
                new_articles.append(article)

        dropped = len(articles) - len(new_articles)
        logger.info(
            "Dedup: %d new / %d total (%d duplicate%s dropped)",
            len(new_articles), len(articles), dropped, "s" if dropped != 1 else "",
        )
        return new_articles

    def cleanup_expired(self) -> int:
        """Delete records older than TTL. Returns count of removed rows."""
        count = self._store.cleanup_seen(self._cutoff_iso())
        if count:
            logger.info("Dedup cleanup: removed %d expired record%s", count, "s" if count != 1 else "")
        return count

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cutoff_iso(self) -> str:
        return (datetime.now(timezone.utc) - self._ttl).isoformat()

    @staticmethod
    def _url_hash(url: str) -> str:
        return hashlib.sha256(Deduplicator._normalize_url(url).encode()).hexdigest()

    @staticmethod
    def _content_hash(content: str) -> str:
        return hashlib.sha256(content[:500].encode()).hexdigest()

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Strip tracking params and normalize to canonical form."""
        try:
            parsed = urlparse(url)
            clean_params = {
                k: v
                for k, v in parse_qs(parsed.query).items()
                if k.lower() not in _TRACKING_PARAMS
            }
            clean_query = urlencode(sorted(clean_params.items()))
            return parsed._replace(query=clean_query, fragment="").geturl().rstrip("/")
        except Exception:
            return url.rstrip("/")
