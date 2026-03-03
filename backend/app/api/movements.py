"""
Movement endpoints.

Provides movement listing, search, history for a user, and
aggregated stats for charting.
"""

import logging
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth.oidc import get_current_user, get_optional_user
from app.core.database import get_db
from app.models.logging import ExerciseResult, PersonalRecord, RecordType, WorkoutLog
from app.models.user import User
from app.models.workout import Exercise, Movement, MovementType, WorkoutDay
from app.api.schemas import (
    MovementResponse,
    MovementHistoryEntry,
    MovementHistoryResponse,
    MovementStatsResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[MovementResponse])
async def list_movements(
    q: str | None = Query(None, description="Search query for movement name"),
    movement_type: str | None = Query(None, description="Filter by movement type"),
    muscle_group: str | None = Query(None, description="Filter by muscle group"),
    db: Session = Depends(get_db),
):
    """
    List all movements with optional search and filters.

    Query params:
    - q: partial name match (case-insensitive)
    - movement_type: one of barbell, dumbbell, kettlebell, bodyweight, machine, cardio, other
    - muscle_group: filter by muscle group tag
    """
    query = db.query(Movement)

    if q:
        query = query.filter(Movement.name.ilike(f"%{q}%"))

    if movement_type:
        try:
            mt = MovementType(movement_type)
            query = query.filter(Movement.movement_type == mt)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid movement_type: {movement_type}",
            )

    if muscle_group:
        query = query.filter(Movement.muscle_groups.any(muscle_group))

    movements = query.order_by(Movement.name).all()
    return [MovementResponse.model_validate(m) for m in movements]


@router.get("/{movement_id}", response_model=MovementResponse)
async def get_movement(
    movement_id: int,
    db: Session = Depends(get_db),
):
    """Get details for a specific movement by ID."""
    movement = db.query(Movement).filter(Movement.id == movement_id).first()
    if movement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movement {movement_id} not found",
        )
    return MovementResponse.model_validate(movement)


@router.get("/{movement_id}/history", response_model=MovementHistoryResponse)
async def get_movement_history(
    movement_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a chronological log of every time the authenticated user
    performed this movement.

    Includes date, sets, reps, weight, RPE, and PR flags.
    Supports pagination.
    """
    movement = db.query(Movement).filter(Movement.id == movement_id).first()
    if movement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movement {movement_id} not found",
        )

    # Count total entries
    total = (
        db.query(func.count(ExerciseResult.id))
        .join(WorkoutLog)
        .filter(
            ExerciseResult.movement_id == movement_id,
            WorkoutLog.user_id == user.id,
        )
        .scalar()
    )

    # Fetch paginated results with their workout log dates
    results = (
        db.query(ExerciseResult, WorkoutLog.logged_at, WorkoutDay.date)
        .join(WorkoutLog, ExerciseResult.log_id == WorkoutLog.id)
        .join(WorkoutDay, WorkoutLog.workout_day_id == WorkoutDay.id)
        .filter(
            ExerciseResult.movement_id == movement_id,
            WorkoutLog.user_id == user.id,
        )
        .order_by(WorkoutDay.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    history = []
    for er, logged_at, workout_date in results:
        history.append(
            MovementHistoryEntry(
                date=workout_date,
                exercise_result_id=er.id,
                sets_completed=er.sets_completed,
                reps_per_set=er.reps_per_set,
                weight_per_set_lbs=er.weight_per_set_lbs,
                weight_per_set_kg=er.weight_per_set_kg,
                rpe_actual=er.rpe_actual,
                notes=er.notes,
                is_pr=er.is_pr,
            )
        )

    return MovementHistoryResponse(
        movement=MovementResponse.model_validate(movement),
        history=history,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{movement_id}/stats", response_model=MovementStatsResponse)
async def get_movement_stats(
    movement_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get aggregated stats for a movement:
    - Best weights at 1RM, 3RM, 5RM
    - Total number of sessions
    - Volume over time data points for charting
    """
    movement = db.query(Movement).filter(Movement.id == movement_id).first()
    if movement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movement {movement_id} not found",
        )

    # Get PRs for this movement
    prs = (
        db.query(PersonalRecord)
        .filter(
            PersonalRecord.user_id == user.id,
            PersonalRecord.movement_id == movement_id,
        )
        .all()
    )

    best_1rm = None
    best_3rm = None
    best_5rm = None
    for pr in prs:
        if pr.record_type == RecordType.one_rm:
            best_1rm = pr.value
        elif pr.record_type == RecordType.three_rm:
            best_3rm = pr.value
        elif pr.record_type == RecordType.five_rm:
            best_5rm = pr.value

    # Count total sessions
    total_sessions = (
        db.query(func.count(func.distinct(WorkoutLog.id)))
        .join(ExerciseResult, ExerciseResult.log_id == WorkoutLog.id)
        .filter(
            WorkoutLog.user_id == user.id,
            ExerciseResult.movement_id == movement_id,
        )
        .scalar()
    )

    # Volume over time: for each session, calculate total volume (sets x reps x weight)
    results = (
        db.query(ExerciseResult, WorkoutDay.date)
        .join(WorkoutLog, ExerciseResult.log_id == WorkoutLog.id)
        .join(WorkoutDay, WorkoutLog.workout_day_id == WorkoutDay.id)
        .filter(
            WorkoutLog.user_id == user.id,
            ExerciseResult.movement_id == movement_id,
        )
        .order_by(WorkoutDay.date.asc())
        .all()
    )

    volume_over_time = []
    for er, workout_date in results:
        weights = er.weight_per_set_lbs or []
        reps = er.reps_per_set or []
        volume = 0.0
        max_weight = 0.0
        for w, r in zip(weights, reps):
            if w and r:
                volume += w * r
                max_weight = max(max_weight, w)

        volume_over_time.append({
            "date": workout_date.isoformat(),
            "volume": volume,
            "max_weight": max_weight,
            "sets": er.sets_completed or len(weights),
        })

    return MovementStatsResponse(
        movement=MovementResponse.model_validate(movement),
        best_1rm=best_1rm,
        best_3rm=best_3rm,
        best_5rm=best_5rm,
        total_sessions=total_sessions or 0,
        volume_over_time=volume_over_time,
    )
