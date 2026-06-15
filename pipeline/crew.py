"""Pipeline orchestration: Stage 0 (dedup) → Stage 1 (score) → Stage 2 (extract) → Stage 3 (synthesize)."""

from __future__ import annotations

import json
import logging
import os
import signal
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from agents.deep_insight_agent import DeepInsightAgent, InsightBrief
from llm.embedding_client import GeminiEmbedder
from agents.earnings_analyzer import EarningsAnalyzer
from agents.earnings_models import EarningsReport, report_to_legacy_output
from agents.earnings_narrative_extractor import EarningsNarrativeExtractor
from agents.extractor_agent import ArticleSummary, ExtractorAgent
from agents.news_takeaway_agent import NewsTakeawayAgent, news_takeaway_enabled
from agents.relationship_extractor import _load_aliases
from agents.reviewer_agent import ReviewerAgent
from agents.translation_agent import TranslationAgent
from agents.synthesizer_agent import DigestOutput, SynthesizerAgent
from delivery.feedback_poller import poll_pending_feedback
from delivery.pipeline_alert import notify_pipeline_failure
from delivery.revalidate import revalidate_dashboard
from delivery.telegram_bot import TelegramBot
from pipeline.runtime_config import (
    is_staging,
    semantic_prefilter_enabled,
    semantic_prefilter_threshold,
)
from scoring.deduplicator import Deduplicator
from scoring.digest_store import make_digest_store
from scoring.memory_store import (
    MEMORY_TOP_K,
    SEMANTIC_DUP_DISTANCE_THRESHOLD,
    MemorySearchResult,
    make_memory_service,
)
from scoring.scorer import Scorer
from pipeline.earnings_pipeline import EarningsPipelineRunner
from scoring.earnings_report_store import make_earnings_report_store
from sources.sec_xbrl_fetcher import SecXbrlFetcher
from sources.ticker_cik_map import TickerCikMap
from sources.watchlist import EarningsWatchlist
from sources.deep_scraper import DeepScraper
from sources.earnings_fetcher import EarningsFetcher
from sources.rss_fetcher import Article, clean_feed_text
from sources.newsapi_fetcher import NewsApiFetcher
from sources.rss_fetcher import RSSFetcher
from sources.social_tracker import SocialTracker

from llm.localization import strip_weak_summary_openers, to_traditional_zh_tw

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
ITEM_DIGEST_THEME_MIN_SUMMARIES = int(os.getenv("ITEM_DIGEST_THEME_MIN_SUMMARIES", "2"))
SEND_LEGACY_DIGEST = os.getenv("SEND_LEGACY_DIGEST", "0") == "1"
PIPELINE_TIMEOUT_SECONDS = int(os.getenv("PIPELINE_TIMEOUT_SECONDS", "540"))
MAX_DEEP_ARTICLES = int(os.getenv("MAX_DEEP_ARTICLES", "3"))
MIN_DEEP_WORDS = int(os.getenv("MIN_DEEP_WORDS", "800"))
MIN_DIGEST_ITEMS = int(os.getenv("MIN_DIGEST_ITEMS", "5"))
SEMANTIC_DUP_DROP_ENABLED = os.getenv("SEMANTIC_DUP_DROP_ENABLED", "0") == "1"
# Shadow-rollout: log every near-duplicate candidate (even when drop is disabled)
# so the would-drop rate and false positives can be reviewed before flipping the flag.
SEMANTIC_DUP_SHADOW_LOG = os.getenv("SEMANTIC_DUP_SHADOW_LOG", "0") == "1"
MEMORY_CONTEXT_MAX_DISTANCE = float(os.getenv("MEMORY_CONTEXT_MAX_DISTANCE", "0.35"))
EXTRACTOR_FULLTEXT_TOP_K = int(os.getenv("EXTRACTOR_FULLTEXT_TOP_K", "0"))
EXTRACTOR_FULLTEXT_MIN_WORDS = int(os.getenv("EXTRACTOR_FULLTEXT_MIN_WORDS", "120"))
NARRATIVE_EXCERPT_MAX_CHARS = int(os.getenv("NARRATIVE_EXCERPT_MAX_CHARS", "600"))
EXTRACTOR_FULLTEXT_TIMEOUT_SECONDS = int(os.getenv("EXTRACTOR_FULLTEXT_TIMEOUT_SECONDS", "90"))


