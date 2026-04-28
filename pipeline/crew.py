"""CrewAI orchestration: runs the full tech-pulse pipeline once."""

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
from sources.earnings_fetcher import EarningsFetcher
from sources.rss_fetcher import RSSFetcher
from sources.social_tracker import SocialTracker

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

OUTPUT_DIR = Path("output")


class TechPulseCrew:
    def __init__(self):
        self.rss = RSSFetcher()
        self.social = SocialTracker()
        self.earnings_fetcher = EarningsFetcher()
        self.extractor = ExtractorAgent()
        self.synthesizer = SynthesizerAgent()
        self.earnings_agent = EarningsAgent()
        self.telegram = TelegramBot()

    def run(self) -> dict:
        OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        logger.info("=== tech-pulse pipeline starting ===")

        # Stage 1: Fetch news articles
        articles = self.rss.fetch_all()
        logger.info("Fetched %d articles", len(articles))

        trending = self.social.fetch_trending()
        logger.info("Fetched %d trending topics", len(trending))

        # Stage 2: Layer 1 extraction
        article_dicts = [a.model_dump() for a in articles]
        summaries: list[ArticleSummary] = self.extractor.extract_batch(article_dicts)
        logger.info("Extracted %d article summaries", len(summaries))

        self._save_json(OUTPUT_DIR / f"summaries_{timestamp}.json", [s.model_dump() for s in summaries])

        # Stage 3: Layer 2 synthesis
        digest: DigestOutput | None = self.synthesizer.synthesize(summaries)
        if digest:
            self._save_json(OUTPUT_DIR / f"digest_{timestamp}.json", digest.model_dump())
            logger.info("Digest headline: %s", digest.headline)

        # Stage 4: Earnings sub-pipeline
        earnings_outputs = self._run_earnings_pipeline(timestamp)

        # Stage 5: Telegram delivery
        if digest:
            self.telegram.send_digest(digest)
        for earnings in earnings_outputs:
            self.telegram.send_earnings(earnings)

        logger.info("=== tech-pulse pipeline complete ===")
        return {
            "articles_fetched": len(articles),
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
