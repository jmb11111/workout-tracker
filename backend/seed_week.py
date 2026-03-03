"""
Seed the database with the last week's workouts.
Run inside the backend container:
  docker compose exec backend python seed_week.py
"""

import logging
import sys
from datetime import date, timedelta

from app.scraper.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


def main():
    today = date.today()
    # Seed the last 7 days (including today)
    dates = [today - timedelta(days=i) for i in range(7, -1, -1)]

    logger.info("Seeding workouts for %d days: %s to %s",
                len(dates), dates[0].isoformat(), dates[-1].isoformat())

    results = []
    for target_date in dates:
        day_name = target_date.strftime("%A")
        logger.info("--- %s %s ---", day_name, target_date.isoformat())

        result = run_pipeline(target_date)
        results.append(result)

        if result["success"]:
            logger.info(
                "OK  method=%s  confidence=%.2f  flagged=%s",
                result["method"],
                result["confidence"],
                result["flagged"],
            )
        else:
            logger.warning("FAIL  error=%s", result.get("error", "unknown"))

    # Summary
    successes = sum(1 for r in results if r["success"])
    failures = sum(1 for r in results if not r["success"])
    flagged = sum(1 for r in results if r.get("flagged"))

    logger.info("=" * 50)
    logger.info("SEED COMPLETE: %d success, %d failed, %d flagged out of %d days",
                successes, failures, flagged, len(results))


if __name__ == "__main__":
    main()
