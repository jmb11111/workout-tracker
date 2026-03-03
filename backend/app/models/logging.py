from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, Text,
    ForeignKey, Enum as SAEnum, JSON,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.core.database import Base
from app.models.workout import TrackType


class ResultType(str, enum.Enum):
    rounds_reps = "rounds_reps"
    time = "time"
    load = "load"
    distance = "distance"
    notes_only = "notes_only"


class RecordType(str, enum.Enum):
    one_rm = "1rm"
    three_rm = "3rm"
    five_rm = "5rm"
    max_reps = "max_reps"
    max_weight_reps = "max_weight_reps"
    best_time = "best_time"


class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workout_day_id = Column(Integer, ForeignKey("workout_days.id", ondelete="CASCADE"), nullable=False)
    track_type = Column(SAEnum(TrackType), nullable=False)
    logged_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    overall_notes = Column(Text, nullable=True)
    completed = Column(Boolean, default=False)
    selected_option = Column(String, nullable=True)

    user = relationship("User", back_populates="workout_logs")
    workout_day = relationship("WorkoutDay", back_populates="logs")
    exercise_results = relationship("ExerciseResult", back_populates="log", cascade="all, delete-orphan")
    conditioning_results = relationship("ConditioningResult", back_populates="log", cascade="all, delete-orphan")


class ExerciseResult(Base):
    __tablename__ = "exercise_results"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(Integer, ForeignKey("workout_logs.id", ondelete="CASCADE"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=True)
    movement_id = Column(Integer, ForeignKey("movements.id"), nullable=True)
    sets_completed = Column(Integer, nullable=True)
    reps_per_set = Column(JSON, nullable=True)
    weight_per_set_lbs = Column(JSON, nullable=True)
    weight_per_set_kg = Column(JSON, nullable=True)
    tempo_used = Column(String(10), nullable=True)
    rpe_actual = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    is_pr = Column(Boolean, default=False)

    log = relationship("WorkoutLog", back_populates="exercise_results")
    exercise = relationship("Exercise", back_populates="results")
    movement = relationship("Movement")


class ConditioningResult(Base):
    __tablename__ = "conditioning_results"

    id = Column(Integer, primary_key=True, index=True)
    log_id = Column(Integer, ForeignKey("workout_logs.id", ondelete="CASCADE"), nullable=False)
    conditioning_workout_id = Column(Integer, ForeignKey("conditioning_workouts.id"), nullable=True)
    result_type = Column(SAEnum(ResultType), nullable=True)
    rounds_completed = Column(Integer, nullable=True)
    reps_completed = Column(Integer, nullable=True)
    time_seconds = Column(Integer, nullable=True)
    total_reps = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    is_named_benchmark = Column(Boolean, default=False)

    log = relationship("WorkoutLog", back_populates="conditioning_results")
    conditioning_workout = relationship("ConditioningWorkout", back_populates="results")


class PersonalRecord(Base):
    __tablename__ = "personal_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movement_id = Column(Integer, ForeignKey("movements.id", ondelete="CASCADE"), nullable=False)
    record_type = Column(SAEnum(RecordType), nullable=False)
    value = Column(Float, nullable=False)
    reps = Column(Integer, nullable=True)
    set_count = Column(Integer, nullable=True)
    tempo = Column(String(10), nullable=True)
    notes = Column(Text, nullable=True)
    achieved_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    exercise_result_id = Column(Integer, ForeignKey("exercise_results.id"), nullable=True)

    user = relationship("User", back_populates="personal_records")
    movement = relationship("Movement", back_populates="personal_records")
    exercise_result = relationship("ExerciseResult")
