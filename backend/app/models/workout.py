from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Float, Text,
    ForeignKey, Enum as SAEnum, ARRAY,
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.core.database import Base


class ParseMethod(str, enum.Enum):
    ollama = "ollama"
    claude = "claude"
    regex = "regex"


class TrackType(str, enum.Enum):
    fitness_performance = "fitness_performance"
    endurance = "endurance"


class BlockType(str, enum.Enum):
    strength = "strength"
    accessory = "accessory"
    conditioning = "conditioning"
    conditioning_amrap = "conditioning_amrap"
    conditioning_emom = "conditioning_emom"
    conditioning_fortime = "conditioning_fortime"
    conditioning_interval = "conditioning_interval"
    pump = "pump"
    other = "other"


class MovementType(str, enum.Enum):
    barbell = "barbell"
    dumbbell = "dumbbell"
    kettlebell = "kettlebell"
    bodyweight = "bodyweight"
    machine = "machine"
    cardio = "cardio"
    other = "other"


class ConditioningFormat(str, enum.Enum):
    amrap = "amrap"
    for_time = "for_time"
    emom = "emom"
    interval = "interval"
    tabata = "tabata"


class Modality(str, enum.Enum):
    bike_erg = "bike_erg"
    run = "run"
    row = "row"
    ski = "ski"
    other = "other"


class WorkoutDay(Base):
    __tablename__ = "workout_days"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    source_url = Column(String, nullable=True)
    raw_html = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    parse_confidence = Column(Float, default=0.0)
    parse_flagged = Column(Boolean, default=False)
    parse_method = Column(SAEnum(ParseMethod), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tracks = relationship("WorkoutTrack", back_populates="workout_day", cascade="all, delete-orphan")
    logs = relationship("WorkoutLog", back_populates="workout_day")


class WorkoutTrack(Base):
    __tablename__ = "workout_tracks"

    id = Column(Integer, primary_key=True, index=True)
    workout_day_id = Column(Integer, ForeignKey("workout_days.id", ondelete="CASCADE"), nullable=False)
    track_type = Column(SAEnum(TrackType), nullable=False)
    display_order = Column(Integer, default=0)

    workout_day = relationship("WorkoutDay", back_populates="tracks")
    blocks = relationship("WorkoutBlock", back_populates="track", cascade="all, delete-orphan")


class WorkoutBlock(Base):
    __tablename__ = "workout_blocks"

    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(Integer, ForeignKey("workout_tracks.id", ondelete="CASCADE"), nullable=False)
    label = Column(String, nullable=True)
    block_type = Column(SAEnum(BlockType), default=BlockType.other)
    raw_text = Column(Text, nullable=True)
    display_order = Column(Integer, default=0)

    track = relationship("WorkoutTrack", back_populates="blocks")
    exercises = relationship("Exercise", back_populates="block", cascade="all, delete-orphan")
    conditioning_workouts = relationship("ConditioningWorkout", back_populates="block", cascade="all, delete-orphan")


class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    movement_type = Column(SAEnum(MovementType), default=MovementType.other)
    is_named_benchmark = Column(Boolean, default=False)
    aliases = Column(ARRAY(Text), default=list)
    muscle_groups = Column(ARRAY(Text), default=list)

    exercises = relationship("Exercise", back_populates="movement")
    personal_records = relationship("PersonalRecord", back_populates="movement")


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    block_id = Column(Integer, ForeignKey("workout_blocks.id", ondelete="CASCADE"), nullable=False)
    movement_id = Column(Integer, ForeignKey("movements.id"), nullable=True)
    display_order = Column(Integer, default=0)
    sets = Column(Integer, nullable=True)
    reps_min = Column(Integer, nullable=True)
    reps_max = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    tempo = Column(String(10), nullable=True)
    rpe_min = Column(Float, nullable=True)
    rpe_max = Column(Float, nullable=True)
    percent_1rm_min = Column(Float, nullable=True)
    percent_1rm_max = Column(Float, nullable=True)
    rest_seconds = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    is_alternative = Column(Boolean, default=False)
    alternative_group_id = Column(Integer, nullable=True)

    block = relationship("WorkoutBlock", back_populates="exercises")
    movement = relationship("Movement", back_populates="exercises")
    results = relationship("ExerciseResult", back_populates="exercise")


class ConditioningWorkout(Base):
    __tablename__ = "conditioning_workouts"

    id = Column(Integer, primary_key=True, index=True)
    block_id = Column(Integer, ForeignKey("workout_blocks.id", ondelete="CASCADE"), nullable=False)
    format = Column(SAEnum(ConditioningFormat), nullable=False)
    duration_minutes = Column(Float, nullable=True)
    rounds = Column(Integer, nullable=True)
    time_cap_minutes = Column(Float, nullable=True)
    is_partner = Column(Boolean, default=False)
    is_named_benchmark = Column(Boolean, default=False)
    benchmark_name = Column(String, nullable=True)

    block = relationship("WorkoutBlock", back_populates="conditioning_workouts")
    intervals = relationship("ConditioningInterval", back_populates="conditioning_workout", cascade="all, delete-orphan")
    results = relationship("ConditioningResult", back_populates="conditioning_workout")


class ConditioningInterval(Base):
    __tablename__ = "conditioning_intervals"

    id = Column(Integer, primary_key=True, index=True)
    conditioning_workout_id = Column(Integer, ForeignKey("conditioning_workouts.id", ondelete="CASCADE"), nullable=False)
    interval_order = Column(Integer, default=0)
    modality = Column(SAEnum(Modality), default=Modality.other)
    distance_meters = Column(Integer, nullable=True)
    calories = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    effort_percent = Column(Integer, nullable=True)

    conditioning_workout = relationship("ConditioningWorkout", back_populates="intervals")