def truncate_paragraph_at_sentence_boundary(text: str, max_chars: int = 600) -> str:
    """Cut text to max_chars, preferring end-of-sentence or newline over mid-sentence chop."""
    if not text:
        return ""
    t = text.strip()
    if len(t) <= max_chars:
        return t
    window = t[:max_chars]
    min_keep = min(120, max(8, max_chars // 5))
    for i in range(len(window) - 1, min_keep - 1, -1):
        if window[i] in "。！？!?":
            return window[: i + 1].strip()
        if window[i] == "." and i + 1 < len(window) and window[i + 1] == " ":
            return window[: i + 1].strip()
    nl = window.rfind("\n")
    if nl >= min_keep:
        return window[:nl].strip()
    return window.rstrip()


class PipelineDeadlineExceeded(BaseException):
    """Raised when the pipeline reaches its self-imposed Cloud Run runtime budget."""


class TechPulseCrew:
    def __init__(self):
        self.rss = RSSFetcher()
        self.social = SocialTracker()
        self.earnings_fetcher = EarningsFetcher()
        self._earnings_narrative = EarningsNarrativeExtractor()
        self._earnings_analyzer = EarningsAnalyzer()
        self._earnings_watchlist = EarningsWatchlist.load()
        self._ticker_cik_map = TickerCikMap.load(watchlist=self._earnings_watchlist)
        self._sec_xbrl = SecXbrlFetcher()
        self._earnings_report_store = make_earnings_report_store()
        self._earnings_runner = EarningsPipelineRunner(
            fetcher=self.earnings_fetcher,
            xbrl=self._sec_xbrl,
            narrative=self._earnings_narrative,
            analyzer=self._earnings_analyzer,
            store=self._earnings_report_store,
            watchlist=self._earnings_watchlist,
            cik_map=self._ticker_cik_map,
        )
        self._last_earnings_stats = None
        self.deduplicator = Deduplicator()
        self.scorer = Scorer()
        self.deep_scraper = DeepScraper(min_words=MIN_DEEP_WORDS)
        self._extractor_fulltext_scraper = DeepScraper(
            min_words=max(50, EXTRACTOR_FULLTEXT_MIN_WORDS),
            timeout_seconds=EXTRACTOR_FULLTEXT_TIMEOUT_SECONDS,
        )
        self.deep_agent = DeepInsightAgent()
        self.extractor = ExtractorAgent()
        self.reviewer = ReviewerAgent()
        self.translation_agent = TranslationAgent()
        self.news_takeaway_agent = NewsTakeawayAgent()
        self.synthesizer = SynthesizerAgent()
        self.telegram = TelegramBot()
        self.memory = make_memory_service()
        self.digest_store = make_digest_store()
        self._embedder = GeminiEmbedder()
        self._newsapi = NewsApiFetcher()

    def run(self) -> dict:
        OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        alarm_supported = hasattr(signal, "SIGALRM")
        previous_handler = None
        if alarm_supported and PIPELINE_TIMEOUT_SECONDS > 0:
            previous_handler = signal.getsignal(signal.SIGALRM)
            signal.signal(signal.SIGALRM, self._handle_deadline)
            signal.alarm(PIPELINE_TIMEOUT_SECONDS)

        logger.info("=== tech-pulse pipeline starting ===")
        try:
            feedback_count = poll_pending_feedback()
            if feedback_count:
                logger.info("Processed %d Telegram feedback callback(s)", feedback_count)
        except Exception as exc:
            logger.warning("Telegram feedback poll skipped: %s", exc)

        raw_articles = []
        articles = []
        scored_articles = []
        instant_scored_articles = []
        deep_briefs: list[InsightBrief] = []
        summaries: list[ArticleSummary] = []
        digest: DigestOutput | None = None
        earnings_telegram_reports: list[EarningsReport] = []
        critical_errors: list[str] = []
        translation_filled_count = 0
        semantic_prefilter_dropped = 0
        newsapi_fetched = 0
        # Reset per-run semantic dedup observability (avoid stale values on reruns
        # or when the memory step is skipped).
        self._semantic_dup_checked = 0
        self._semantic_dup_would_drop = 0
        self._semantic_dup_dropped = 0

        try:
            if is_staging():
                logger.info(
                    "TECH_PULSE_ENV=staging — semantic prefilter %s",
                    "on" if semantic_prefilter_enabled() else "off",
                )

            # Stage 0 — Ingest & Deduplicate
            try:
                raw_articles = self.rss.fetch_all()
                logger.info("Fetched %d raw articles from RSS/KOL", len(raw_articles))
            except Exception as exc:
                logger.error("RSS fetch failed: %s", exc, exc_info=True)
                critical_errors.append("ingestion:rss")
                raw_articles = []

            try:
                newsapi_articles = self._newsapi.fetch()
                newsapi_fetched = len(newsapi_articles)
                raw_articles = self._merge_articles_by_url(raw_articles, newsapi_articles)
                logger.info(
                    "Ingest total %d articles (newsapi=%d)",
                    len(raw_articles),
                    newsapi_fetched,
                )
            except Exception as exc:
                logger.error("NewsAPI ingest failed: %s", exc, exc_info=True)

            try:
                trending = self.social.fetch_trending()
                logger.info("Fetched %d trending topics", len(trending))
                self.scorer.set_trending_hashtags(trending)
            except Exception as exc:
                logger.error("Social trending fetch failed: %s", exc, exc_info=True)
                self.scorer.set_trending_hashtags([])

            try:
                articles = self.deduplicator.filter_unseen(raw_articles)
                self.deduplicator.cleanup_expired()
            except Exception as exc:
                logger.error("Dedup stage failed: %s", exc, exc_info=True)
                articles = raw_articles  # fallback: use all articles

            # Stage 1 — Score & Filter (Horizon pattern — cheap Gemini Flash gate)
            try:
                scored_articles = self.scorer.filter_articles(articles)
            except Exception as exc:
                logger.error("Scoring stage failed: %s", exc, exc_info=True)
                critical_errors.append("llm:scoring")
                # Mark all as fallback so delivery puts them in tail, not main digest
                for a in articles:
                    if not getattr(a, "score_status", None):
                        a.score = 0.0
                        a.score_status = "fallback"
                scored_articles = articles

            # Semantic pre-extraction dedup — drops same-story duplicates before LLM calls.
            if semantic_prefilter_enabled() and scored_articles:
                before_prefilter = len(scored_articles)
                scored_articles = self._semantic_prefilter(scored_articles)
                semantic_prefilter_dropped = before_prefilter - len(scored_articles)

            # Deep tier — full-text KOL/paper analysis.
            try:
                deep_candidates = [a for a in scored_articles if self._is_deep_candidate(a)]
                deep_briefs, deep_fallbacks, deep_consumed_urls = self._run_deep_pipeline(
                    deep_candidates,
                    timestamp,
                )
                instant_scored_articles = [
                    a for a in scored_articles
                    if a.url not in deep_consumed_urls and not self._is_deep_candidate(a)
                ] + deep_fallbacks
            except Exception as exc:
                logger.error("Deep pipeline failed: %s", exc, exc_info=True)
                critical_errors.append("llm:deep")
                instant_scored_articles = scored_articles

            # Stage 2 — Extract (Gemini Pro)
            try:
                self._enrich_extractor_candidates_with_fulltext(instant_scored_articles)
                article_dicts = [a.model_dump() for a in instant_scored_articles]
                summaries = self.extractor.extract_batch(article_dicts)
                logger.info("Extracted %d article summaries", len(summaries))
                self._save_json(
                    OUTPUT_DIR / f"summaries_{timestamp}.json",
                    [s.model_dump() for s in summaries],
                )
            except Exception as exc:
                logger.error("Extraction stage failed: %s", exc, exc_info=True)
                critical_errors.append("llm:extraction")

            # Stage 2.5 — Reviewer (fact-grounding check + quality gate)
            if summaries:
                pre_review_summaries = summaries
                try:
                    reviewed = self.reviewer.review_batch(summaries)
                    approved = [r.final_output for r in reviewed if r.approved and r.final_output]
                    fact_errors = sum(1 for r in reviewed if r.fact_error)
                    inferred = sum(1 for r in reviewed if r.inferred)
                    logger.info(
                        "Reviewer: %d/%d approved | fact_errors=%d inferred=%d",
                        len(approved), len(reviewed), fact_errors, inferred,
                    )
                    summaries = approved
                    if not summaries and pre_review_summaries:
                        summaries = pre_review_summaries
                        logger.warning("Reviewer rejected all summaries; delivering pre-review summaries")
                except Exception as exc:
                    logger.error("Reviewer stage failed: %s", exc, exc_info=True)
                    critical_errors.append("llm:reviewer")
                    # fail-open: continue with original summaries

            summaries = self._ensure_minimum_summaries(
                summaries, instant_scored_articles, scored_articles
            )
            if summaries:
                try:
                    summaries, translation_filled_count = self.translation_agent.translate_batch(
                        summaries
                    )
                except Exception as exc:
                    logger.error("Translation agent failed: %s", exc, exc_info=True)
                    critical_errors.append("llm:translation")
            if summaries:
                summaries = self._apply_news_takeaways(summaries)
            if summaries:
                summaries = self._apply_memory_context(summaries)
            if summaries:
                summaries = self._apply_portfolio_impact(summaries)
            if summaries:
                summaries = self._apply_decision_context(summaries)
            if summaries:
                summaries = self._claim_deliverable_summaries(summaries, instant_scored_articles)

            should_synthesize = (
                len(summaries) >= ITEM_DIGEST_THEME_MIN_SUMMARIES
                and self._has_formal_scored_item_signal(summaries)
            )
            if summaries and not should_synthesize:
                logger.info(
                    "Skipping digest synthesis: summaries=%d (min=%d) formal_scored_signal=%s "
                    "deliverable_signal=%s",
                    len(summaries),
                    ITEM_DIGEST_THEME_MIN_SUMMARIES,
                    self._has_formal_scored_item_signal(summaries),
                    self._has_deliverable_item_signal(summaries),
                )
            if should_synthesize:
                # Stage 3 — Synthesize (Gemini Pro)
                macro_context: dict | None = None
                try:
                    from agents.macro_context_builder import fetch_macro_context

                    macro_context = fetch_macro_context()
                    if macro_context.get("theme_bias") or macro_context.get("macro"):
                        self._save_json(
                            OUTPUT_DIR / "macro_context_latest.json", macro_context
                        )
                except Exception as exc:
                    logger.warning("Macro context fetch failed: %s", exc)

                try:
                    digest = self.synthesizer.synthesize(
                        summaries, macro_context=macro_context
                    )
                    if digest:
                        self._save_json(OUTPUT_DIR / f"digest_{timestamp}.json", digest.model_dump())
                        logger.info("Digest headline: %s", digest.headline)
                except Exception as exc:
                    logger.error("Synthesis stage failed: %s", exc, exc_info=True)
                    critical_errors.append("llm:synthesis")

            # Earnings sub-pipeline (separate path, not scored — always high-value)
            try:
                earnings_telegram_reports = self._run_earnings_pipeline(timestamp)
            except Exception as exc:
                logger.error("Earnings pipeline failed: %s", exc, exc_info=True)
                critical_errors.append("llm:earnings")
        except PipelineDeadlineExceeded as exc:
            logger.warning("%s; delivering partial results", exc)
        finally:
            if alarm_supported and PIPELINE_TIMEOUT_SECONDS > 0:
                signal.alarm(0)
                if previous_handler is not None:
                    signal.signal(signal.SIGALRM, previous_handler)

        if deep_briefs:
            deep_briefs = self._claim_deep_briefs(deep_briefs, scored_articles)

        # Delivery — each send independently guarded
        narrative_excerpt: str | None = None
        if digest and digest.narrative:
            paragraphs = [p.strip() for p in digest.narrative.split("\n\n") if p.strip()]
            if paragraphs:
                narrative_excerpt = truncate_paragraph_at_sentence_boundary(
                    paragraphs[0], NARRATIVE_EXCERPT_MAX_CHARS
                )

        delivery_attempted = 0
        delivery_succeeded = 0
        story_insights_for_delivery = digest.top_stories if digest else None
        try:
            if self._has_deliverable_item_signal(
                summaries, story_insights=story_insights_for_delivery
            ):
                delivery_attempted += 1
                if self._send_items_digest_with_memory(
                    summaries,
                    total_fetched=len(raw_articles),
                    total_after_filter=len(instant_scored_articles),
                    themes=digest.themes if digest else None,
                    market_takeaway=self.synthesizer.build_market_takeaway(digest) if digest else None,
                    headline=digest.headline if digest else None,
                    narrative_excerpt=narrative_excerpt,
                    story_insights=story_insights_for_delivery,
                ):
                    delivery_succeeded += 1
            else:
                logger.warning(
                    "Telegram items digest skipped: nothing deliverable (summaries=%d, "
                    "has_digest=%s). See funnel in pipeline_run_summary.",
                    len(summaries),
                    digest is not None,
                )
        except Exception as exc:
            logger.error("Telegram items digest delivery failed: %s", exc, exc_info=True)
            critical_errors.append("delivery:items_digest")

        if digest and SEND_LEGACY_DIGEST:
            try:
                delivery_attempted += 1
                if self.telegram.send_digest(digest):
                    delivery_succeeded += 1
            except Exception as exc:
                logger.error("Telegram digest delivery failed: %s", exc, exc_info=True)
                critical_errors.append("delivery:legacy_digest")

        for report in earnings_telegram_reports:
            try:
                delivery_attempted += 1
                if self.telegram.send_earnings_report(report):
                    delivery_succeeded += 1
            except Exception as exc:
                logger.error("Telegram earnings delivery failed: %s", exc, exc_info=True)
                critical_errors.append("delivery:earnings")

        deep_delivered = 0
        for brief in deep_briefs:
            try:
                delivery_attempted += 1
                if self.telegram.send_deep_brief(brief):
                    delivery_succeeded += 1
                    deep_delivered += 1
                    self._archive_delivered_deep_brief(brief)
            except Exception as exc:
                logger.error("Telegram deep brief delivery failed: %s", exc, exc_info=True)
                critical_errors.append("delivery:deep_brief")

        # Best-effort: flush the dashboard's ISR cache so /tries pick up the
        # latest archive without waiting out the 5-minute revalidate window.
        # No-op when DASHBOARD_REVALIDATE_URL / DASHBOARD_REVALIDATE_TOKEN are
        # unset (local dev / CI).
        if delivery_succeeded > 0:
            try:
                self.digest_store.save_run(
                    digest=digest,
                    summaries=summaries,
                    deep_briefs=deep_briefs,
                    funnel={
                        "articles_fetched": len(raw_articles),
                        "newsapi_fetched": newsapi_fetched,
                        "semantic_prefilter_dropped": semantic_prefilter_dropped,
                        "semantic_prefilter_enabled": semantic_prefilter_enabled(),
                        "semantic_dup_checked": self._semantic_dup_checked,
                        "semantic_dup_would_drop": self._semantic_dup_would_drop,
                        "semantic_dup_dropped": self._semantic_dup_dropped,
                    },
                )
            except Exception as exc:
                logger.warning("Digest snapshot save failed: %s", exc)

            try:
                revalidate_dashboard()
            except Exception as exc:  # noqa: BLE001 — best-effort, must not block
                logger.warning("Dashboard revalidate raised unexpectedly: %s", exc)

        low_score_fallback_count = sum(
            1 for s in summaries if getattr(s, "score_status", "") == "low_score_fallback"
        )
        fallback_summary_count = sum(
            1 for s in summaries if getattr(s, "score_status", "") in {"fallback", "unscored"}
        )
        logger.info(
            "Pipeline run summary: fetched=%d after_dedup=%d after_scoring=%d "
            "instant=%d deep=%d earnings=%d low_score_fallback=%d fallback=%d "
            "delivery_attempted=%d delivery_succeeded=%d",
            len(raw_articles),
            len(articles),
            len(scored_articles),
            len(summaries),
            len(deep_briefs),
            len(earnings_telegram_reports),
            low_score_fallback_count,
            fallback_summary_count,
            delivery_attempted,
            delivery_succeeded,
        )
        run_summary = {
            "articles_fetched": len(raw_articles),
            "newsapi_fetched": newsapi_fetched,
            "articles_after_dedup": len(articles),
            "articles_after_scoring": len(scored_articles),
            "semantic_prefilter_enabled": semantic_prefilter_enabled(),
            "semantic_prefilter_dropped": semantic_prefilter_dropped,
            "semantic_dup_drop_enabled": SEMANTIC_DUP_DROP_ENABLED,
            "semantic_dup_checked": self._semantic_dup_checked,
            "semantic_dup_would_drop": self._semantic_dup_would_drop,
            "semantic_dup_dropped": self._semantic_dup_dropped,
            "tech_pulse_env": os.getenv("TECH_PULSE_ENV", "production"),
            "instant_candidates": len(instant_scored_articles),
            "synthesis_ran": digest is not None,
            "summaries_count": len(summaries),
            "translation_filled_count": translation_filled_count,
            "low_score_fallback_count": low_score_fallback_count,
            "fallback_summary_count": fallback_summary_count,
            "deep_briefs": len(deep_briefs),
            "earnings": len(earnings_telegram_reports),
            "digest_headline": (digest.headline if digest else None),
            "delivery_succeeded": delivery_succeeded,
            "delivery_attempted": delivery_attempted,
            "critical_errors": critical_errors,
        }
        if self._last_earnings_stats is not None:
            es = self._last_earnings_stats
            run_summary.update(
                {
                    "earnings_filings_seen": es.filings_seen,
                    "earnings_xbrl_facts_loaded": es.xbrl_facts_loaded,
                    "earnings_vendor_calls": es.vendor_calls,
                    "earnings_reports_archived": es.reports_archived,
                    "earnings_sec_only_count": es.sec_only_count,
                    "earnings_vendor_enriched_count": es.vendor_enriched_count,
                    "earnings_fundamental_enriched_count": es.fundamental_enriched_count,
                    "earnings_telegram_candidates": es.telegram_candidates,
                }
            )
        logger.info("pipeline_run_summary %s", json.dumps(run_summary, ensure_ascii=False))
        logger.info("=== tech-pulse pipeline complete ===")
        return {
            "articles_fetched": len(raw_articles),
            "articles_after_dedup": len(articles),
            "articles_after_scoring": len(scored_articles),
            "summaries_extracted": len(summaries),
            "instant_processed": len(summaries),
            "deep_processed": len(deep_briefs),
            "deep_delivered": deep_delivered,
            "digest": digest.model_dump() if digest else None,
            "earnings": [r.model_dump(mode="json") for r in earnings_telegram_reports],
            "delivery_attempted": delivery_attempted,
            "delivery_succeeded": delivery_succeeded,
            "critical_errors": critical_errors,
        }

    def _run_deep_pipeline(
        self,
        candidates: list[Article],
        timestamp: str,
    ) -> tuple[list[InsightBrief], list[Article], set[str]]:
        if not candidates:
            return [], [], set()

        briefs: list[InsightBrief] = []
        instant_fallbacks: list[Article] = []
        consumed_urls: set[str] = set()

        ordered = sorted(candidates, key=lambda a: getattr(a, "score", 0.0), reverse=True)
        for article in ordered:
            if len(briefs) >= MAX_DEEP_ARTICLES:
                article.deep_status = "over_deep_cap"
                instant_fallbacks.append(article)
                continue

            min_words = max(MIN_DEEP_WORDS, int(getattr(article, "min_words", MIN_DEEP_WORDS) or MIN_DEEP_WORDS))
            scrape = self.deep_scraper.fetch(article.url, min_words=min_words)
            article.word_count = scrape.word_count
            article.deep_status = scrape.status
            if scrape.status != "ok":
                logger.info(
                    "Deep candidate downgraded to instant: %s status=%s words=%d",
                    article.title[:80],
                    scrape.status,
                    scrape.word_count,
                )
                instant_fallbacks.append(article)
                continue

            consumed_urls.add(article.url)
            brief = self.deep_agent.create_brief(
                title=article.title,
                text=scrape.text,
                source_name=article.source,
                source_display_name=article.source_display_name,
                source_language=article.source_language,
                url=article.url,
                author=article.author,
                domain_hints=article.domain,
                score=article.score,
                item_id=self._item_id(article.url),
                cross_ref=article.cross_ref,
            )
            if brief:
                article.deep_status = "brief_created"
                briefs.append(brief)
            else:
                article.deep_status = "deep_llm_failed"

        if briefs:
            self._save_json(
                OUTPUT_DIR / f"deep_briefs_{timestamp}.json",
                [b.model_dump() for b in briefs],
            )
        logger.info("Deep pipeline: %d brief(s), %d fallback(s)", len(briefs), len(instant_fallbacks))
        return briefs, instant_fallbacks, consumed_urls

    def _enrich_extractor_candidates_with_fulltext(self, articles: list[Article]) -> None:
        """Optional Apify full-page fetch for top-K scored articles before extraction (needs APIFY_API_KEY)."""
        k = EXTRACTOR_FULLTEXT_TOP_K
        if k <= 0 or not articles:
            return
        min_words = max(50, EXTRACTOR_FULLTEXT_MIN_WORDS)
        scraper = self._extractor_fulltext_scraper
        ranked = sorted(
            [a for a in articles if float(getattr(a, "score", 0.0) or 0.0) > 0],
            key=lambda a: float(getattr(a, "score", 0.0) or 0.0),
            reverse=True,
        )
        enriched = 0
        for article in ranked[:k]:
            url = getattr(article, "url", "") or ""
            if not url:
                continue
            try:
                scrape = scraper.fetch(url, min_words=min_words)
            except Exception as exc:
                logger.warning("Fulltext enrich failed for %s: %s", url[:80], exc)
                continue
            if scrape.status not in {"ok", "too_short"}:
                continue
            body = (scrape.text or "").strip()
            if not body:
                continue
            prev = (article.content or article.summary or "")
            if len(body) <= len(prev) + 80:
                continue
            article.content = body
            enriched += 1
            logger.info(
                "Extractor fulltext enrich: score=%.1f words=%d title=%s",
                float(getattr(article, "score", 0.0) or 0.0),
                scrape.word_count,
                (article.title or "")[:70],
            )
        if enriched:
            logger.info("Extractor fulltext enrich: %d/%d candidate(s)", enriched, min(k, len(ranked)))

    @staticmethod
    def _is_deep_candidate(article: Article) -> bool:
        return getattr(article, "tier", "instant") == "deep" or getattr(article, "label", "") in {"kol", "paper"}

    @staticmethod
    def _item_id(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:8]

    def _run_earnings_pipeline(self, timestamp: str) -> list[EarningsReport]:
        reports, telegram_reports, stats = self._earnings_runner.run()
        self._last_earnings_stats = stats
        sent_ids = {r.report_id for r in telegram_reports}
        for report in reports:
            try:
                delivered = datetime.now(timezone.utc) if report.report_id in sent_ids else None
                self.memory.archive_earnings_report(report, delivered_at=delivered)
            except Exception as exc:
                logger.warning("Memory archive skipped for earnings report %s: %s", report.report_id, exc)
        logger.info(
            "Earnings pipeline: %d reports archived, %d Telegram candidates",
            len(reports),
            len(telegram_reports),
        )
        if reports:
            self._save_json(
                OUTPUT_DIR / f"earnings_reports_{timestamp}.json",
                [r.model_dump(mode="json") for r in reports],
            )
        if telegram_reports:
            self._save_json(
                OUTPUT_DIR / f"earnings_{timestamp}.json",
                [report_to_legacy_output(r).model_dump() for r in telegram_reports],
            )
        return telegram_reports

    def _fallback_summaries(self, articles: list[Article]) -> list[ArticleSummary]:
        max_articles = int(os.getenv("MAX_EXTRACTION_ARTICLES", "12"))
        summaries: list[ArticleSummary] = []
        for article in articles[:max_articles]:
            raw_text = clean_feed_text(article.content or article.summary or "")
            if not raw_text:
                raw_text = article.title  # last resort: at least show the headline
            # Split text into fact / impact heuristically: first sentence is fact, rest is impact.
            sentences = [s.strip() for s in raw_text.replace("。", ". ").split(". ") if s.strip()]
            what_happened = sentences[0] if sentences else raw_text
            why_it_matters = ". ".join(sentences[1:]) if len(sentences) > 1 else ""
            zh_sum = strip_weak_summary_openers(
                to_traditional_zh_tw((what_happened + " " + (why_it_matters or "")).strip()[:200])
            )
            if len(zh_sum) < 8:
                zh_sum = strip_weak_summary_openers(to_traditional_zh_tw(what_happened[:200]))
            # Mechanical character conversion is not translation; emitting it as
            # zh_body misleads dashboard readers into thinking it's a real 繁中 譯本.
            # The UI falls back to the English summary when zh_body is empty.
            zh_body = None
            summaries.append(
                ArticleSummary(
                    entity=article.source or "Unknown",
                    title=article.title,
                    summary=raw_text,
                    what_happened=what_happened,
                    why_it_matters=why_it_matters,
                    category="other",
                    key_facts=[],
                    sentiment="neutral",
                    confidence="low",
                    cross_ref=article.cross_ref,
                    source_url=article.url,
                    source_name=article.source,
                    source_display_name=getattr(article, "source_display_name", ""),
                    source_language=getattr(article, "source_language", "en") or "en",
                    score=float(getattr(article, "score", 0.0)),
                    score_status=str(getattr(article, "score_status", "fallback")),
                    label=str(getattr(article, "label", "news")),
                    author=str(getattr(article, "author", "")),
                    published_at=article.published_at.isoformat() if article.published_at else "",
                    allowed_themes=list(getattr(article, "allowed_themes", []) or []),
                    source_text=raw_text[:4000],
                    zh_summary=zh_sum or None,
                    zh_body=zh_body,
                )
            )
        return summaries

    @staticmethod
    def _merge_articles_by_url(*pools: list[Article]) -> list[Article]:
        seen: set[str] = set()
        merged: list[Article] = []
        for pool in pools:
            for article in pool:
                url = (article.url or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                merged.append(article)
        return merged

    @staticmethod
    def _merge_article_pools(primary: list[Article], secondary: list[Article]) -> list[Article]:
        """Dedupe by URL; preserve order (instant candidates first, then full scored pool)."""
        seen: set[str] = set()
        ordered: list[Article] = []
        for pool in (primary, secondary):
            for article in pool:
                url = getattr(article, "url", "") or ""
                if url and url not in seen:
                    seen.add(url)
                    ordered.append(article)
        return ordered

    def _ensure_minimum_summaries(
        self,
        summaries: list[ArticleSummary],
        instant_articles: list[Article],
        scored_articles: list[Article],
    ) -> list[ArticleSummary]:
        if len(summaries) >= MIN_DIGEST_ITEMS:
            return summaries

        pool = self._merge_article_pools(instant_articles, scored_articles)
        if not pool:
            return summaries

        existing_urls = {summary.source_url for summary in summaries if summary.source_url}
        needed = MIN_DIGEST_ITEMS - len(summaries)
        fallback_articles = [a for a in pool if a.url not in existing_urls][:needed]
        if not fallback_articles:
            return summaries

        fallback_summaries = self._fallback_summaries(fallback_articles)
        logger.warning(
            "Digest below minimum (%d/%d); adding %d fallback summary item(s) from pooled articles",
            len(summaries),
            MIN_DIGEST_ITEMS,
            len(fallback_summaries),
        )
        return summaries + fallback_summaries

    def _apply_news_takeaways(self, summaries: list[ArticleSummary]) -> list[ArticleSummary]:
        if not news_takeaway_enabled():
            return summaries
        aliases = _load_aliases()
        enriched: list[ArticleSummary] = []
        for summary in summaries:
            if not self._is_formal_scored_summary(summary):
                enriched.append(summary)
                continue
            try:
                summary.takeaway = self.news_takeaway_agent.generate_takeaway(
                    summary, aliases=aliases
                )
            except Exception as exc:
                logger.warning("News takeaway skipped for %s: %s", summary.title[:80], exc)
            enriched.append(summary)
        return enriched

    def _apply_portfolio_impact(
        self, summaries: list[ArticleSummary]
    ) -> list[ArticleSummary]:
        """P1: attach position-aware impact score to each summary (additive, read-only)."""
        try:
            from scoring.portfolio_impact import score_impact  # noqa: PLC0415
            from sources.portfolio import Portfolio, theme_for  # noqa: PLC0415
            from sources.watchlist import EarningsWatchlist  # noqa: PLC0415

            portfolio = Portfolio.load()
            if not portfolio.positions:
                return summaries
            watchlist = EarningsWatchlist.load()
            positions = [
                (p.ticker, (p.shares or 0.0) * (p.avg_cost or 0.0))
                for p in portfolio.positions
            ]
            held_themes = {theme_for(p.ticker, watchlist) for p in portfolio.positions}
        except Exception as exc:  # noqa: BLE001 - never block delivery on impact setup
            logger.warning("Portfolio impact setup skipped: %s", exc)
            return summaries

        for summary in summaries:
            try:
                primary = (summary.tickers or [None])[0]
                theme = theme_for(primary, watchlist) if primary else ""
                summary.portfolio_impact = score_impact(
                    tickers=summary.tickers,
                    entity=summary.entity,
                    theme=theme,
                    confidence=summary.confidence,
                    news_score=summary.score,
                    cross_ref=summary.cross_ref,
                    published_at=summary.published_at,
                    positions=positions,
                    held_themes=held_themes,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Portfolio impact skipped for %s: %s", summary.title[:80], exc
                )
        return summaries

    def _apply_decision_context(
        self, summaries: list[ArticleSummary]
    ) -> list[ArticleSummary]:
        """P2: attach market-context flags to material/held names (gated, default off)."""
        flag = os.getenv("DECISION_CONTEXT_ENABLED", "0").strip().lower()
        if flag not in {"1", "true", "yes", "on"}:
            return summaries
        api_key = os.getenv("FINNHUB_API_KEY", "")
        if not api_key:
            return summaries
        try:
            from agents.decision_context_builder import (  # noqa: PLC0415
                build_market_context,
                closes_from_candle,
            )
            from sources.finnhub_provider import FinnhubProvider  # noqa: PLC0415
            from sources.portfolio import Portfolio  # noqa: PLC0415
            from sources.watchlist import EarningsWatchlist  # noqa: PLC0415

            fh = FinnhubProvider(api_key)
            held = set(Portfolio.load().tickers()) | set(EarningsWatchlist.load().tickers())
            bench = closes_from_candle(fh.candle("SOXX", days_back=250))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Decision context setup skipped: %s", exc)
            return summaries

        cap = int(os.getenv("DECISION_CONTEXT_MAX_CALLS", "12"))
        threshold = float(os.getenv("DECISION_CONTEXT_MIN_IMPACT", "0.3"))
        material = sorted(
            (
                s
                for s in summaries
                if s.portfolio_impact and s.portfolio_impact.score >= threshold
            ),
            key=lambda s: -(s.portfolio_impact.score if s.portfolio_impact else 0.0),
        )
        calls = 0
        for summary in material:
            if calls >= cap:
                break
            primary = (summary.tickers or [None])[0]
            if not primary or primary.upper() not in held:
                continue
            try:
                summary.market_context = build_market_context(
                    fh, primary, bench_closes=bench
                )
                calls += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Market context skipped for %s: %s", primary, exc)
        return summaries

    def _apply_memory_context(self, summaries: list[ArticleSummary]) -> list[ArticleSummary]:
        """Attach retrieval-memory context and optionally drop semantic duplicates.

        Tracks shadow-rollout observability on self: `_semantic_dup_checked`
        (summaries that reached memory search), `_semantic_dup_would_drop`
        (near-duplicate candidates regardless of the drop flag), and
        `_semantic_dup_dropped` (actually dropped). The drop decision itself is
        unchanged — gated by SEMANTIC_DUP_DROP_ENABLED.
        """
        retained: list[ArticleSummary] = []
        checked = 0
        would_drop = 0
        dropped = 0
        for summary in summaries:
            query_summary = self._summary_memory_text(summary)
            try:
                matches = self.memory.search_similar(
                    summary.title or summary.entity,
                    query_summary,
                    top_k=MEMORY_TOP_K,
                    exclude_url=summary.source_url,
                )
            except Exception as exc:
                logger.warning("Memory search failed for %s; continuing without context: %s", summary.title[:80], exc)
                retained.append(summary)
                continue

            checked += 1
            nearest = matches[0] if matches else None
            if nearest and nearest.distance is not None:
                summary.semantic_distance = nearest.distance
                if nearest.distance <= SEMANTIC_DUP_DISTANCE_THRESHOLD:
                    summary.semantic_duplicate = True
                    would_drop += 1
                    if SEMANTIC_DUP_SHADOW_LOG:
                        logger.info(
                            "Semantic dup candidate: '%s' distance=%.3f<=%.2f nearest='%s' "
                            "drop_enabled=%s",
                            (summary.title or summary.entity)[:60],
                            nearest.distance,
                            SEMANTIC_DUP_DISTANCE_THRESHOLD,
                            (nearest.title or "")[:60],
                            SEMANTIC_DUP_DROP_ENABLED,
                        )
                    if SEMANTIC_DUP_DROP_ENABLED:
                        dropped += 1
                        continue

            # Only attach history context for close matches; distant matches add noise.
            if nearest and nearest.distance is not None and nearest.distance <= MEMORY_CONTEXT_MAX_DISTANCE:
                context = self._memory_context_line(matches)
                if context:
                    summary.history_context = context
            retained.append(summary)

        self._semantic_dup_checked = checked
        self._semantic_dup_would_drop = would_drop
        self._semantic_dup_dropped = dropped

        if would_drop:
            logger.info(
                "Semantic dedup: %d/%d near-duplicate candidate(s) at distance<=%.2f "
                "(drop_enabled=%s, dropped=%d)",
                would_drop, checked, SEMANTIC_DUP_DISTANCE_THRESHOLD,
                SEMANTIC_DUP_DROP_ENABLED, dropped,
            )
        return retained

    @staticmethod
    def _summary_memory_text(summary: ArticleSummary) -> str:
        fact = (summary.what_happened or "").strip()
        impact = (summary.why_it_matters or "").strip()
        if fact and impact:
            return f"{fact} {impact}"
        if fact:
            return fact
        return (summary.summary or "").strip()

    @staticmethod
    def _memory_context_line(matches: list[MemorySearchResult]) -> str:
        if not matches:
            return ""
        match = matches[0]
        if not match.title:
            return ""
        source = f"（{match.source_name}）" if match.source_name else ""
        distance = f"，距離 {match.distance:.2f}" if match.distance is not None else ""
        return f"相關歷史：{match.title}{source}{distance}"

    def _semantic_prefilter(self, articles: list[Article]) -> list[Article]:
        """Drop scored articles that are semantically duplicate of an article already in this batch.

        Uses local cosine similarity against embeddings stored in state_store (7-day window).
        Operates BEFORE extractor/reviewer LLM calls to save tokens when multiple sources
        cover the same paper or announcement.
        """
        kept: list[Article] = []
        dropped = 0
        for article in articles:
            text = f"{article.title} {article.summary or ''}".strip()
            embedding = self._embedder.generate_embedding(text)
            if not embedding:
                # Embedding API failure — fail open, keep the article
                kept.append(article)
                continue
            try:
                is_dup, sim = self.deduplicator._store.is_semantically_duplicate(
                    embedding, threshold=semantic_prefilter_threshold()
                )
            except Exception as exc:
                logger.warning("Semantic prefilter check failed for '%s': %s", article.title[:60], exc)
                kept.append(article)
                continue
            if is_dup:
                logger.info(
                    "Semantic duplicate detected (similarity %.2f): '%s' — skipping pre-extraction",
                    sim, article.title[:80],
                )
                dropped += 1
                continue
            try:
                self.deduplicator._store.store_embedding(
                    article_id=article.url,
                    url=article.url,
                    embedding=embedding,
                )
            except Exception as exc:
                logger.warning("Failed to store embedding for '%s': %s", article.title[:60], exc)
            kept.append(article)
        if dropped:
            logger.info("Semantic prefilter dropped %d duplicate article(s)", dropped)
        return kept

    def _claim_deliverable_summaries(
        self,
        summaries: list[ArticleSummary],
        articles: list[Article],
    ) -> list[ArticleSummary]:
        article_by_url = {article.url: article for article in articles}
        claimed: list[ArticleSummary] = []
        skipped = 0
        for summary in summaries:
            article = article_by_url.get(summary.source_url)
            try:
                if article:
                    ok = self.deduplicator.claim_article(article)
                else:
                    content = f"{summary.title}{summary.summary}"
                    ok = self.deduplicator.claim_url(summary.source_url, content)
            except Exception as exc:
                logger.error("Final dedup claim failed for %s: %s", summary.source_url, exc, exc_info=True)
                ok = True

            if ok:
                claimed.append(summary)
            else:
                skipped += 1

        if skipped:
            logger.info("Final dedup claim skipped %d duplicate summary item(s)", skipped)
        return claimed

    def _claim_deep_briefs(
        self,
        briefs: list[InsightBrief],
        articles: list[Article],
    ) -> list[InsightBrief]:
        article_by_url = {article.url: article for article in articles}
        claimed: list[InsightBrief] = []
        skipped = 0
        for brief in briefs:
            article = article_by_url.get(brief.url)
            try:
                if article:
                    ok = self.deduplicator.claim_article(article)
                else:
                    ok = self.deduplicator.claim_url(brief.url, f"{brief.title}{brief.insight}")
            except Exception as exc:
                logger.error("Final deep dedup claim failed for %s: %s", brief.url, exc, exc_info=True)
                ok = True

            if ok:
                claimed.append(brief)
            else:
                skipped += 1

        if skipped:
            logger.info("Final dedup claim skipped %d duplicate deep brief(s)", skipped)
        return claimed

    def _send_items_digest_with_memory(
        self,
        summaries: list[ArticleSummary],
        *,
        total_fetched: int,
        total_after_filter: int,
        themes=None,
        market_takeaway=None,
        headline=None,
        narrative_excerpt=None,
        story_insights=None,
    ) -> bool:
        if not self._has_deliverable_item_signal(summaries, story_insights=story_insights):
            logger.info("Skipping items digest delivery: no scored summaries or story insights")
            return False

        sent = self.telegram.send_items_digest(
            summaries,
            total_fetched=total_fetched,
            total_after_filter=total_after_filter,
            themes=themes,
            market_takeaway=market_takeaway,
            headline=headline,
            narrative_excerpt=narrative_excerpt,
            story_insights=story_insights,
        )
        if sent:
            self._archive_delivered_summaries(summaries)
        return sent

    def _archive_delivered_summaries(self, summaries: list[ArticleSummary]) -> None:
        try:
            self.memory.archive_summaries(summaries)
        except Exception as exc:
            logger.warning("Memory archive skipped for delivered summaries: %s", exc)

    @staticmethod
    def _has_deliverable_item_signal(
        summaries: list[ArticleSummary],
        *,
        story_insights=None,
    ) -> bool:
        if story_insights:
            return True
        deliverable = [s for s in summaries if TechPulseCrew._is_deliverable_summary(s)]
        if not deliverable:
            return False
        # When no formally-scored item exists, require >=2 fallback items so that
        # a single low-confidence article (e.g. a 5.6 KOL roundup) cannot ship alone.
        if not any(TechPulseCrew._is_formal_scored_summary(s) for s in deliverable):
            return len(deliverable) >= 2
        return True

    @staticmethod
    def _has_formal_scored_item_signal(summaries: list[ArticleSummary]) -> bool:
        return any(TechPulseCrew._is_formal_scored_summary(summary) for summary in summaries)

    @staticmethod
    def _is_deliverable_summary(summary: ArticleSummary) -> bool:
        if getattr(summary, "score_status", "") == "low_score_fallback":
            return float(getattr(summary, "score", 0.0) or 0.0) > 0
        return TechPulseCrew._is_formal_scored_summary(summary)

    @staticmethod
    def _is_formal_scored_summary(summary: ArticleSummary) -> bool:
        return (
            float(getattr(summary, "score", 0.0) or 0.0) > 0
            and getattr(summary, "score_status", "ok")
            not in {"fallback", "unscored", "low_score_fallback"}
        )

    def _archive_delivered_deep_brief(self, brief: InsightBrief) -> None:
        try:
            self.memory.archive_deep_brief(brief)
        except Exception as exc:
            logger.warning("Memory archive skipped for delivered deep brief: %s", exc)

    def _handle_deadline(self, signum, frame):
        raise PipelineDeadlineExceeded(
            f"Pipeline runtime budget reached after {PIPELINE_TIMEOUT_SECONDS}s"
        )

    def _save_json(self, path: Path, data: object) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.debug("Saved %s", path)


def main() -> None:
    import sys

    try:
        crew = TechPulseCrew()
        result = crew.run()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    except Exception as exc:
        logger.exception("Pipeline failed with a critical unhandled exception")
        notify_pipeline_failure("tech-pulse", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
