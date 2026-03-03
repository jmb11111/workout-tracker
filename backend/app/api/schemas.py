"""
Pydantic schemas for all API request/response models.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared / base
# ---------------------------------------------------------------------------


class OrmBase(BaseModel):
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Movements
# ---------------------------------------------------------------------------


class MovementResponse(OrmBase):
    id: int
    name: str
    movement_type: str
    is_named_benchmark: bool
    aliases: list[str] = []
    muscle_groups: list[str] = []


class MovementHistoryEntry(OrmBase):
    date: date
    exercise_result_id: int
    sets_completed: Optional[int] = None
    reps_per_set: Optional[list[int]] = None
    weight_per_set_lbs: Optional[list[float]] = None
    weight_per_set_kg: Optional[list[float]] = None
    rpe_actual: Optional[float] = None
    notes: Optional[str] = None
    is_pr: bool = False


class MovementHistoryResponse(BaseModel):
    movement: MovementResponse
    history: list[MovementHistoryEntry]
    total: int
    page: int
    page_size: int


class MovementStatsResponse(BaseModel):
    movement: MovementResponse
    best_1rm: Optional[float] = None
    best_3rm: Optional[float] = None
    best_5rm: Optional[float] = None
    total_sessions: int = 0
    volume_over_time: list[dict] = []


# ---------------------------------------------------------------------------
# Conditioning intervals
# ---------------------------------------------------------------------------


class ConditioningIntervalResponse(OrmBase):
    id: int
    interval_order: int
    modality: str
    distance_meters: Optional[int] = None
    calories: Optional[int] = None
    duration_seconds: Optional[int] = None
    effort_percent: Optional[int] = None


# ---------------------------------------------------------------------------
# Conditioning workouts
# ---------------------------------------------------------------------------


class ConditioningWorkoutResponse(OrmBase):
    id: int
    format: str
    duration_minutes: Optional[float] = None
    rounds: Optional[int] = None
    time_cap_minutes: Optional[float] = None
    is_partner: bool = False
    is_named_benchmark: bool = False
    benchmark_name: Optional[str] = None
    intervals: list[ConditioningIntervalResponse] = []


# ---------------------------------------------------------------------------
# Exercises
# ---------------------------------------------------------------------------


class ExerciseResponse(OrmBase):
    id: int
    movement_id: Optional[int] = None
    movement: Optional[MovementResponse] = None
    display_order: int = 0
    sets: Optional[int] = None
    reps_min: Optional[int] = None
    reps_max: Optional[int] = None
    duration_seconds: Optional[int] = None
    tempo: Optional[str] = None
    rpe_min: Optional[float] = None
    rpe_max: Optional[float] = None
    percent_1rm_min: Optional[float] = None
    percent_1rm_max: Optional[float] = None
    rest_seconds: Optional[int] = None
    notes: Optional[str] = None
    is_alternative: bool = False
    alternative_group_id: Optional[int] = None
    # Inline last-result chip data (populated when user is authenticated)
    last_result: Optional["ExerciseResultResponse"] = None


# ---------------------------------------------------------------------------
# Workout blocks
# ---------------------------------------------------------------------------


class WorkoutBlockResponse(OrmBase):
    id: int
    label: Optional[str] = None
    block_type: str
    raw_text: Optional[str] = None
    display_order: int = 0
    exercises: list[ExerciseResponse] = []
    conditioning_workouts: list[ConditioningWorkoutResponse] = []


class BlockUpdate(BaseModel):
    label: Optional[str] = None
    block_type: Optional[str] = None
    raw_text: Optional[str] = None
    exercises: Optional[list[dict]] = None
    conditioning: Optional[dict] = None


# ---------------------------------------------------------------------------
# Workout tracks
# ---------------------------------------------------------------------------


class WorkoutTrackResponse(OrmBase):
    id: int
    track_type: str
    display_order: int = 0
    blocks: list[WorkoutBlockResponse] = []


# ---------------------------------------------------------------------------
# Workout day
# ---------------------------------------------------------------------------


class WorkoutDayResponse(OrmBase):
    id: int
    date: date
    source_url: Optional[str] = None
    raw_text: Optional[str] = None
    parse_confidence: float = 0.0
    parse_flagged: bool = False
    parse_method: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tracks: list[WorkoutTrackResponse] = []


class CalendarDayEntry(BaseModel):
    date: date
    has_workout: bool = True
    user_logged: bool = False


class CalendarResponse(BaseModel):
    year: int
    month: int
    days: list[CalendarDayEntry]


# ---------------------------------------------------------------------------
# Exercise results
# ---------------------------------------------------------------------------


class ExerciseResultCreate(BaseModel):
    exercise_id: Optional[int] = None
    movement_id: Optional[int] = None
    sets_completed: Optional[int] = None
    reps_per_set: Optional[list[int]] = None
    weight_per_set_lbs: Optional[list[float]] = None
    weight_per_set_kg: Optional[list[float]] = None
    tempo_used: Optional[str] = None
    rpe_actual: Optional[float] = None
    notes: Optional[str] = None


class ExerciseResultResponse(OrmBase):
    id: int
    log_id: int
    exercise_id: Optional[int] = None
    movement_id: Optional[int] = None
    sets_completed: Optional[int] = None
    reps_per_set: Optional[list[int]] = None
    weight_per_set_lbs: Optional[list[float]] = None
    weight_per_set_kg: Optional[list[float]] = None
    tempo_used: Optional[str] = None
    rpe_actual: Optional[float] = None
    notes: Optional[str] = None
    is_pr: bool = False


# ---------------------------------------------------------------------------
# Conditioning results
# ---------------------------------------------------------------------------


class ConditioningResultCreate(BaseModel):
    conditioning_workout_id: Optional[int] = None
    result_type: Optional[str] = None
    rounds_completed: Optional[int] = None
    reps_completed: Optional[int] = None
    time_seconds: Optional[int] = None
    total_reps: Optional[int] = None
    notes: Optional[str] = None
    is_named_benchmark: bool = False


class ConditioningResultResponse(OrmBase):
    id: int
    log_id: int
    conditioning_workout_id: Optional[int] = None
    result_type: Optional[str] = None
    rounds_completed: Optional[int] = None
    reps_completed: Optional[int] = None
    time_seconds: Optional[int] = None
    total_reps: Optional[int] = None
    notes: Optional[str] = None
    is_named_benchmark: bool = False


# ---------------------------------------------------------------------------
# Workout logs
# ---------------------------------------------------------------------------


class WorkoutLogCreate(BaseModel):
    workout_day_id: int
    track_type: str
    selected_option: Optional[str] = None


class WorkoutLogUpdate(BaseModel):
    overall_notes: Optional[str] = None
    completed: Optional[bool] = None


class WorkoutLogResponse(OrmBase):
    id: int
    user_id: int
    workout_day_id: int
    track_type: str
    logged_at: Optional[datetime] = None
    overall_notes: Optional[str] = None
    completed: bool = False
    selected_option: Optional[str] = None
    exercise_results: list[ExerciseResultResponse] = []
    conditioning_results: list[ConditioningResultResponse] = []


# ---------------------------------------------------------------------------
# Personal records
# ---------------------------------------------------------------------------


class PersonalRecordResponse(OrmBase):
    id: int
    user_id: int
    movement_id: int
    movement_name: Optional[str] = None
    record_type: str
    value: float
    reps: Optional[int] = None
    set_count: Optional[int] = None
    tempo: Optional[str] = None
    notes: Optional[str] = None
    achieved_at: Optional[datetime] = None
    exercise_result_id: Optional[int] = None


class GroupedPersonalRecords(BaseModel):
    """PRs grouped by movement, then by record_type."""
    movement: MovementResponse
    records: dict[str, PersonalRecordResponse]


class BenchmarkAttempt(BaseModel):
    date: Optional[date] = None
    result_type: Optional[str] = None
    rounds_completed: Optional[int] = None
    reps_completed: Optional[int] = None
    time_seconds: Optional[int] = None
    total_reps: Optional[int] = None
    notes: Optional[str] = None


class BenchmarkGroup(BaseModel):
    benchmark_name: str
    attempts: list[BenchmarkAttempt]


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class UserResponse(OrmBase):
    id: int
    authentik_sub: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    weight_unit: str
    dark_mode: bool = True
    created_at: Optional[datetime] = None


class UserUpdate(BaseModel):
    weight_unit: Optional[str] = None
    dark_mode: Optional[bool] = None


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


class ScraperStatusResponse(BaseModel):
    last_run_at: Optional[str] = None
    last_run_success: Optional[bool] = None
    last_run_method: Optional[str] = None
    last_run_confidence: Optional[float] = None
    last_run_error: Optional[str] = None
    next_run_at: Optional[str] = None
    scheduler_running: bool = False


class ScraperTriggerResponse(BaseModel):
    date: str
    success: bool
    method: Optional[str] = None
    confidence: float = 0.0
    flagged: bool = False
    error: Optional[str] = None
    workout_day_id: Optional[int] = None


class ReparseResponse(BaseModel):
    workout_day_id: int
    success: bool
    method: Optional[str] = None
    confidence: float = 0.0
    flagged: bool = False
    error: Optional[str] = None
    date: Optional[str] = None


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


class FlaggedWorkoutResponse(OrmBase):
    id: int
    date: date
    parse_confidence: float
    parse_method: Optional[str] = None
    parse_flagged: bool = True
    raw_text: Optional[str] = None


class ReviewResponse(BaseModel):
    workout_day_id: int
    parse_flagged: bool = False
    message: str = "Marked as reviewed"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None


class LoginUrlResponse(BaseModel):
    authorization_url: str
