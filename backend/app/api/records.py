"""
Personal records endpoints.

Provides access to user PRs grouped by movement and record type,
plus benchmark workout comparisons.
"""

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.auth.oidc import get_current_user
from app.core.database import get_db
from app.models.logging import (
    ConditioningResult,
    PersonalRecord,
    WorkoutLog,
)
from app.models.user import User
from app.models.workout import (
    ConditioningWorkout,
    Movement,
    MovementType,
    WorkoutDay,
)
from app.api.schemas import (
    PersonalRecordResponse,
    GroupedPersonalRecords,
    MovementResponse,
    BenchmarkAttempt,
    BenchmarkGroup,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[GroupedPersonalRecords])
async def get_personal_records(
    movement_type: str | None = Query(None, description="Filter by movement type"),
    muscle_group: str | None = Query(None, description="Filter by muscle group"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all personal records for the authenticated user, grouped by
    movement and then by record_type.

    Each record includes the movement name, value, date, and
    workout context.

    Filterable by movement_type and muscle_group.
    """
    query = (
        db.query(PersonalRecord)
        .options(joinedload(PersonalRecord.movement))
        .filter(PersonalRecord.user_id == user.id)
    )

    # Apply movement-level filters via a subquery
    if movement_type or muscle_group:
        query = query.join(Movement)
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

    records = query.order_by(PersonalRecord.movement_id).all()

    # Group by movement
    grouped: dict[int, dict] = {}
    for pr in records:
        mid = pr.movement_id
        if mid not in grouped:
            grouped[mid] = {
                "movement": pr.movement,
                "records_map": {},
            }
        record_type_str = pr.record_type.value if pr.record_type else "unknown"
        grouped[mid]["records_map"][record_type_str] = PersonalRecordResponse(
            id=pr.id,
            user_id=pr.user_id,
            movement_id=pr.movement_id,
            movement_name=pr.movement.name if pr.movement else None,
            record_type=record_type_str,
            value=pr.value,
            reps=pr.reps,
            set_count=pr.set_count,
            tempo=pr.tempo,
            notes=pr.notes,
            achieved_at=pr.achieved_at,
            exercise_result_id=pr.exercise_result_id,
        )

    result = []
    for mid, data in grouped.items():
        result.append(
            GroupedPersonalRecords(
                movement=MovementResponse.model_validate(data["movement"]),
                records=data["records_map"],
            )
        )

    return result


@router.get("/benchmarks", response_model=list[BenchmarkGroup])
async def get_benchmark_results(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all named benchmark workout results for the authenticated user,
    grouped by benchmark_name with all attempts for side-by-side comparison.
    """
    results = (
        db.query(ConditioningResult, WorkoutDay.date)
        .join(WorkoutLog, ConditioningResult.log_id == WorkoutLog.id)
        .join(WorkoutDay, WorkoutLog.workout_day_id == WorkoutDay.id)
        .join(
            ConditioningWorkout,
            ConditioningResult.conditioning_workout_id == ConditioningWorkout.id,
        )
        .filter(
            WorkoutLog.user_id == user.id,
            ConditioningWorkout.is_named_benchmark.is_(True),
            ConditioningWorkout.benchmark_name.isnot(None),
        )
        .order_by(WorkoutDay.date.asc())
        .all()
    )

    # Group by benchmark name
    grouped: dict[str, list[BenchmarkAttempt]] = defaultdict(list)
    for cr, workout_date in results:
        # Look up benchmark name via the conditioning workout
        cw = (
            db.query(ConditioningWorkout)
            .filter(ConditioningWorkout.id == cr.conditioning_workout_id)
            .first()
        )
        if not cw or not cw.benchmark_name:
            continue

        grouped[cw.benchmark_name].append(
            BenchmarkAttempt(
                date=workout_date,
                result_type=cr.result_type.value if cr.result_type else None,
                rounds_completed=cr.rounds_completed,
                reps_completed=cr.reps_completed,
                time_seconds=cr.time_seconds,
                total_reps=cr.total_reps,
                notes=cr.notes,
            )
        )

    return [
        BenchmarkGroup(benchmark_name=name, attempts=attempts)
        for name, attempts in sorted(grouped.items())
    ]
