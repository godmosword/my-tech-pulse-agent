"""LLM-based 0-10 item scorer using Gemini Flash as a cheap fast filter gate.

Inspired by Thysrael/Horizon: run a cheap model score gate *before* expensive
Gemini Pro agent calls so only high-signal items reach the extraction agents.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from llm.gemini_client import GEMINI_FLASH_MODEL, generate_json, make_client

logger = logging.getLogger(__name__)

SCORE_CONFIG_PATH = Path(__file__).parent / "score_config.yaml"
FLASH_MODEL = GEMINI_FLASH_MODEL

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
    """Scores news articles using Gemini Flash before expensive Gemini Pro calls."""

    def __init__(self, config_path: Path = SCORE_CONFIG_PATH):
        self._client = make_client()
        self._config = self._load_config(config_path)
        self._source_weights = self._config.get("source_weights", {})

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
            data, raw = generate_json(
                self._client,
                model=FLASH_MODEL,
                max_output_tokens=512,
                system_instruction=_SYSTEM,
                prompt=prompt,
                response_schema=ScoreResult,
            )
            return ScoreResult(**data)
        except json.JSONDecodeError as exc:
            logger.warning("Scorer JSON parse error: %s", exc)
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

            weighted_score = self._apply_source_weight(result.score, getattr(article, "source", ""))
            article.score = weighted_score
            if weighted_score >= thresh:
                passed.append(article)
            else:
                logger.debug(
                    "Filtered out '%s' (score=%.1f < %.1f)",
                    article.title[:60], weighted_score, thresh,
                )

        logger.info(
            "Scoring: %d/%d articles passed threshold %.1f",
            len(passed), len(articles), thresh,
        )
        return passed

    def _apply_source_weight(self, score: float, source_name: str) -> float:
        weight = float(self._source_weights.get(source_name, 1.0))
        weighted = max(0.0, min(10.0, score * weight))
        return round(weighted, 2)
