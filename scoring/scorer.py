"""LLM-based 0-10 item scorer using Gemini Flash as a cheap fast filter gate.

Inspired by Thysrael/Horizon: run a cheap model score gate *before* expensive
Gemini Pro agent calls so only high-signal items reach the extraction agents.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel

from llm.gemini_client import GEMINI_FLASH_MODEL, generate_json, make_client
from scoring.heuristic_filter import HeuristicFilter

logger = logging.getLogger(__name__)

SCORE_CONFIG_PATH = Path(__file__).parent / "score_config.yaml"
DOMAIN_LEXICON_PATH = Path(__file__).parent.parent / "sources" / "domain_lexicon.yaml"
FLASH_MODEL = GEMINI_FLASH_MODEL
MIN_LEXICON_SCORE = float(os.getenv("MIN_LEXICON_SCORE", "3.0"))

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

_KOL_PROMPT = """\
Score this tech analysis/newsletter piece 0–10 on three dimensions:
- relevance (0-10): Is this meaningful tech/business analysis? Not pure opinion/fluff.
- novelty   (0-10): Does it offer a distinct perspective or framework (may be older)?
- depth     (0-10): Does it contain specific analysis, frameworks, or data points?

Final score = relevance × {w_rel} + novelty × {w_nov} + depth × {w_dep}

Reply ONLY with valid JSON:
{{"relevance": N, "novelty": N, "depth": N, "score": N}}

