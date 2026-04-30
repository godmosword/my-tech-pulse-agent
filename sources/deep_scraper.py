"""Apify-backed full-text fetcher for deep-tier articles.

Cloud Run instances should not scrape target sites directly. This module only
talks to the Apify API, starts an article extraction actor, waits for it, and
reads the actor dataset output.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Literal, Optional

import httpx

logger = logging.getLogger(__name__)

APIFY_BASE_URL = "https://api.apify.com/v2"
DEFAULT_ARTICLE_ACTOR = "apify/website-content-crawler"
ACTOR_POLL_INTERVAL = 3
ACTOR_TIMEOUT = 120


@dataclass(frozen=True)
class DeepScrapeResult:
    url: str
    text: str
    word_count: int
    status: Literal[
        "ok",
        "too_short",
        "empty",
        "fetch_failed",
        "missing_apify_key",
        "rate_limited",
        "timed_out",
    ]


class DeepScraper:
    """Delegates public article extraction to Apify."""

    def __init__(
        self,
        min_words: int = 800,
        timeout_seconds: int = ACTOR_TIMEOUT,
        actor_id: str | None = None,
        apify_key: str | None = None,
    ):
        self.min_words = min_words
        self.timeout_seconds = timeout_seconds
        self.actor_id = actor_id or os.getenv("APIFY_ARTICLE_ACTOR", DEFAULT_ARTICLE_ACTOR)
        self._apify_key = apify_key if apify_key is not None else os.getenv("APIFY_API_KEY", "")

    def fetch(self, url: str, min_words: int | None = None) -> DeepScrapeResult:
        min_words = min_words if min_words is not None else self.min_words
        if not self._apify_key:
            logger.warning("APIFY_API_KEY not set; skipping deep scrape for %s", url)
            return DeepScrapeResult(url=url, text="", word_count=0, status="missing_apify_key")

        try:
            with httpx.Client(timeout=30) as client:
                run_id = self._start_actor_run(client, url)
                if not run_id:
                    return DeepScrapeResult(url=url, text="", word_count=0, status="fetch_failed")
                status = self._wait_for_run(client, run_id)
                if status != "SUCCEEDED":
                    return DeepScrapeResult(
                        url=url,
                        text="",
                        word_count=0,
                        status="timed_out" if status == "TIMED-OUT" else "fetch_failed",
                    )
                items = self._fetch_run_items(client, run_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("Apify rate limited deep scrape for %s", url)
                return DeepScrapeResult(url=url, text="", word_count=0, status="rate_limited")
            logger.warning("Apify deep scrape HTTP error for %s: %s", url, exc)
            return DeepScrapeResult(url=url, text="", word_count=0, status="fetch_failed")
        except Exception as exc:
            logger.warning("Apify deep scrape failed for %s: %s", url, exc)
            return DeepScrapeResult(url=url, text="", word_count=0, status="fetch_failed")

        text = self._extract_dataset_text(items)
        if not text:
            return DeepScrapeResult(url=url, text="", word_count=0, status="empty")

        words = count_mixed_words(text)
        status: Literal["ok", "too_short"] = "ok" if words >= min_words else "too_short"
        return DeepScrapeResult(url=url, text=text, word_count=words, status=status)

    def _start_actor_run(self, client: httpx.Client, url: str) -> Optional[str]:
        response = client.post(
            f"{APIFY_BASE_URL}/acts/{self.actor_id}/runs",
            params={"token": self._apify_key},
            json=self._actor_payload(url),
        )
        response.raise_for_status()
        run_id = response.json().get("data", {}).get("id")
        if not run_id:
            logger.warning("Apify article actor response missing run id: %s", response.text[:200])
        return run_id

    def _wait_for_run(self, client: httpx.Client, run_id: str) -> str:
        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            response = client.get(
                f"{APIFY_BASE_URL}/actor-runs/{run_id}",
                params={"token": self._apify_key},
            )
            response.raise_for_status()
            status = response.json().get("data", {}).get("status", "")
            if status in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
                if status != "SUCCEEDED":
                    logger.warning("Apify article actor run %s ended with status=%s", run_id, status)
                return status
            time.sleep(ACTOR_POLL_INTERVAL)
        logger.warning("Apify article actor run %s timed out after %ds", run_id, self.timeout_seconds)
        return "TIMED-OUT"

    def _fetch_run_items(self, client: httpx.Client, run_id: str) -> list[dict]:
        response = client.get(
            f"{APIFY_BASE_URL}/actor-runs/{run_id}/dataset/items",
            params={"token": self._apify_key, "clean": "true"},
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _actor_payload(url: str) -> dict:
        return {
            "startUrls": [{"url": url}],
            "maxCrawlPages": 1,
            "maxResults": 1,
            "crawlerType": "playwright:firefox",
            "saveMarkdown": True,
            "saveHtml": False,
            "removeElementsCssSelector": "nav, header, footer, script, style, noscript, svg",
        }

    @staticmethod
    def _extract_dataset_text(items: list[dict]) -> str:
        chunks: list[str] = []
        for item in items:
            for key in (
                "text",
                "markdown",
                "content",
                "articleText",
                "pageText",
                "description",
            ):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    chunks.append(value.strip())
                    break
        text = "\n\n".join(chunks)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def count_mixed_words(text: str) -> int:
    """Count CJK characters plus latin/number tokens for mixed Chinese-English text."""
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    latin_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-_.:/]*", text)
    return len(cjk) + len(latin_tokens)
