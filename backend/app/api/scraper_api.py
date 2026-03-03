"""
Scraper management endpoints.

Provides manual scrape triggers, re-parsing, and scheduler status.
"""

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.oidc import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.workout import WorkoutDay
from app.scraper.pipeline import run_pipeline, reparse
from app.scraper.scheduler import get_last_run_status
from app.api.schemas import (
    ScraperStatusResponse,
    ScraperTriggerResponse,
    ReparseResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/trigger", response_model=ScraperTriggerResponse)
async def trigger_scrape(
    target_date: str | None = Query(
        None,
        description="Date to scrape (YYYY-MM-DD). Defaults to today.",
    ),
    user: User = Depends(get_current_user),
):
    """
    Manually trigger the scraper pipeline for today or a given date.

    Runs the full fetch-parse-save pipeline and returns the result.
    Requires authentication.
    """
    scrape_date: date
    if target_date:
        try:
            scrape_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD.",
            )
    else:
        scrape_date = date.today()

    logger.info("Manual scrape triggered by user %d for %s", user.id, scrape_date.isoformat())

    result = run_pipeline(scrape_date)

    return ScraperTriggerResponse(
        date=result.get("date", scrape_date.isoformat()),
        success=result.get("success", False),
        method=result.get("method"),
        confidence=result.get("confidence", 0.0),
        flagged=result.get("flagged", False),
        error=result.get("error"),
        workout_day_id=result.get("workout_day_id"),
    )


@router.post("/reparse/{workout_day_id}", response_model=ReparseResponse)
async def reparse_workout(
    workout_day_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-run the parsing pipeline on a stored WorkoutDay's raw_text
    without re-fetching from the blog.

    Useful when parsing logic has been updated or when manual
    review suggests the initial parse was incorrect.
    Requires authentication.
    """
    # Verify the workout day exists
    workout_day = db.query(WorkoutDay).filter(WorkoutDay.id == workout_day_id).first()
    if workout_day is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WorkoutDay {workout_day_id} not found",
        )

    logger.info(
        "Reparse triggered by user %d for WorkoutDay %d",
        user.id,
        workout_day_id,
    )

    result = reparse(workout_day_id)

    return ReparseResponse(
        workout_day_id=result.get("workout_day_id", workout_day_id),
        success=result.get("success", False),
        method=result.get("method"),
        confidence=result.get("confidence", 0.0),
        flagged=result.get("flagged", False),
        error=result.get("error"),
        date=result.get("date"),
    )


@router.get("/status", response_model=ScraperStatusResponse)
async def get_scraper_status(
    user: User = Depends(get_current_user),
):
    """
    Get the scraper's current status including last run time,
    method, confidence, flagged status, and next scheduled run.
    Requires authentication.
    """
    status_data = get_last_run_status()

    return ScraperStatusResponse(
        last_run_at=status_data.get("last_run_at"),
        last_run_success=status_data.get("last_run_success"),
        last_run_method=status_data.get("last_run_method"),
        last_run_confidence=status_data.get("last_run_confidence"),
        last_run_error=status_data.get("last_run_error"),
        next_run_at=status_data.get("next_run_at"),
        scheduler_running=status_data.get("scheduler_running", False),
    )