Author: {author}
Title: {title}
Text: {text}
"""


class ScoreResult(BaseModel):
    relevance: float
    novelty: float
    depth: float
    score: float


@dataclass
class ScoreOutcome:
    result: Optional[ScoreResult]
    error_kind: Literal["none", "parse", "api"]


@dataclass(frozen=True)
class LexiconMatch:
    lexicon_score: float
    matched_signals: list[str]


class Scorer:
    """Scores news articles using Gemini Flash before expensive Gemini Pro calls."""

    def __init__(
        self,
        config_path: Path = SCORE_CONFIG_PATH,
        domain_lexicon_path: Path = DOMAIN_LEXICON_PATH,
    ):
        self._client = None
        self._config = self._load_config(config_path)
        self._domain_lexicon = self._load_config(domain_lexicon_path)
        self._source_weights = self._config.get("source_weights", {})
        self._heuristic_filter = HeuristicFilter()
        self._warn_if_threshold_too_low()

    def _load_config(self, path: Path) -> dict:
        with open(path) as f:
            return yaml.safe_load(f)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_item(
        self, title: str, text: str, item_type: str = "default", author: str = ""
    ) -> Optional[ScoreResult]:
        """Score a single item. Returns None on API/parse failure (caller decides fallback)."""
        outcome = self._score_item_with_status(title, text, item_type, author=author)
        return outcome.result

    def match_lexicon(self, title: str, lede_text: str = "") -> LexiconMatch:
        """Run deterministic domain lexicon scoring on title + lede text."""
        haystack = f"{title} {lede_text}".lower()
        score = 5.0
        matched: list[str] = []

        for domain, signals in self._domain_lexicon.items():
            for term in signals.get("high_signal", []):
                if self._contains_term(haystack, term):
                    score += 0.4
                    matched.append(f"{domain}.high:{term}")
            for term in signals.get("low_signal", []):
                if self._contains_term(haystack, term):
                    score -= 0.3
                    matched.append(f"{domain}.low:{term}")

        return LexiconMatch(lexicon_score=round(max(0.0, min(10.0, score)), 2), matched_signals=matched)

    def _score_item_with_status(
        self, title: str, text: str, item_type: str = "default", author: str = ""
    ) -> ScoreOutcome:
        """Score item and include explicit error kind for downstream fallback policies."""
        if item_type == "kol":
            w = self._config.get("kol_weights", self._config["weights"])
            prompt = _KOL_PROMPT.format(
                w_rel=w["relevance"],
                w_nov=w["novelty"],
                w_dep=w["depth"],
                author=author or "unknown",
                title=title[:200],
                text=text[:800],
            )
        else:
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
                self._gemini_client,
                model=FLASH_MODEL,
                max_output_tokens=128,
                system_instruction=_SYSTEM,
                prompt=prompt,
                response_schema=ScoreResult,
            )
            return ScoreOutcome(result=ScoreResult(**data), error_kind="none")
        except json.JSONDecodeError as exc:
            logger.warning("Scorer JSON parse error: %s", exc)
            return ScoreOutcome(result=None, error_kind="parse")
        except Exception as exc:
            logger.warning("Scorer failed for '%s': %s", title[:60], exc)
            return ScoreOutcome(result=None, error_kind="api")

    def threshold(self, item_type: str = "default") -> float:
        """Return score threshold for item_type. SCORE_THRESHOLD env var overrides default."""
        thresholds = self._config["thresholds"]
        base = thresholds.get(item_type, thresholds["default"])
        if item_type == "default":
            return float(os.getenv("SCORE_THRESHOLD", str(base)))
        return float(base)

    def _warn_if_threshold_too_low(self) -> None:
        raw = os.getenv("SCORE_THRESHOLD")
        if raw is None:
            return
        try:
            threshold = float(raw)
        except ValueError:
            logger.warning("Invalid SCORE_THRESHOLD env value: %s", raw)
            return
        if threshold < 1.0:
            logger.warning(
                "SCORE_THRESHOLD=%.2f is very low and may allow low-quality items through.",
                threshold,
            )

    def filter_articles(self, articles: list, item_type: str = "default") -> list:
        """Score all articles and keep threshold-passing + unscored fallback items.

        Scored items below threshold are dropped from main digest candidates.
        Unscored items are tagged for tail placement in delivery formatting.
        """
        default_thresh = self.threshold(item_type)
        passed: list = []
        unscored_count = 0

        for article in articles:
            self._annotate_lexicon_match(article)

        lexicon_passed = []
        lexicon_dropped = []
        for article in articles:
            if getattr(article, "lexicon_score", 5.0) < MIN_LEXICON_SCORE:
                article.score_status = "lexicon_filtered_out"
                lexicon_dropped.append(article)
            else:
                lexicon_passed.append(article)

        if lexicon_dropped:
            logger.info(
                "Lexicon filter: %d/%d passed before Gemini scoring (%d dropped)",
                len(lexicon_passed), len(articles), len(lexicon_dropped),
            )

        prefiltered, dropped = self._heuristic_filter.filter_articles(lexicon_passed)
        if dropped:
            logger.info(
                "Heuristic prefilter: %d/%d passed before Gemini scoring (%d dropped)",
                len(prefiltered), len(articles), len(dropped),
            )

        max_articles = int(os.getenv("MAX_SCORING_ARTICLES", "24"))
        candidates = prefiltered[:max_articles]
        if len(prefiltered) > len(candidates):
            logger.info(
                "Scoring capped at %d/%d articles to stay within runtime budget",
                len(candidates), len(prefiltered),
            )

        for article in candidates:
            text = article.content or article.summary or ""
            article_type = getattr(article, "label", "news")
            effective_type = "kol" if article_type == "kol" else item_type
            author = getattr(article, "author", "")
            thresh = self.threshold(effective_type) if effective_type != item_type else default_thresh
            outcome = self._score_item_with_status(article.title, text, effective_type, author=author)
            result = outcome.result

            if result is None:
                article.score = 0.0
                article.score_status = "fallback"
                unscored_count += 1
                if outcome.error_kind == "api":
                    passed.append(article)
                continue

            weighted_score = self._apply_source_weight(result.score, getattr(article, "source", ""))
            article.score = weighted_score
            article.score_status = "ok"
            if weighted_score >= thresh:
                article.score_status = "scored"
                passed.append(article)
            else:
                article.score_status = "filtered_out"
                logger.debug(
                    "Filtered out '%s' (score=%.1f < %.1f)",
                    article.title[:60], weighted_score, thresh,
                )

        unscored_ratio = (unscored_count / len(candidates)) if candidates else 0.0
        logger.info(
            "Scoring: %d/%d articles passed+unscored | unscored=%d (%.1f%%)",
            len(passed), len(candidates), unscored_count, unscored_ratio * 100,
        )
        return passed

    def _apply_source_weight(self, score: float, source_name: str) -> float:
        weight = float(self._source_weights.get(source_name, 1.0))
        weighted = max(0.0, min(10.0, score * weight))
        return round(weighted, 2)

    @property
    def _gemini_client(self):
        if self._client is None:
            self._client = make_client()
        return self._client

    def _annotate_lexicon_match(self, article) -> None:
        lede_text = (getattr(article, "summary", "") or getattr(article, "content", "") or "")[:800]
        lexicon_match = self.match_lexicon(getattr(article, "title", ""), lede_text)
        article.lexicon_score = lexicon_match.lexicon_score
        article.matched_signals = lexicon_match.matched_signals

    @staticmethod
    def _contains_term(haystack: str, term: str) -> bool:
        escaped = re.escape(term.lower())
        return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", haystack) is not None
