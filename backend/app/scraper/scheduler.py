"""
APScheduler-based cron scheduler for the scraper pipeline.

Parses the SCRAPER_CRON setting into APScheduler CronTrigger fields
and runs the pipeline daily to fetch and parse workout posts.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.scraper.pipeline import run_pipeline

logger = logging.getLogger(__name__)

# Module-level scheduler state
_scheduler: Optional[BackgroundScheduler] = None

# Last run status, exposed for the /api/scraper/status endpoint
_last_run_status: dict = {
    "last_run_at": None,
    "last_run_success": None,
    "last_run_method": None,
    "last_run_confidence": None,
    "last_run_error": None,
    "next_run_at": None,
    "scheduler_running": False,
}


def get_last_run_status() -> dict:
    """Return the current scheduler / last run status dict."""
    # Update next_run_at if scheduler is running
    if _scheduler and _scheduler.running:
        _last_run_status["scheduler_running"] = True
        job = _scheduler.get_job("scraper_daily")
        if job and job.next_run_time:
            _last_run_status["next_run_at"] = job.next_run_time.isoformat()
        else:
            _last_run_status["next_run_at"] = None
    else:
        _last_run_status["scheduler_running"] = False
        _last_run_status["next_run_at"] = None

    return _last_run_status.copy()


def _parse_cron_string(cron_str: str) -> dict:
    """
    Parse a standard 5-field cron string into APScheduler CronTrigger kwargs.

    Format: minute hour day_of_month month day_of_week
    Example: "0 5 * * *" -> run at 5:00 AM every day

    Returns:
        dict with keys: minute, hour, day, month, day_of_week
    """
    parts = cron_str.strip().split()
    if len(parts) != 5:
        raise ValueError(
            f"Invalid cron string '{cron_str}': expected 5 fields "
            f"(minute hour day month day_of_week), got {len(parts)}"
        )

    field_names = ["minute", "hour", "day", "month", "day_of_week"]
    kwargs = {}
    for name, value in zip(field_names, parts):
        if value != "*":
            kwargs[name] = value

    return kwargs


def _run_scraper_job() -> None:
    """
    The scheduled job function. Runs the pipeline for today's date
    and updates the last run status.
    """
    logger.info("Scheduled scraper job starting")
    now = datetime.now(timezone.utc)
    _last_run_status["last_run_at"] = now.isoformat()

    try:
        result = run_pipeline()

        _last_run_status["last_run_success"] = result.get("success", False)
        _last_run_status["last_run_method"] = result.get("method")
        _last_run_status["last_run_confidence"] = result.get("confidence")
        _last_run_status["last_run_error"] = result.get("error")

        if result.get("success"):
            logger.info(
                "Scheduled scraper job completed successfully: method=%s confidence=%.2f",
                result.get("method"),
                result.get("confidence", 0),
            )
        else:
            logger.warning(
                "Scheduled scraper job completed with errors: %s",
                result.get("error"),
            )

    except Exception as exc:
        logger.exception("Scheduled scraper job failed with unexpected error")
        _last_run_status["last_run_success"] = False
        _last_run_status["last_run_error"] = str(exc)
        _last_run_status["last_run_method"] = None
        _last_run_status["last_run_confidence"] = None


def start_scheduler() -> None:
    """
    Start the background scheduler with the configured cron schedule.

    Called from the FastAPI app lifespan startup.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler is already running, skipping start")
        return

    cron_str = settings.SCRAPER_CRON
    logger.info("Starting scraper scheduler with cron: %s", cron_str)

    try:
        cron_kwargs = _parse_cron_string(cron_str)
    except ValueError as exc:
        logger.error("Invalid SCRAPER_CRON setting: %s", exc)
        return

    _scheduler = BackgroundScheduler(
        job_defaults={"coalesce": True, "max_instances": 1},
    )

    trigger = CronTrigger(**cron_kwargs)

    _scheduler.add_job(
        _run_scraper_job,
        trigger=trigger,
        id="scraper_daily",
        name="Daily workout scraper",
        replace_existing=True,
    )

    _scheduler.start()
    _last_run_status["scheduler_running"] = True

    # Log next scheduled run
    job = _scheduler.get_job("scraper_daily")
    if job and job.next_run_time:
        _last_run_status["next_run_at"] = job.next_run_time.isoformat()
        logger.info("Next scraper run scheduled for: %s", job.next_run_time.isoformat())


def stop_scheduler() -> None:
    """
    Shut down the background scheduler gracefully.

    Called from the FastAPI app lifespan shutdown.
    """
    global _scheduler

    if _scheduler is None:
        logger.debug("No scheduler to stop")
        return

    if _scheduler.running:
        logger.info("Shutting down scraper scheduler")
        _scheduler.shutdown(wait=False)

    _scheduler = None
    _last_run_status["scheduler_running"] = False
    _last_run_status["next_run_at"] = None
    logger.info("Scraper scheduler stopped")
