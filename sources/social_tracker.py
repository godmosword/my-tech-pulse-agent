"""Social trending tracker — trending topic signal only, no content scraped."""

import logging
import os
import time
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

APIFY_ACTOR_X = "apidojo/tweet-scraper"
APIFY_BASE_URL = "https://api.apify.com/v2"
ACTOR_POLL_INTERVAL = 3   # seconds between status checks
ACTOR_TIMEOUT = 90        # seconds before giving up on an actor run


class TrendingTopic(BaseModel):
    platform: str          # "x" | "threads"
    hashtag: str
    volume: Optional[int] = None
    engagement_score: Optional[float] = None
    rank: int


class SocialTracker:
    """Retrieves trending hashtags and engagement signals from X / Threads.

    Intentionally returns signal only (hashtag + volume) — no post content is stored
    or forwarded to agents, to avoid scraping policy issues and keep focus on signals.
    """

    def __init__(self):
        self._apify_key = os.getenv("APIFY_API_KEY", "")

    def fetch_trending(self, limit: int = 20) -> list[TrendingTopic]:
        topics: list[TrendingTopic] = []

        if self._apify_key:
            topics.extend(self._fetch_x_trending(limit))
        else:
            logger.info("APIFY_API_KEY not set; skipping social trending fetch")

        return topics

    def _fetch_x_trending(self, limit: int) -> list[TrendingTopic]:
        if not self._apify_key:
            return []

        try:
            payload = {
                "searchTerms": ["#tech", "#AI", "#technology"],
                "maxTweets": limit,
                "queryType": "Latest",
            }
            with httpx.Client(timeout=30) as client:
                run_resp = client.post(
                    f"{APIFY_BASE_URL}/acts/{APIFY_ACTOR_X}/runs",
                    params={"token": self._apify_key},
                    json=payload,
                )
                run_resp.raise_for_status()
                run_data = run_resp.json().get("data", {})
                run_id = run_data.get("id")
                if not run_id:
                    logger.warning("Apify run response missing id: %s", run_resp.text[:200])
                    return []

                if not self._wait_for_run(client, run_id):
                    return []

                results_resp = client.get(
                    f"{APIFY_BASE_URL}/actor-runs/{run_id}/dataset/items",
                    params={"token": self._apify_key, "limit": limit},
                )
                results_resp.raise_for_status()
                items = results_resp.json()

            hashtag_counts: dict[str, int] = {}
            for item in items:
                for tag in item.get("entities", {}).get("hashtags", []):
                    text = f"#{tag['text'].lower()}"
                    hashtag_counts[text] = hashtag_counts.get(text, 0) + 1

            return [
                TrendingTopic(platform="x", hashtag=hashtag, volume=count, rank=rank)
                for rank, (hashtag, count) in enumerate(
                    sorted(hashtag_counts.items(), key=lambda x: -x[1])[:limit], start=1
                )
            ]

        except Exception as exc:
            logger.warning("X trending fetch failed: %s", exc)
            return []

    def _wait_for_run(self, client: httpx.Client, run_id: str) -> bool:
        """Poll until the actor run succeeds or times out."""
        deadline = time.time() + ACTOR_TIMEOUT
        while time.time() < deadline:
            try:
                status_resp = client.get(
                    f"{APIFY_BASE_URL}/actor-runs/{run_id}",
                    params={"token": self._apify_key},
                )
                status_resp.raise_for_status()
                status = status_resp.json().get("data", {}).get("status", "")
                if status == "SUCCEEDED":
                    return True
                if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    logger.warning("Apify actor run %s ended with status: %s", run_id, status)
                    return False
            except Exception as exc:
                logger.warning("Error polling actor run %s: %s", run_id, exc)
                return False
            time.sleep(ACTOR_POLL_INTERVAL)

        logger.warning("Apify actor run %s timed out after %ds", run_id, ACTOR_TIMEOUT)
        return False
