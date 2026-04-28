"""Social trending tracker — trending topic signal only, no content scraped."""

import logging
import os
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

APIFY_ACTOR_X = "apidojo/tweet-scraper"
APIFY_BASE_URL = "https://api.apify.com/v2"


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
                run_id = run_resp.json()["data"]["id"]

                results_resp = client.get(
                    f"{APIFY_BASE_URL}/actor-runs/{run_id}/dataset/items",
                    params={"token": self._apify_key, "limit": limit},
                )
                results_resp.raise_for_status()
                items = results_resp.json()

            topics = []
            hashtag_counts: dict[str, int] = {}
            for item in items:
                for tag in item.get("entities", {}).get("hashtags", []):
                    text = f"#{tag['text'].lower()}"
                    hashtag_counts[text] = hashtag_counts.get(text, 0) + 1

            for rank, (hashtag, count) in enumerate(
                sorted(hashtag_counts.items(), key=lambda x: -x[1])[:limit], start=1
            ):
                topics.append(
                    TrendingTopic(
                        platform="x",
                        hashtag=hashtag,
                        volume=count,
                        rank=rank,
                    )
                )
            return topics

        except Exception as exc:
            logger.warning("X trending fetch failed: %s", exc)
            return []
