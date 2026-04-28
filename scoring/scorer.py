"""LLM-based 0-10 item scorer using Claude Haiku as a cheap fast filter gate.

Inspired by Thysrael/Horizon: run a cheap model score gate *before* expensive
Sonnet agent calls so only high-signal items reach CrewAI.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import anthropic
import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SCORE_CONFIG_PATH = Path(__file__).parent / "score_config.yaml"
HAIKU_MODEL = os.getenv("HAIKU_MODEL", "claude-haiku-4-5-20251001")

_SYSTEM = (
    "You are a tech news quality filter. "
    "Reply ONLY with a valid JSON object, no explanation, no markdown."
)

_PROMPT = """\
Score this news item 0–10 on three dimensions:
- relevance (0-10): Is this meaningful tech/business news? Not opinion or fluff.
- novelty   (0-10): Is this new information, not a rehash of known facts?
- depth     (0-10): Does it contain specific facts, data, or quotes — not just headlines?

Final score = relevance × {w_rel} + novelty × {w_nov} + depth × {w_dep}

Reply ONLY with valid JSON:
{{"relevance": N, "novelty": N, "depth": N, "score": N}}

Title: {title}
Text: {text}
"""


class ScoreResult(BaseModel):
    relevance: float
    novelty: float
    depth: float
    score: float


class Scorer:
    """Scores news articles using Claude Haiku before expensive Sonnet calls."""

    def __init__(self, config_path: Path = SCORE_CONFIG_PATH):
        self._client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            max_retries=2,
        )
        self._config = self._load_config(config_path)

    def _load_config(self, path: Path) -> dict:
        with open(path) as f:
            return yaml.safe_load(f)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_item(
        self, title: str, text: str, item_type: str = "default"
    ) -> Optional[ScoreResult]:
        """Score a single item. Returns None on API/parse failure (caller decides fallback)."""
        w = self._config["weights"]
        prompt = _PROMPT.format(
            w_rel=w["relevance"],
            w_nov=w["novelty"],
            w_dep=w["depth"],
            title=title[:200],
            text=text[:800],
        )
        try:
            message = self._client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=128,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            data = json.loads(raw)
            return ScoreResult(**data)
        except json.JSONDecodeError as exc:
            logger.warning("Scorer JSON parse error: %s | raw=%s", exc, raw[:100])
            return None
        except Exception as exc:
            logger.warning("Scorer failed for '%s': %s", title[:60], exc)
            return None

    def threshold(self, item_type: str = "default") -> float:
        """Return score threshold for item_type. SCORE_THRESHOLD env var overrides default."""
        thresholds = self._config["thresholds"]
        base = thresholds.get(item_type, thresholds["default"])
        if item_type == "default":
            return float(os.getenv("SCORE_THRESHOLD", str(base)))
        return float(base)

    def filter_articles(self, articles: list, item_type: str = "default") -> list:
        """Score all articles, attach score, and return those meeting threshold.

        If scoring fails for an item, it is included with score=0.0 to avoid
        over-filtering due to transient API errors.
        """
        thresh = self.threshold(item_type)
        passed: list = []

        for article in articles:
            text = article.content or article.summary or ""
            result = self.score_item(article.title, text, item_type)

            if result is None:
                # API error: include with score 0.0 (fail-open)
                article.score = 0.0
                passed.append(article)
                continue

            article.score = result.score
            if result.score >= thresh:
                passed.append(article)
            else:
                logger.debug(
                    "Filtered out '%s' (score=%.1f < %.1f)",
                    article.title[:60], result.score, thresh,
                )

        logger.info(
            "Scoring: %d/%d articles passed threshold %.1f",
            len(passed), len(articles), thresh,
        )
        return passed
