"""Pipeline orchestration: Stage 0 (dedup) → Stage 1 (score) → Stage 2 (extract) → Stage 3 (synthesize)."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from agents.earnings_agent import EarningsAgent, EarningsOutput
from agents.extractor_agent import ArticleSummary, ExtractorAgent
from agents.synthesizer_agent import DigestOutput, SynthesizerAgent
from delivery.telegram_bot import TelegramBot
from scoring.deduplicator import Deduplicator
from scoring.scorer import Scorer
from sources.earnings_fetcher import EarningsFetcher
from sources.ir_scraper import IRScraper
from sources.rss_fetcher import RSSFetcher
from sources.social_tracker import SocialTracker

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))


class TechPulseCrew:
    def __init__(self):
        self.rss = RSSFetcher()
        self.social = SocialTracker()
        self.earnings_fetcher = EarningsFetcher()
        self.ir_scraper = IRScraper()
        self.deduplicator = Deduplicator()
        self.scorer = Scorer()
        self.extractor = ExtractorAgent()
        self.synthesizer = SynthesizerAgent()
        self.earnings_agent = EarningsAgent()
        self.telegram = TelegramBot()

    def run(self) -> dict:
        OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        logger.info("=== tech-pulse pipeline starting ===")

        # Stage 0 — Ingest & Deduplicate
        raw_articles = []
        try:
            raw_articles = self.rss.fetch_all()
            logger.info("Fetched %d raw articles", len(raw_articles))
        except Exception as exc:
            logger.error("RSS fetch failed: %s", exc, exc_info=True)

        try:
            trending = self.social.fetch_trending()
            logger.info("Fetched %d trending topics", len(trending))
        except Exception as exc:
            logger.error("Social trending fetch failed: %s", exc, exc_info=True)

        articles = []
        try:
            articles = self.deduplicator.filter_new(raw_articles)
            self.deduplicator.cleanup_expired()
        except Exception as exc:
            logger.error("Dedup stage failed: %s", exc, exc_info=True)
            articles = raw_articles  # fallback: use all articles

        # Stage 1 — Score & Filter (Horizon pattern — cheap Gemini Flash gate)
        scored_articles = []
        try:
            scored_articles = self.scorer.filter_articles(articles)
        except Exception as exc:
            logger.error("Scoring stage failed: %s", exc, exc_info=True)
            scored_articles = articles  # fallback: pass everything through unscored

        # Stage 2 — Extract (Gemini Pro)
        summaries: list[ArticleSummary] = []
        try:
            article_dicts = [a.model_dump() for a in scored_articles]
            summaries = self.extractor.extract_batch(article_dicts)
            logger.info("Extracted %d article summaries", len(summaries))
            self._save_json(
                OUTPUT_DIR / f"summaries_{timestamp}.json",
                [s.model_dump() for s in summaries],
            )
        except Exception as exc:
            logger.error("Extraction stage failed: %s", exc, exc_info=True)

        # Stage 3 — Synthesize (Gemini Pro)
        digest: DigestOutput | None = None
        try:
            digest = self.synthesizer.synthesize(summaries)
            if digest:
                self._save_json(OUTPUT_DIR / f"digest_{timestamp}.json", digest.model_dump())
                logger.info("Digest headline: %s", digest.headline)
        except Exception as exc:
            logger.error("Synthesis stage failed: %s", exc, exc_info=True)

        # Earnings sub-pipeline (separate path, not scored — always high-value)
        earnings_outputs: list[EarningsOutput] = []
        try:
            earnings_outputs = self._run_earnings_pipeline(timestamp)
        except Exception as exc:
            logger.error("Earnings pipeline failed: %s", exc, exc_info=True)

        # Delivery — each send independently guarded
        try:
            self.telegram.send_items_digest(
                summaries,
                total_fetched=len(raw_articles),
                total_after_filter=len(scored_articles),
            )
        except Exception as exc:
            logger.error("Telegram items digest delivery failed: %s", exc, exc_info=True)

        if digest:
            try:
                self.telegram.send_digest(digest)
            except Exception as exc:
                logger.error("Telegram digest delivery failed: %s", exc, exc_info=True)

        for earnings in earnings_outputs:
            try:
                self.telegram.send_earnings(earnings)
            except Exception as exc:
                logger.error("Telegram earnings delivery failed: %s", exc, exc_info=True)

        logger.info("=== tech-pulse pipeline complete ===")
        return {
            "articles_fetched": len(raw_articles),
            "articles_after_dedup": len(articles),
            "articles_after_scoring": len(scored_articles),
            "summaries_extracted": len(summaries),
            "digest": digest.model_dump() if digest else None,
            "earnings": [e.model_dump() for e in earnings_outputs],
        }

    def _run_earnings_pipeline(self, timestamp: str) -> list[EarningsOutput]:
        filings = self.earnings_fetcher.fetch_recent_filings()
        logger.info("Fetched %d earnings filings", len(filings))

        results = []
        for filing in filings[:10]:  # cap per run to avoid rate limits
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
