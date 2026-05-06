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

from llm.gemini_client import GEMINI_FLASH_MODEL, GeminiEmptyResponseError, generate_json, make_client
from scoring.heuristic_filter import HeuristicFilter

logger = logging.getLogger(__name__)

SCORE_CONFIG_PATH = Path(__file__).parent / "score_config.yaml"
DOMAIN_LEXICON_PATH = Path(__file__).parent.parent / "sources" / "domain_lexicon.yaml"
FLASH_MODEL = GEMINI_FLASH_MODEL
SCORE_FLASH_OUTPUT_TOKENS = int(os.getenv("SCORE_FLASH_OUTPUT_TOKENS", "512"))
SCORE_FLASH_RETRY_OUTPUT_TOKENS = int(os.getenv("SCORE_FLASH_RETRY_OUTPUT_TOKENS", "1024"))
MIN_LEXICON_SCORE = float(os.getenv("MIN_LEXICON_SCORE", "3.0"))

_SYSTEM = (
    "You are a tech news quality filter. "
    "Respond with ONLY a JSON object. No preamble, no explanation, no markdown fences. "
    'If you cannot score this article, return: {"score": 0, "reason": "cannot_score"}.'
)

_PROMPT = """\
Score this news item 0–10 on three dimensions:
- relevance (0-10): Is AI, semiconductors, or crypto the PRIMARY subject of this article?
  Score 8-10 only when the technical domain is the core story.
  Score ≤ 6 when AI/chips/crypto is merely the demand driver or backdrop for a financial event
  (e.g. a VC fundraise, a stock move, capex guidance, or equipment sales benefiting from AI).
- novelty   (0-10): Is this new information, not a rehash of known facts?
- depth     (0-10): Does it contain specific facts, data, or quotes — not just headlines?

Final score = relevance × {w_rel} + novelty × {w_nov} + depth × {w_dep}

Respond with ONLY a JSON object. No preamble, no explanation, no markdown fences.
If you cannot score this article, return: {{"score": 0, "reason": "cannot_score"}}

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

Respond with ONLY a JSON object. No preamble, no explanation, no markdown fences.
If you cannot score this article, return: {{"score": 0, "reason": "cannot_score"}}

Reply ONLY with valid JSON:
{{"relevance": N, "novelty": N, "depth": N, "score": N}}

Author: {author}
Title: {title}
Text: {text}
"""


class ScoreResult(BaseModel):
    relevance: float = 0.0
    novelty: float = 0.0
    depth: float = 0.0
    score: float
    reason: Optional[str] = None


