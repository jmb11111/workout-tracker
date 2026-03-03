"""
Admin endpoints.

Provides tools for reviewing flagged workout parses that need
manual attention due to low confidence scores.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.oidc import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.workout import WorkoutDay
from app.api.schemas import FlaggedWorkoutResponse, ReviewResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/flagged", response_model=list[FlaggedWorkoutResponse])
async def list_flagged_workouts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all workout days where parse_flagged is true.

    Returns date, parse confidence, parse method, and raw text
    for each flagged workout so the admin can review and fix.
    Requires authentication.
    """
    flagged = (
        db.query(WorkoutDay)
        .filter(WorkoutDay.parse_flagged.is_(True))
        .order_by(WorkoutDay.date.desc())
        .all()
    )

    return [
        FlaggedWorkoutResponse(
            id=wd.id,
            date=wd.date,
            parse_confidence=wd.parse_confidence,
            parse_method=wd.parse_method.value if wd.parse_method else None,
            parse_flagged=wd.parse_flagged,
            raw_text=wd.raw_text,
        )
        for wd in flagged
    ]


@router.post("/flagged/{workout_day_id}/review", response_model=ReviewResponse)
async def review_flagged_workout(
    workout_day_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark a flagged workout as reviewed by setting parse_flagged to false.

    This indicates an admin has reviewed the parse output and
    either corrected it (via the block editor) or confirmed it
    is acceptable.
    Requires authentication.
    """
    workout_day = db.query(WorkoutDay).filter(WorkoutDay.id == workout_day_id).first()
    if workout_day is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WorkoutDay {workout_day_id} not found",
        )

    if not workout_day.parse_flagged:
        return ReviewResponse(
            workout_day_id=workout_day_id,
            parse_flagged=False,
            message="Workout was already marked as reviewed",
        )

    workout_day.parse_flagged = False
    workout_day.updated_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(
        "User %d marked WorkoutDay %d as reviewed",
        user.id,
        workout_day_id,
    )

    return ReviewResponse(
        workout_day_id=workout_day_id,
        parse_flagged=False,
        message="Marked as reviewed",
    )
