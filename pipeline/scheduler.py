"""APScheduler-based cron scheduler for the tech-pulse pipeline."""

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

NEWS_INTERVAL_MINUTES = 15
EARNINGS_INTERVAL_HOURS = 1


def run_news_pipeline():
    from pipeline.crew import TechPulseCrew
    try:
        logger.info("Scheduled news pipeline run starting")
        crew = TechPulseCrew()
        result = crew.run()
        logger.info(
            "Scheduled run complete: %d articles, %d summaries",
            result["articles_fetched"],
            result["summaries_extracted"],
        )
    except Exception as exc:
        logger.error("Scheduled pipeline run failed: %s", exc, exc_info=True)


def main():
    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        run_news_pipeline,
        trigger=IntervalTrigger(minutes=NEWS_INTERVAL_MINUTES),
        id="news_pipeline",
        name="Tech News Pipeline",
        replace_existing=True,
        max_instances=1,
    )

    def _shutdown(signum, frame):
        logger.info("Received signal %d, shutting down scheduler", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info(
        "Scheduler started — news pipeline every %d min; running immediately",
        NEWS_INTERVAL_MINUTES,
    )

    # Run immediately before the first scheduled interval fires
    run_news_pipeline()
    scheduler.start()


if __name__ == "__main__":
    main()