@dataclass
class ScoreOutcome:
    result: Optional[ScoreResult]
    error_kind: Literal["none", "parse", "api", "empty_response", "safety_blocked", "recitation_blocked"]


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

    def _recover_scores_from_partial_json(self, text: str, item_type: str) -> Optional[ScoreResult]:
        """When Flash returns truncated JSON (e.g. {\"relevance\": ), extract numeric fields via regex."""
        if not text or not text.strip():
            return None
        w = self._config.get("kol_weights", self._config["weights"]) if item_type == "kol" else self._config["weights"]

        def grab(key: str) -> Optional[float]:
            m = re.search(rf'"{key}"\s*:\s*(-?\d+(?:\.\d+)?)', text)
            if not m:
                return None
            return float(m.group(1))

        rel = grab("relevance")
        nov = grab("novelty")
        dep = grab("depth")
        scr = grab("score")
        if rel is not None and nov is not None and dep is not None:
            combined = rel * w["relevance"] + nov * w["novelty"] + dep * w["depth"]
            return ScoreResult(relevance=rel, novelty=nov, depth=dep, score=round(combined, 2))
        if scr is not None:
            return ScoreResult(
                relevance=rel if rel is not None else 0.0,
                novelty=nov if nov is not None else 0.0,
                depth=dep if dep is not None else 0.0,
                score=scr,
            )
        return None

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
                max_output_tokens=SCORE_FLASH_OUTPUT_TOKENS,
                system_instruction=_SYSTEM,
                prompt=prompt,
                response_schema=ScoreResult,
                log_parse_errors=False,
            )
            return ScoreOutcome(result=ScoreResult(**data), error_kind="none")
        except GeminiEmptyResponseError as exc:
            error_kind = self._empty_response_error_kind(exc.finish_reason)
            logger.warning(
                "Scoring failed for '%s' | reason=%s | finish_reason=%s",
                title[:60],
                error_kind,
                exc.finish_reason or "unknown",
            )
            return ScoreOutcome(result=None, error_kind=error_kind)
        except json.JSONDecodeError as exc:
            raw_first = getattr(exc, "raw_text", "") or ""
            recovered = self._recover_scores_from_partial_json(raw_first, item_type)
            if recovered:
                logger.info(
                    "Scorer recovered partial JSON for '%s' (first attempt)",
                    title[:60],
                )
                return ScoreOutcome(result=recovered, error_kind="none")
            retry_prompt = (
                "Reply with ONLY one compact JSON object and nothing else — no prose.\n"
                'Shape: {"relevance":N,"novelty":N,"depth":N,"score":N}\n'
                f"Title: {title[:200]}\n"
                f"Text: {text[:500]}\n"
                "Use numbers 0-10 for relevance, novelty, depth. "
                "score = relevance*w_rel + novelty*w_nov + depth*w_dep with "
                f"w_rel={w['relevance']}, w_nov={w['novelty']}, w_dep={w['depth']}."
            )
            try:
                data, raw = generate_json(
                    self._gemini_client,
                    model=FLASH_MODEL,
                    max_output_tokens=SCORE_FLASH_RETRY_OUTPUT_TOKENS,
                    system_instruction=_SYSTEM,
                    prompt=retry_prompt,
                    response_schema=ScoreResult,
                    log_parse_errors=False,
                )
                return ScoreOutcome(result=ScoreResult(**data), error_kind="none")
            except GeminiEmptyResponseError as empty_exc:
                error_kind = self._empty_response_error_kind(empty_exc.finish_reason)
                logger.warning(
                    "Scoring retry failed for '%s' | reason=%s | finish_reason=%s",
                    title[:60],
                    error_kind,
                    empty_exc.finish_reason or "unknown",
                )
                return ScoreOutcome(result=None, error_kind=error_kind)
            except json.JSONDecodeError as retry_exc:
                raw_retry = getattr(retry_exc, "raw_text", "") or ""
                recovered_retry = self._recover_scores_from_partial_json(raw_retry, item_type)
                if recovered_retry:
                    logger.info(
                        "Scorer recovered partial JSON for '%s' (after retry)",
                        title[:60],
                    )
                    return ScoreOutcome(result=recovered_retry, error_kind="none")
                logger.warning("Scorer JSON parse error after retry: %s", retry_exc)
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

        unscored: list = []

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
                unscored.append(article)  # kept separate — not in main passed list
                logger.warning(
                    "Scoring failed for '%s' (%s) — will appear in fallback tail only",
                    article.title[:60], outcome.error_kind,
                )
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

        # Append unscored items at the end so they form the fallback tail in delivery.
        # Capped so they never crowd out scored content.
        max_unscored_tail = int(os.getenv("MAX_UNSCORED_TAIL", "1"))
        passed.extend(unscored[:max_unscored_tail])

        unscored_ratio = (unscored_count / len(candidates)) if candidates else 0.0
        logger.info(
            "Scoring: %d scored | %d unscored (%.1f%%) | %d total passed",
            len(passed) - min(unscored_count, max_unscored_tail),
            unscored_count,
            unscored_ratio * 100,
            len(passed),
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

    @staticmethod
    def _empty_response_error_kind(finish_reason: str) -> Literal["empty_response", "safety_blocked", "recitation_blocked"]:
        normalized = finish_reason.upper()
        if normalized == "SAFETY":
            return "safety_blocked"
        if normalized == "RECITATION":
            return "recitation_blocked"
        return "empty_response"
