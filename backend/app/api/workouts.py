"""
Workout endpoints.

Provides access to parsed workout data by date, calendar views,
and inline block editing.
"""

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import extract
from sqlalchemy.orm import Session, joinedload

from app.auth.oidc import get_current_user, get_optional_user
from app.core.cache import cache_get, cache_set, cache_delete
from app.core.database import get_db
from app.models.logging import ExerciseResult, WorkoutLog
from app.models.user import User
from app.models.workout import (
    WorkoutDay,
    WorkoutTrack,
    WorkoutBlock,
    Exercise,
    ConditioningWorkout,
    ConditioningInterval,
    Movement,
    BlockType,
)
from app.api.schemas import (
    WorkoutDayResponse,
    WorkoutTrackResponse,
    WorkoutBlockResponse,
    ExerciseResponse,
    ExerciseResultResponse,
    ConditioningWorkoutResponse,
    ConditioningIntervalResponse,
    MovementResponse,
    CalendarResponse,
    CalendarDayEntry,
    BlockUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_workout_day(db: Session, target_date: date) -> WorkoutDay:
    """Load a WorkoutDay with all nested relationships eagerly loaded."""
    workout_day = (
        db.query(WorkoutDay)
        .options(
            joinedload(WorkoutDay.tracks)
            .joinedload(WorkoutTrack.blocks)
            .joinedload(WorkoutBlock.exercises)
            .joinedload(Exercise.movement),
            joinedload(WorkoutDay.tracks)
            .joinedload(WorkoutTrack.blocks)
            .joinedload(WorkoutBlock.conditioning_workouts)
            .joinedload(ConditioningWorkout.intervals),
        )
        .filter(WorkoutDay.date == target_date)
        .first()
    )
    return workout_day


def _build_workout_response(
    workout_day: WorkoutDay,
    user: User | None,
    db: Session,
) -> WorkoutDayResponse:
    """
    Convert a WorkoutDay ORM object into a full response schema,
    optionally attaching the user's last results to each exercise.
    """
    # Pre-fetch user's last results for each movement if authenticated
    last_results_by_movement: dict[int, ExerciseResult] = {}
    if user is not None:
        # Collect all movement IDs in this workout
        movement_ids = set()
        for track in workout_day.tracks:
            for block in track.blocks:
                for exercise in block.exercises:
                    if exercise.movement_id:
                        movement_ids.add(exercise.movement_id)

        if movement_ids:
            # For each movement, get the user's most recent ExerciseResult
            for mid in movement_ids:
                result = (
                    db.query(ExerciseResult)
                    .join(WorkoutLog)
                    .filter(
                        WorkoutLog.user_id == user.id,
                        ExerciseResult.movement_id == mid,
                    )
                    .order_by(WorkoutLog.logged_at.desc())
                    .first()
                )
                if result:
                    last_results_by_movement[mid] = result

    # Build the nested response
    tracks = []
    for track in sorted(workout_day.tracks, key=lambda t: t.display_order):
        blocks = []
        for block in sorted(track.blocks, key=lambda b: b.display_order):
            exercises = []
            for ex in sorted(block.exercises, key=lambda e: e.display_order):
                movement_resp = None
                if ex.movement:
                    movement_resp = MovementResponse.model_validate(ex.movement)

                last_result = None
                if ex.movement_id and ex.movement_id in last_results_by_movement:
                    last_result = ExerciseResultResponse.model_validate(
                        last_results_by_movement[ex.movement_id]
                    )

                exercises.append(
                    ExerciseResponse(
                        id=ex.id,
                        movement_id=ex.movement_id,
                        movement=movement_resp,
                        display_order=ex.display_order,
                        sets=ex.sets,
                        reps_min=ex.reps_min,
                        reps_max=ex.reps_max,
                        duration_seconds=ex.duration_seconds,
                        tempo=ex.tempo,
                        rpe_min=ex.rpe_min,
                        rpe_max=ex.rpe_max,
                        percent_1rm_min=ex.percent_1rm_min,
                        percent_1rm_max=ex.percent_1rm_max,
                        rest_seconds=ex.rest_seconds,
                        notes=ex.notes,
                        is_alternative=ex.is_alternative,
                        alternative_group_id=ex.alternative_group_id,
                        last_result=last_result,
                    )
                )

            conditioning_workouts = []
            for cw in block.conditioning_workouts:
                intervals = [
                    ConditioningIntervalResponse.model_validate(iv)
                    for iv in sorted(cw.intervals, key=lambda i: i.interval_order)
                ]
                conditioning_workouts.append(
                    ConditioningWorkoutResponse(
                        id=cw.id,
                        format=cw.format.value if cw.format else "amrap",
                        duration_minutes=cw.duration_minutes,
                        rounds=cw.rounds,
                        time_cap_minutes=cw.time_cap_minutes,
                        is_partner=cw.is_partner,
                        is_named_benchmark=cw.is_named_benchmark,
                        benchmark_name=cw.benchmark_name,
                        intervals=intervals,
                    )
                )

            blocks.append(
                WorkoutBlockResponse(
                    id=block.id,
                    label=block.label,
                    block_type=block.block_type.value if block.block_type else "other",
                    raw_text=block.raw_text,
                    display_order=block.display_order,
                    exercises=exercises,
                    conditioning_workouts=conditioning_workouts,
                )
            )

        tracks.append(
            WorkoutTrackResponse(
                id=track.id,
                track_type=track.track_type.value if track.track_type else "fitness_performance",
                display_order=track.display_order,
                blocks=blocks,
            )
        )

    return WorkoutDayResponse(
        id=workout_day.id,
        date=workout_day.date,
        source_url=workout_day.source_url,
        raw_text=workout_day.raw_text,
        parse_confidence=workout_day.parse_confidence,
        parse_flagged=workout_day.parse_flagged,
        parse_method=workout_day.parse_method.value if workout_day.parse_method else None,
        created_at=workout_day.created_at,
        updated_at=workout_day.updated_at,
        tracks=tracks,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/today", response_model=WorkoutDayResponse)
async def get_today_workout(
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Get today's parsed workout with all tracks, blocks, exercises,
    and conditioning details. Uses in-memory cache for performance.
    If authenticated, includes the user's last results for each exercise.
    """
    today = date.today()

    # For unauthenticated users, try cache first
    if user is None:
        cache_key = f"workout:{today.isoformat()}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    workout_day = _load_workout_day(db, today)
    if workout_day is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No workout found for {today.isoformat()}",
        )

    response = _build_workout_response(workout_day, user, db)

    # Cache unauthenticated responses
    if user is None:
        cache_set(f"workout:{today.isoformat()}", response)

    return response


@router.get("/calendar/{year}/{month}", response_model=CalendarResponse)
async def get_calendar(
    year: int,
    month: int,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Get a list of dates in the given month that have workouts,
    and which ones the authenticated user has logged results for.
    """
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Month must be between 1 and 12",
        )

    workout_days = (
        db.query(WorkoutDay.id, WorkoutDay.date)
        .filter(
            extract("year", WorkoutDay.date) == year,
            extract("month", WorkoutDay.date) == month,
        )
        .all()
    )

    # Determine which workout days the user has logged
    logged_day_ids: set[int] = set()
    if user is not None and workout_days:
        wd_ids = [wd.id for wd in workout_days]
        logged_logs = (
            db.query(WorkoutLog.workout_day_id)
            .filter(
                WorkoutLog.user_id == user.id,
                WorkoutLog.workout_day_id.in_(wd_ids),
            )
            .all()
        )
        logged_day_ids = {log.workout_day_id for log in logged_logs}

    days = [
        CalendarDayEntry(
            date=wd.date,
            has_workout=True,
            user_logged=wd.id in logged_day_ids,
        )
        for wd in workout_days
    ]

    return CalendarResponse(year=year, month=month, days=days)


@router.get("/{date_str}", response_model=WorkoutDayResponse)
async def get_workout_by_date(
    date_str: str,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Get the parsed workout for a specific date (YYYY-MM-DD format).
    If authenticated, includes the user's last results for each exercise.
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    # For unauthenticated users, try cache first
    if user is None:
        cache_key = f"workout:{target_date.isoformat()}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

    workout_day = _load_workout_day(db, target_date)
    if workout_day is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No workout found for {target_date.isoformat()}",
        )

    response = _build_workout_response(workout_day, user, db)

    if user is None:
        cache_set(f"workout:{target_date.isoformat()}", response)

    return response


@router.put("/blocks/{block_id}", response_model=WorkoutBlockResponse)
async def update_block(
    block_id: int,
    payload: BlockUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a workout block's structured data via the inline editor.
    Re-validates and updates parse_confidence on the parent WorkoutDay.
    Requires authentication.
    """
    block = (
        db.query(WorkoutBlock)
        .options(
            joinedload(WorkoutBlock.exercises).joinedload(Exercise.movement),
            joinedload(WorkoutBlock.conditioning_workouts)
            .joinedload(ConditioningWorkout.intervals),
        )
        .filter(WorkoutBlock.id == block_id)
        .first()
    )
    if block is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block {block_id} not found",
        )

    # Update scalar fields
    if payload.label is not None:
        block.label = payload.label
    if payload.block_type is not None:
        try:
            block.block_type = BlockType(payload.block_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid block_type: {payload.block_type}",
            )
    if payload.raw_text is not None:
        block.raw_text = payload.raw_text

    # If exercises provided, replace them
    if payload.exercises is not None:
        # Delete existing exercises
        for ex in block.exercises:
            db.delete(ex)
        db.flush()

        for idx, ex_data in enumerate(payload.exercises):
            movement_id = ex_data.get("movement_id")
            exercise = Exercise(
                block_id=block.id,
                movement_id=movement_id,
                display_order=ex_data.get("display_order", idx),
                sets=ex_data.get("sets"),
                reps_min=ex_data.get("reps_min"),
                reps_max=ex_data.get("reps_max"),
                duration_seconds=ex_data.get("duration_seconds"),
                tempo=ex_data.get("tempo"),
                rpe_min=ex_data.get("rpe_min"),
                rpe_max=ex_data.get("rpe_max"),
                percent_1rm_min=ex_data.get("percent_1rm_min"),
                percent_1rm_max=ex_data.get("percent_1rm_max"),
                rest_seconds=ex_data.get("rest_seconds"),
                notes=ex_data.get("notes"),
                is_alternative=ex_data.get("is_alternative", False),
                alternative_group_id=ex_data.get("alternative_group_id"),
            )
            db.add(exercise)

    # Bump the parent WorkoutDay confidence (manual edit = high confidence)
    track = db.query(WorkoutTrack).filter(WorkoutTrack.id == block.track_id).first()
    if track:
        workout_day = (
            db.query(WorkoutDay)
            .filter(WorkoutDay.id == track.workout_day_id)
            .first()
        )
        if workout_day:
            workout_day.parse_confidence = 1.0
            workout_day.updated_at = datetime.now()
            # Invalidate cache
            cache_delete(f"workout:{workout_day.date.isoformat()}")

    db.commit()

    # Reload for response
    db.refresh(block)
    block = (
        db.query(WorkoutBlock)
        .options(
            joinedload(WorkoutBlock.exercises).joinedload(Exercise.movement),
            joinedload(WorkoutBlock.conditioning_workouts)
            .joinedload(ConditioningWorkout.intervals),
        )
        .filter(WorkoutBlock.id == block_id)
        .first()
    )

    exercises = []
    for ex in sorted(block.exercises, key=lambda e: e.display_order):
        movement_resp = None
        if ex.movement:
            movement_resp = MovementResponse.model_validate(ex.movement)
        exercises.append(
            ExerciseResponse(
                id=ex.id,
                movement_id=ex.movement_id,
                movement=movement_resp,
                display_order=ex.display_order,
                sets=ex.sets,
                reps_min=ex.reps_min,
                reps_max=ex.reps_max,
                duration_seconds=ex.duration_seconds,
                tempo=ex.tempo,
                rpe_min=ex.rpe_min,
                rpe_max=ex.rpe_max,
                percent_1rm_min=ex.percent_1rm_min,
                percent_1rm_max=ex.percent_1rm_max,
                rest_seconds=ex.rest_seconds,
                notes=ex.notes,
                is_alternative=ex.is_alternative,
                alternative_group_id=ex.alternative_group_id,
            )
        )

    conditioning_workouts = []
    for cw in block.conditioning_workouts:
        intervals = [
            ConditioningIntervalResponse.model_validate(iv)
            for iv in sorted(cw.intervals, key=lambda i: i.interval_order)
        ]
        conditioning_workouts.append(
            ConditioningWorkoutResponse(
                id=cw.id,
                format=cw.format.value if cw.format else "amrap",
                duration_minutes=cw.duration_minutes,
                rounds=cw.rounds,
                time_cap_minutes=cw.time_cap_minutes,
                is_partner=cw.is_partner,
                is_named_benchmark=cw.is_named_benchmark,
                benchmark_name=cw.benchmark_name,
                intervals=intervals,
            )
        )

    return WorkoutBlockResponse(
        id=block.id,
        label=block.label,
        block_type=block.block_type.value if block.block_type else "other",
        raw_text=block.raw_text,
        display_order=block.display_order,
        exercises=exercises,
        conditioning_workouts=conditioning_workouts,
    )
