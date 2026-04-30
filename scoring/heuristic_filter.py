"""Cheap pre-LLM filtering for obvious low-signal feed noise."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

TECH_TERMS = {
    "ai", "artificial intelligence", "llm", "model", "openai", "anthropic", "gemini",
    "nvidia", "gpu", "chip", "semiconductor", "cloud", "aws", "azure", "google cloud",
    "data center", "datacenter", "robot", "startup", "funding", "ipo", "cybersecurity",
    "security", "privacy", "regulation", "antitrust", "apple", "meta", "microsoft",
    "google", "amazon", "tesla", "spacex", "software", "developer", "database",
    "open source", "enterprise", "saas", "api", "infrastructure", "quantum",
}

LOW_SIGNAL_TERMS = {
    "coupon", "promo code", "deal", "discount", "gift guide", "best early",
    "black friday", "cyber monday", "wordle", "connections hint", "streaming",
    "trailer", "recap", "spoiler", "watch online", "review:", "hands-on:",
}

DEPTH_MARKERS = {
    "announced", "launched", "released", "reported", "acquired", "raised",
    "revenue", "earnings", "guidance", "filing", "sec", "benchmark", "study",
    "research", "technical", "architecture", "strategy", "policy", "regulator",
}


@dataclass(frozen=True)
class HeuristicResult:
    score: float
    passed: bool
    reason: str


class HeuristicFilter:
    """Scores items locally before spending Gemini tokens."""

    def __init__(self, threshold: float | None = None):
        if threshold is None:
            threshold = float(os.getenv("MIN_BASE_SCORE_THRESHOLD", "0.35"))
        self.threshold = max(0.0, min(1.0, threshold))

    def evaluate(self, article) -> HeuristicResult:
        label = getattr(article, "label", "news")
        if label == "kol":
            return HeuristicResult(score=1.0, passed=True, reason="kol_bypass")

        title = getattr(article, "title", "") or ""
        text = getattr(article, "content", "") or getattr(article, "summary", "") or ""
        haystack = f"{title} {text[:1000]}".lower()

        score = 0.0
        reasons: list[str] = []

        if any(term in haystack for term in TECH_TERMS):
            score += 0.4
            reasons.append("tech_terms")

        if any(term in haystack for term in DEPTH_MARKERS):
            score += 0.25
            reasons.append("depth_markers")

        if re.search(r"(\$[\d,.]+|\d+%|\b\d{4}\b|\b\d+(?:\.\d+)?\s*(?:billion|million|trillion)\b)", haystack):
            score += 0.2
            reasons.append("specifics")

        text_len = len(text.strip())
        if text_len >= 180:
            score += 0.15
            reasons.append("body")
        elif text_len >= 80:
            score += 0.08
            reasons.append("short_body")

        if any(term in haystack for term in LOW_SIGNAL_TERMS):
            score -= 0.45
            reasons.append("low_signal_terms")

        if len(title.split()) < 4 and text_len < 80:
            score -= 0.15
            reasons.append("thin")

        score = round(max(0.0, min(1.0, score)), 2)
        passed = score >= self.threshold
        return HeuristicResult(score=score, passed=passed, reason="+".join(reasons) or "no_signal")

    def filter_articles(self, articles: list) -> tuple[list, list]:
        passed = []
        dropped = []
        for article in articles:
            result = self.evaluate(article)
            article.base_score = result.score
            article.base_score_status = result.reason
            if result.passed:
                passed.append(article)
            else:
                article.score_status = "prefiltered_out"
                dropped.append(article)
        return passed, dropped
