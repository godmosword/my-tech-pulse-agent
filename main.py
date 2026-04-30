"""Cloud Run Job entry point for one-shot tech-pulse pipeline runs."""

from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

from pipeline.crew import TechPulseCrew


def configure_logging() -> None:
    """Send application logs to Cloud Logging via stdout."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )


def run_job() -> int:
    """Run the pipeline once and return a POSIX process exit code."""
    load_dotenv()
    configure_logging()
    logger = logging.getLogger(__name__)

    try:
        result = TechPulseCrew().run()
    except Exception:
        logger.exception("Pipeline failed with a critical unhandled exception")
        return 1

    fetched = int(result.get("articles_fetched", 0))
    processed = (
        int(result.get("instant_processed", result.get("summaries_extracted", 0)))
        + int(result.get("deep_processed", 0))
        + len(result.get("earnings", []))
    )
    delivered = int(result.get("delivery_succeeded", 0))
    logger.info(
        "Pipeline completed. Fetched: %d, Processed: %d, Delivered: %d",
        fetched,
        processed,
        delivered,
    )
    if result.get("critical_errors"):
        logger.error("Pipeline completed with critical errors: %s", result["critical_errors"])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_job())
