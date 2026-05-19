"""Cheap pre-LLM filtering for obvious low-signal feed noise."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

# 三大主題白名單：文章必須在 AI / 半導體 / 加密 至少一個叢集命中，否則一律不過。
AI_TERMS = {
    "ai", "a.i.", "artificial intelligence", "llm", "large language model",
    "openai", "anthropic", "claude", "gemini", "gpt", "chatgpt", "copilot",
    "ai agent", "llm agent", "agentic", "autonomous", "generative",
    "transformer", "diffusion", "rag", "retrieval-augmented",
    "inference", "training run", "fine-tuning", "alignment", "rlhf",
    "mistral", "deepseek", "meta llama", "llama", "perplexity", "xai", "grok",
    "robotics", "humanoid", "self-driving", "autonomous vehicle",
}

SEMI_TERMS = {
    "nvidia", "tsmc", "amd", "intel", "samsung", "sk hynix", "micron",
    "broadcom", "marvell", "qualcomm", "arm holdings", "asml", "lam research",
    "applied materials", "kla", "tokyo electron", "cadence", "synopsys",
    "semiconductor", "chip", "chips", "wafer", "fab", "foundry",
    "gpu", "tpu", "asic", "npu", "hbm", "high bandwidth memory",
    "lithography", "euv", "high-na", "advanced packaging", "cowos",
    "2nm", "3nm", "5nm", "a16", "rubin", "blackwell", "h100", "h200", "b200",
    "ai accelerator", "data center gpu", "node shrink", "photonics",
}

CRYPTO_TERMS = {
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
    "stablecoin", "usdc", "usdt", "tether", "circle",
    "defi", "web3", "blockchain", "on-chain", "onchain", "off-chain",
    "solana", "sui", "aptos", "near protocol",
    "layer 1", "layer 2", "l1", "l2", "rollup", "zk", "zero-knowledge",
    "spot etf", "spot bitcoin etf", "spot ether etf",
    "coinbase", "binance", "kraken", "robinhood crypto",
    "miner", "mining", "hashrate", "halving",
    "nft", "tokenization", "rwa", "real-world asset",
}

LOW_SIGNAL_TERMS = {
    "coupon", "promo code", "deal", "discount", "gift guide", "best early",
    "black friday", "cyber monday", "wordle", "connections hint", "streaming",
    "trailer", "recap", "spoiler", "watch online", "review:", "hands-on:",
}

# 學術 / paper 風格內容：使用者只要技術發展與投資熱點，學術成果不要。
ACADEMIC_TERMS = {
    "arxiv", "preprint", "peer-reviewed", "peer review",
    "doi:", "abstract:", "we propose", "we present", "in this paper",
    "conference proceedings", "lecture notes", "supplementary material",
    "journal of", "nature.com/articles", "icml", "neurips", "iclr",
    "siggraph", "acm transactions",
}

DEPTH_MARKERS = {
    "announced", "launched", "released", "reported", "acquired", "raised",
    "revenue", "earnings", "guidance", "filing", "sec", "benchmark", "study",
    "research", "technical", "architecture", "strategy", "policy", "regulator",
}

_SPECIFICS_RE = re.compile(
    r"(\$[\d,.]+|\d+%|\b\d{4}\b|\b\d+(?:\.\d+)?\s*(?:billion|million|trillion)\b)"
)


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

        ai_hit, semi_hit, crypto_hit = _theme_hits(haystack)
        has_theme = ai_hit or semi_hit or crypto_hit
        has_depth = _has_term(haystack, DEPTH_MARKERS)
        has_specifics = _has_specifics(haystack)

        if has_theme:
            score += 0.4
            reasons.append(
                "theme:" + "+".join(
                    t for t, ok in (("ai", ai_hit), ("semi", semi_hit), ("crypto", crypto_hit)) if ok
                )
            )
        else:
            score -= 0.6
            reasons.append("offtopic")

        if has_depth:
            score += 0.25
            reasons.append("depth_markers")

        if has_specifics:
            score += 0.2
            reasons.append("specifics")

        text_len = len(text.strip())
        if text_len >= 180:
            score += 0.15
            reasons.append("body")
        elif text_len >= 80:
            score += 0.08
            reasons.append("short_body")

        if _has_term(haystack, LOW_SIGNAL_TERMS):
            score -= 0.45
            reasons.append("low_signal_terms")

        if _has_term(haystack, ACADEMIC_TERMS):
            score -= 0.5
            reasons.append("academic")

        if len(title.split()) < 4 and text_len < 80:
            score -= 0.15
            reasons.append("thin")

        score = round(max(0.0, min(1.0, score)), 2)
        passed = score >= self.threshold
        if has_theme and passed and not _passes_quality_gate(has_depth, has_specifics):
            passed = False
            reasons.append("gate:needs_depth_or_specifics")

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


def _theme_hits(haystack: str) -> tuple[bool, bool, bool]:
    return (
        _has_term(haystack, AI_TERMS),
        _has_term(haystack, SEMI_TERMS),
        _has_term(haystack, CRYPTO_TERMS),
    )


def _has_specifics(haystack: str) -> bool:
    return bool(_SPECIFICS_RE.search(haystack))


def _passes_quality_gate(has_depth: bool, has_specifics: bool) -> bool:
    return has_depth or has_specifics


def _has_term(haystack: str, terms: set[str]) -> bool:
    for term in terms:
        escaped = r"\s+".join(re.escape(part) for part in term.split())
        prefix = r"(?<![a-z0-9])" if term[0].isalnum() else ""
        suffix = r"(?![a-z0-9])" if term[-1].isalnum() else ""
        if re.search(f"{prefix}{escaped}{suffix}", haystack):
            return True
    return False
