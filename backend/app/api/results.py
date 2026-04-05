"""
Result logging endpoints.

Handles creating workout logs and saving exercise/conditioning results,
including automatic PR detection.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth.oidc import get_current_user
from app.core.database import get_db
from app.models.logging import (
    WorkoutLog,
    ExerciseResult,
    ConditioningResult,
    PersonalRecord,
    RecordType,
)
from app.models.user import User
from app.models.workout import (
    WorkoutDay,
    Exercise,
    ConditioningWorkout,
    TrackType,
)
from app.api.schemas import (
    WorkoutLogCreate,
    WorkoutLogUpdate,
    WorkoutLogResponse,
    ExerciseResultCreate,
    ExerciseResultResponse,
    ConditioningResultCreate,
    ConditioningResultResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PR detection helpers
# ---------------------------------------------------------------------------


def _determine_record_type(reps: int) -> RecordType | None:
    """Map a rep count to the appropriate record type."""
    if reps == 1:
        return RecordType.one_rm
    elif reps == 3:
        return RecordType.three_rm
    elif reps == 5:
        return RecordType.five_rm
    return None


def _detect_exercise_prs(
    db: Session,
    user: User,
    result: ExerciseResult,
    now: datetime,
) -> bool:
    """
    Check if this exercise result sets a new personal record.

    For each set logged with weight data, determine the heaviest weight
    at 1, 3, or 5 reps and compare against existing PersonalRecord entries.

    Returns True if a PR was detected and set.
    """
    if not result.movement_id:
        return False

    weights = result.weight_per_set_lbs or []
    reps_list = result.reps_per_set or []

    if not weights or not reps_list:
        return False

    is_pr = False

    # Evaluate each set
    for i, (weight, reps) in enumerate(zip(weights, reps_list)):
        if weight is None or reps is None or weight <= 0:
            continue

        record_type = _determine_record_type(reps)
        if record_type is None:
            continue

        # Check existing record
        existing = (
            db.query(PersonalRecord)
            .filter(
                PersonalRecord.user_id == user.id,
                PersonalRecord.movement_id == result.movement_id,
                PersonalRecord.record_type == record_type,
            )
            .first()
        )

        if existing is None or weight > existing.value:
            if existing:
                existing.value = weight
                existing.reps = reps
                existing.achieved_at = now
                existing.exercise_result_id = result.id
            else:
                pr = PersonalRecord(
                    user_id=user.id,
                    movement_id=result.movement_id,
                    record_type=record_type,
                    value=weight,
                    reps=reps,
                    achieved_at=now,
                    exercise_result_id=result.id,
                )
                db.add(pr)
            db.flush()
            is_pr = True

    return is_pr


def _detect_conditioning_pr(
    db: Session,
    user: User,
    result: ConditioningResult,
) -> bool:
    """
    Check if a conditioning result for a named benchmark is a PR.

    Compares against previous ConditioningResults for the same benchmark_name.
    For timed workouts, lower is better. For AMRAP, higher rounds+reps is better.
    """
    if not result.conditioning_workout_id:
        return False

    cw = (
        db.query(ConditioningWorkout)
        .filter(ConditioningWorkout.id == result.conditioning_workout_id)
        .first()
    )
    if not cw or not cw.is_named_benchmark or not cw.benchmark_name:
        return False

    # Find all previous results for this benchmark by this user
    previous = (
        db.query(ConditioningResult)
        .join(WorkoutLog)
        .join(ConditioningWorkout)
        .filter(
            WorkoutLog.user_id == user.id,
            ConditioningWorkout.benchmark_name == cw.benchmark_name,
            ConditioningResult.id != result.id,
        )
        .all()
    )

    if not previous:
        return True  # First attempt is always a PR

    # Compare based on result type
    if result.time_seconds is not None:
        # For timed workouts, lower is better
        best_previous = min(
            (p.time_seconds for p in previous if p.time_seconds is not None),
            default=None,
        )
        if best_previous is None or result.time_seconds < best_previous:
            return True
    elif result.rounds_completed is not None or result.reps_completed is not None:
        # For AMRAP, more rounds+reps is better
        def _score(r: ConditioningResult) -> float:
            return (r.rounds_completed or 0) * 1000 + (r.reps_completed or 0)

        current_score = _score(result)
        best_previous = max((_score(p) for p in previous), default=0)
        if current_score > best_previous:
            return True

    return False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/log", response_model=WorkoutLogResponse, status_code=status.HTTP_201_CREATED)
async def create_or_get_log(
    payload: WorkoutLogCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new workout log or return an existing one for today.

    Takes the workout_day_id, track_type, and optional selected_option.
    If the user already has a log for this workout_day + track_type,
    returns the existing log instead of creating a duplicate.
    """
    # Validate workout day exists
    workout_day = db.query(WorkoutDay).filter(WorkoutDay.id == payload.workout_day_id).first()
    if workout_day is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WorkoutDay {payload.workout_day_id} not found",
        )

    # Validate track_type
    try:
        track_type = TrackType(payload.track_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid track_type: {payload.track_type}",
        )

    # Check for existing log
    existing = (
        db.query(WorkoutLog)
        .options(
            joinedload(WorkoutLog.exercise_results),
            joinedload(WorkoutLog.conditioning_results),
        )
        .filter(
            WorkoutLog.user_id == user.id,
            WorkoutLog.workout_day_id == payload.workout_day_id,
            WorkoutLog.track_type == track_type,
        )
        .first()
    )
    if existing:
        return WorkoutLogResponse.model_validate(existing)

    log = WorkoutLog(
        user_id=user.id,
        workout_day_id=payload.workout_day_id,
        track_type=track_type,
        selected_option=payload.selected_option,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    return WorkoutLogResponse.model_validate(log)


@router.post(
    "/log/{log_id}/exercises",
    response_model=list[ExerciseResultResponse],
    status_code=status.HTTP_201_CREATED,
)
async def save_exercise_results(
    log_id: int,
    results: list[ExerciseResultCreate],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save exercise results for a workout log.

    Accepts a list of ExerciseResultCreate objects. Automatically detects
    personal records by comparing against the personal_records table for
    1RM, 3RM, and 5RM thresholds.
    """
    log = db.query(WorkoutLog).filter(WorkoutLog.id == log_id).first()
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WorkoutLog {log_id} not found",
        )
    if log.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this log",
        )

    now = datetime.now(timezone.utc)
    created_results = []

    for result_data in results:
        # Resolve movement_id from exercise if not provided
        movement_id = result_data.movement_id
        if movement_id is None and result_data.exercise_id is not None:
            exercise = db.query(Exercise).filter(Exercise.id == result_data.exercise_id).first()
            if exercise:
                movement_id = exercise.movement_id

        # Upsert: update existing result for same exercise in same log
        er = None
        if result_data.exercise_id is not None:
            er = (
                db.query(ExerciseResult)
                .filter(
                    ExerciseResult.log_id == log_id,
                    ExerciseResult.exercise_id == result_data.exercise_id,
                )
                .first()
            )

        if er:
            er.movement_id = movement_id
            er.sets_completed = result_data.sets_completed
            er.reps_per_set = result_data.reps_per_set
            er.weight_per_set_lbs = result_data.weight_per_set_lbs
            er.weight_per_set_kg = result_data.weight_per_set_kg
            er.tempo_used = result_data.tempo_used
            er.rpe_actual = result_data.rpe_actual
            er.notes = result_data.notes
            er.is_pr = False
        else:
            er = ExerciseResult(
                log_id=log_id,
                exercise_id=result_data.exercise_id,
                movement_id=movement_id,
                sets_completed=result_data.sets_completed,
                reps_per_set=result_data.reps_per_set,
                weight_per_set_lbs=result_data.weight_per_set_lbs,
                weight_per_set_kg=result_data.weight_per_set_kg,
                tempo_used=result_data.tempo_used,
                rpe_actual=result_data.rpe_actual,
                notes=result_data.notes,
                is_pr=False,
            )
            db.add(er)

        db.flush()

        # PR detection
        is_pr = _detect_exercise_prs(db, user, er, now)
        if is_pr:
            er.is_pr = True

        created_results.append(er)

    db.commit()

    # Refresh all results for response
    response = []
    for er in created_results:
        db.refresh(er)
        response.append(ExerciseResultResponse.model_validate(er))

    return response


@router.post(
    "/log/{log_id}/conditioning",
    response_model=list[ConditioningResultResponse],
    status_code=status.HTTP_201_CREATED,
)
async def save_conditioning_results(
    log_id: int,
    results: list[ConditioningResultCreate],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save conditioning results for a workout log.

    Detects PRs for named benchmark workouts by comparing against
    previous results for the same benchmark_name.
    """
    log = db.query(WorkoutLog).filter(WorkoutLog.id == log_id).first()
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WorkoutLog {log_id} not found",
        )
    if log.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this log",
        )

    created_results = []

    for result_data in results:
        # Upsert: update existing result for same conditioning workout in same log
        cr = None
        if result_data.conditioning_workout_id is not None:
            cr = (
                db.query(ConditioningResult)
                .filter(
                    ConditioningResult.log_id == log_id,
                    ConditioningResult.conditioning_workout_id == result_data.conditioning_workout_id,
                )
                .first()
            )

        if cr:
            cr.result_type = result_data.result_type
            cr.rounds_completed = result_data.rounds_completed
            cr.reps_completed = result_data.reps_completed
            cr.time_seconds = result_data.time_seconds
            cr.total_reps = result_data.total_reps
            cr.notes = result_data.notes
            cr.is_named_benchmark = result_data.is_named_benchmark
        else:
            cr = ConditioningResult(
                log_id=log_id,
                conditioning_workout_id=result_data.conditioning_workout_id,
                result_type=result_data.result_type,
                rounds_completed=result_data.rounds_completed,
                reps_completed=result_data.reps_completed,
                time_seconds=result_data.time_seconds,
                total_reps=result_data.total_reps,
                notes=result_data.notes,
                is_named_benchmark=result_data.is_named_benchmark,
            )
            db.add(cr)

        db.flush()

        # Detect benchmark PRs
        if result_data.is_named_benchmark:
            is_pr = _detect_conditioning_pr(db, user, cr)
            if is_pr:
                cr.is_named_benchmark = True
                logger.info(
                    "Conditioning PR detected for user %d on benchmark",
                    user.id,
                )

        created_results.append(cr)

    db.commit()

    response = []
    for cr in created_results:
        db.refresh(cr)
        response.append(ConditioningResultResponse.model_validate(cr))

    return response


