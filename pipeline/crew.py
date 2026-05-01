"""Pipeline orchestration: Stage 0 (dedup) → Stage 1 (score) → Stage 2 (extract) → Stage 3 (synthesize)."""

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
from agents.earnings_agent import EarningsAgent, EarningsOutput
from agents.extractor_agent import ArticleSummary, ExtractorAgent
from agents.reviewer_agent import ReviewerAgent
from agents.synthesizer_agent import DigestOutput, SynthesizerAgent
from delivery.telegram_bot import TelegramBot
from scoring.deduplicator import Deduplicator
from scoring.memory_store import (
    MEMORY_TOP_K,
    SEMANTIC_DUP_DISTANCE_THRESHOLD,
    MemorySearchResult,
    make_memory_service,
)
from scoring.scorer import Scorer
from sources.deep_scraper import DeepScraper
from sources.earnings_fetcher import EarningsFetcher
from sources.ir_scraper import IRScraper
from sources.rss_fetcher import Article, clean_feed_text
from sources.rss_fetcher import RSSFetcher
from sources.social_tracker import SocialTracker

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
ITEM_DIGEST_THEME_MIN_SUMMARIES = int(os.getenv("ITEM_DIGEST_THEME_MIN_SUMMARIES", "5"))
SEND_LEGACY_DIGEST = os.getenv("SEND_LEGACY_DIGEST", "0") == "1"
PIPELINE_TIMEOUT_SECONDS = int(os.getenv("PIPELINE_TIMEOUT_SECONDS", "540"))
MAX_EARNINGS_FILINGS = int(os.getenv("MAX_EARNINGS_FILINGS", "2"))
MAX_DEEP_ARTICLES = int(os.getenv("MAX_DEEP_ARTICLES", "3"))
MIN_DEEP_WORDS = int(os.getenv("MIN_DEEP_WORDS", "800"))
MIN_DIGEST_ITEMS = int(os.getenv("MIN_DIGEST_ITEMS", "3"))
SEMANTIC_DUP_DROP_ENABLED = os.getenv("SEMANTIC_DUP_DROP_ENABLED", "0") == "1"
MEMORY_CONTEXT_MAX_DISTANCE = float(os.getenv("MEMORY_CONTEXT_MAX_DISTANCE", "0.35"))
SEMANTIC_PREFILTER_ENABLED = os.getenv("SEMANTIC_PREFILTER_ENABLED", "0") == "1"
SEMANTIC_PREFILTER_THRESHOLD = float(os.getenv("SEMANTIC_PREFILTER_THRESHOLD", "0.85"))


class PipelineDeadlineExceeded(BaseException):
    """Raised when the pipeline reaches its self-imposed Cloud Run runtime budget."""


