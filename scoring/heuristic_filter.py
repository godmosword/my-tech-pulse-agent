"""Cheap pre-LLM filtering for obvious low-signal feed noise."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

# 三大主題白名單：文章必須在 AI / 半導體 / 加密 至少一個叢集命中，否則一律不過。
AI_TERMS = {
    "ai", "a.i.", "artificial intelligence", "llm", "large language model",
    "openai", "anthropic", "claude", "gemini", "gpt", "chatgpt", "copilot",
    "agent", "agents", "agentic", "autonomous", "generative",
    "transformer", "diffusion", "rag", "retrieval-augmented",
    "inference", "training run", "fine-tuning", "alignment", "rlhf",
    "mistral", "deepseek", "meta llama", "llama", "perplexity", "xai", "grok",
    "robotics", "humanoid", "self-driving", "autonomous vehicle",
}

SEMI_TERMS = {
    "nvidia", "tsmc", "amd", "intel", "samsung", "sk hynix", "micron",
    "broadcom", "marvell", "qualcomm", "arm", "asml", "lam research",
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
    "solana", "sol", "sui", "aptos", "near", "ton",
    "layer 1", "layer 2", "l1", "l2", "rollup", "zk", "zero-knowledge",
    "spot etf", "spot bitcoin etf", "spot ether etf",
    "coinbase", "binance", "kraken", "robinhood crypto",
    "miner", "mining", "hashrate", "halving",
    "nft", "tokenization", "rwa", "real-world asset",
}

# 全部主題詞集合（檢測「至少命中一個主題」用）
TECH_TERMS = AI_TERMS | SEMI_TERMS | CRYPTO_TERMS

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

        ai_hit = _has_term(haystack, AI_TERMS)
        semi_hit = _has_term(haystack, SEMI_TERMS)
        crypto_hit = _has_term(haystack, CRYPTO_TERMS)
        if ai_hit or semi_hit or crypto_hit:
            score += 0.4
            reasons.append(
                "theme:" + "+".join(
                    t for t, ok in (("ai", ai_hit), ("semi", semi_hit), ("crypto", crypto_hit)) if ok
                )
            )
        else:
            # 不在三大主題白名單就直接打入低於門檻區間。
            score -= 0.6
            reasons.append("offtopic")

        if _has_term(haystack, DEPTH_MARKERS):
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


def _has_term(haystack: str, terms: set[str]) -> bool:
    for term in terms:
        escaped = r"\s+".join(re.escape(part) for part in term.split())
        prefix = r"(?<![a-z0-9])" if term[0].isalnum() else ""
        suffix = r"(?![a-z0-9])" if term[-1].isalnum() else ""
        if re.search(f"{prefix}{escaped}{suffix}", haystack):
            return True
    return False