@router.get("/log/{workout_day_id}", response_model=WorkoutLogResponse | None)
async def get_log_for_workout_day(
    workout_day_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the authenticated user's log for a specific workout day.
    Returns null if no log exists.
    """
    log = (
        db.query(WorkoutLog)
        .options(
            joinedload(WorkoutLog.exercise_results),
            joinedload(WorkoutLog.conditioning_results),
        )
        .filter(
            WorkoutLog.user_id == user.id,
            WorkoutLog.workout_day_id == workout_day_id,
        )
        .first()
    )

    if log is None:
        return None

    return WorkoutLogResponse.model_validate(log)


@router.put("/log/{log_id}", response_model=WorkoutLogResponse)
async def update_log(
    log_id: int,
    payload: WorkoutLogUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a workout log's overall_notes or completed status.
    """
    log = (
        db.query(WorkoutLog)
        .options(
            joinedload(WorkoutLog.exercise_results),
            joinedload(WorkoutLog.conditioning_results),
        )
        .filter(WorkoutLog.id == log_id)
        .first()
    )
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WorkoutLog {log_id} not found",
        )
    if log.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this log",
        )

    if payload.overall_notes is not None:
        log.overall_notes = payload.overall_notes
    if payload.completed is not None:
        log.completed = payload.completed

    db.commit()
    db.refresh(log)

    return WorkoutLogResponse.model_validate(log)