class TechPulseCrew:
    def __init__(self):
        self.rss = RSSFetcher()
        self.social = SocialTracker()
        self.earnings_fetcher = EarningsFetcher()
        self.ir_scraper = IRScraper()
        self.deduplicator = Deduplicator()
        self.scorer = Scorer()
        self.deep_scraper = DeepScraper(min_words=MIN_DEEP_WORDS)
        self.deep_agent = DeepInsightAgent()
        self.extractor = ExtractorAgent()
        self.reviewer = ReviewerAgent()
        self.synthesizer = SynthesizerAgent()
        self.earnings_agent = EarningsAgent()
        self.telegram = TelegramBot()
        self.memory = make_memory_service()
        self._embedder = GeminiEmbedder()

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
        raw_articles = []
        articles = []
        scored_articles = []
        instant_scored_articles = []
        deep_briefs: list[InsightBrief] = []
        summaries: list[ArticleSummary] = []
        digest: DigestOutput | None = None
        earnings_outputs: list[EarningsOutput] = []
        critical_errors: list[str] = []

        try:
            # Stage 0 — Ingest & Deduplicate
            try:
                raw_articles = self.rss.fetch_all()
                logger.info("Fetched %d raw articles", len(raw_articles))
            except Exception as exc:
                logger.error("RSS fetch failed: %s", exc, exc_info=True)
                critical_errors.append("ingestion:rss")

            try:
                trending = self.social.fetch_trending()
                logger.info("Fetched %d trending topics", len(trending))
            except Exception as exc:
                logger.error("Social trending fetch failed: %s", exc, exc_info=True)

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
            if SEMANTIC_PREFILTER_ENABLED and scored_articles:
                scored_articles = self._semantic_prefilter(scored_articles)

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

            summaries = self._ensure_minimum_summaries(summaries, instant_scored_articles)
            if summaries:
                summaries = self._apply_memory_context(summaries)
            if summaries:
                summaries = self._claim_deliverable_summaries(summaries, instant_scored_articles)

            should_synthesize = len(summaries) >= ITEM_DIGEST_THEME_MIN_SUMMARIES
            if should_synthesize:
                # Stage 3 — Synthesize (Gemini Pro)
                try:
                    digest = self.synthesizer.synthesize(summaries)
                    if digest:
                        self._save_json(OUTPUT_DIR / f"digest_{timestamp}.json", digest.model_dump())
                        logger.info("Digest headline: %s", digest.headline)
                except Exception as exc:
                    logger.error("Synthesis stage failed: %s", exc, exc_info=True)
                    critical_errors.append("llm:synthesis")

            # Earnings sub-pipeline (separate path, not scored — always high-value)
            try:
                earnings_outputs = self._run_earnings_pipeline(timestamp)
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
                narrative_excerpt = paragraphs[0][:600]

        delivery_attempted = 0
        delivery_succeeded = 0
        try:
            delivery_attempted += 1
            if self._send_items_digest_with_memory(
                summaries,
                total_fetched=len(raw_articles),
                total_after_filter=len(instant_scored_articles),
                themes=digest.themes if digest else None,
                market_takeaway=self.synthesizer.build_market_takeaway(digest) if digest else None,
                headline=digest.headline if digest else None,
                narrative_excerpt=narrative_excerpt,
                story_insights=digest.top_stories if digest else None,
            ):
                delivery_succeeded += 1
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

        for earnings in earnings_outputs:
            try:
                delivery_attempted += 1
                if self.telegram.send_earnings(earnings):
                    delivery_succeeded += 1
                    self._archive_delivered_earnings(earnings)
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

        logger.info(
            "Pipeline run summary: fetched=%d after_dedup=%d after_scoring=%d "
            "instant=%d deep=%d earnings=%d delivery_attempted=%d delivery_succeeded=%d",
            len(raw_articles),
            len(articles),
            len(scored_articles),
            len(summaries),
            len(deep_briefs),
            len(earnings_outputs),
            delivery_attempted,
            delivery_succeeded,
        )
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
            "earnings": [e.model_dump() for e in earnings_outputs],
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

    @staticmethod
    def _is_deep_candidate(article: Article) -> bool:
        return getattr(article, "tier", "instant") == "deep" or getattr(article, "label", "") in {"kol", "paper"}

    @staticmethod
    def _item_id(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:8]

    def _run_earnings_pipeline(self, timestamp: str) -> list[EarningsOutput]:
        filings = self.earnings_fetcher.fetch_recent_filings()
        logger.info("Fetched %d earnings filings", len(filings))

        results = []
        for filing in filings[:MAX_EARNINGS_FILINGS]:
            filing = self.earnings_fetcher.enrich_with_text(filing)

            if not filing.raw_text:
                company_key = filing.company.lower().split()[0]
                doc = self.ir_scraper.fetch(company_key)
                if doc and doc.raw_text:
                    filing.raw_text = doc.raw_text
                    filing.source = "IR page"
                    logger.info("Used IR scraper fallback for %s", filing.company)

            output = self.earnings_agent.extract(filing)
            if output:
                results.append(output)

        if results:
            self._save_json(
                OUTPUT_DIR / f"earnings_{timestamp}.json",
                [e.model_dump() for e in results],
            )
        logger.info("Processed %d earnings reports", len(results))
        return results

    def _fallback_summaries(self, articles: list[Article]) -> list[ArticleSummary]:
        max_articles = int(os.getenv("MAX_EXTRACTION_ARTICLES", "8"))
        summaries: list[ArticleSummary] = []
        for article in articles[:max_articles]:
            raw_text = clean_feed_text(article.content or article.summary or "")
            if not raw_text:
                raw_text = article.title  # last resort: at least show the headline
            # Split text into fact / impact heuristically: first sentence is fact, rest is impact.
            sentences = [s.strip() for s in raw_text.replace("。", ". ").split(". ") if s.strip()]
            what_happened = sentences[0] if sentences else raw_text
            why_it_matters = ". ".join(sentences[1:]) if len(sentences) > 1 else ""
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
                    source_text=raw_text[:4000],
                )
            )
        return summaries

    def _ensure_minimum_summaries(
        self,
        summaries: list[ArticleSummary],
        articles: list[Article],
    ) -> list[ArticleSummary]:
        if len(summaries) >= MIN_DIGEST_ITEMS or not articles:
            return summaries

        existing_urls = {summary.source_url for summary in summaries if summary.source_url}
        needed = MIN_DIGEST_ITEMS - len(summaries)
        fallback_articles = [article for article in articles if article.url not in existing_urls][:needed]
        if not fallback_articles:
            return summaries

        fallback_summaries = self._fallback_summaries(fallback_articles)
        logger.warning(
            "Digest below minimum (%d/%d); adding %d fallback summary item(s)",
            len(summaries),
            MIN_DIGEST_ITEMS,
            len(fallback_summaries),
        )
        return summaries + fallback_summaries

    def _apply_memory_context(self, summaries: list[ArticleSummary]) -> list[ArticleSummary]:
        """Attach retrieval-memory context and optionally drop semantic duplicates."""
        retained: list[ArticleSummary] = []
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

            nearest = matches[0] if matches else None
            if nearest and nearest.distance is not None:
                summary.semantic_distance = nearest.distance
                if nearest.distance <= SEMANTIC_DUP_DISTANCE_THRESHOLD:
                    summary.semantic_duplicate = True
                    if SEMANTIC_DUP_DROP_ENABLED:
                        dropped += 1
                        continue

            # Only attach history context for close matches; distant matches add noise.
            if nearest and nearest.distance is not None and nearest.distance <= MEMORY_CONTEXT_MAX_DISTANCE:
                context = self._memory_context_line(matches)
                if context:
                    summary.history_context = context
            retained.append(summary)

        if dropped:
            logger.info("Memory semantic dedup skipped %d near-duplicate summary item(s)", dropped)
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
                    embedding, threshold=SEMANTIC_PREFILTER_THRESHOLD
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

    def _archive_delivered_deep_brief(self, brief: InsightBrief) -> None:
        try:
            self.memory.archive_deep_brief(brief)
        except Exception as exc:
            logger.warning("Memory archive skipped for delivered deep brief: %s", exc)

    def _archive_delivered_earnings(self, earnings: EarningsOutput) -> None:
        try:
            self.memory.archive_earnings(earnings)
        except Exception as exc:
            logger.warning("Memory archive skipped for delivered earnings: %s", exc)

    def _handle_deadline(self, signum, frame):
        raise PipelineDeadlineExceeded(
            f"Pipeline runtime budget reached after {PIPELINE_TIMEOUT_SECONDS}s"
        )

    def _save_json(self, path: Path, data: object) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.debug("Saved %s", path)


def main():
    crew = TechPulseCrew()
    result = crew.run()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
