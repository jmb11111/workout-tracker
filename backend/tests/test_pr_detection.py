"""Tests for personal record auto-detection logic."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.user import User, WeightUnit
from app.models.workout import (
    WorkoutDay, WorkoutTrack, WorkoutBlock, Exercise, Movement,
    TrackType, BlockType, MovementType,
)
from app.models.logging import (
    WorkoutLog, ExerciseResult, PersonalRecord, RecordType,
)


@pytest.fixture
def pr_db():
    from sqlalchemy import text
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create tables individually — skip ones using ARRAY (unsupported in SQLite)
    for table in Base.metadata.sorted_tables:
        try:
            table.create(bind=engine, checkfirst=True)
        except Exception:
            # movements table has ARRAY columns — create simplified version for SQLite
            if table.name == "movements":
                with engine.connect() as conn:
                    conn.execute(text(
                        "CREATE TABLE IF NOT EXISTS movements ("
                        "id INTEGER PRIMARY KEY, name VARCHAR UNIQUE NOT NULL, "
                        "movement_type VARCHAR, is_named_benchmark BOOLEAN DEFAULT 0)"
                    ))
                    conn.commit()
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create test user
    user = User(
        id=1,
        authentik_sub="test-user-123",
        display_name="Test User",
        email="test@example.com",
        weight_unit=WeightUnit.lbs,
    )
    session.add(user)

    # Create movement using raw SQL (ORM would try to insert ARRAY columns)
    session.execute(text(
        "INSERT INTO movements (id, name, movement_type, is_named_benchmark) "
        "VALUES (1, 'Back Squat', 'barbell', 0)"
    ))

    # Create workout day structure
    workout_day = WorkoutDay(
        id=1,
        date=datetime(2025, 1, 15).date(),
    )
    session.add(workout_day)
    session.flush()

    track = WorkoutTrack(
        id=1,
        workout_day_id=1,
        track_type=TrackType.fitness_performance,
    )
    session.add(track)
    session.flush()

    block = WorkoutBlock(
        id=1,
        track_id=1,
        label="A",
        block_type=BlockType.strength,
    )
    session.add(block)
    session.flush()

    exercise = Exercise(
        id=1,
        block_id=1,
        movement_id=1,
        sets=5,
        reps_min=3,
        reps_max=3,
    )
    session.add(exercise)

    log = WorkoutLog(
        id=1,
        user_id=1,
        workout_day_id=1,
        track_type=TrackType.fitness_performance,
    )
    session.add(log)
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def detect_pr(session, user_id, movement_id, weight, reps):
    """Simplified PR detection matching the API logic."""
    if reps <= 1:
        record_type = RecordType.one_rm
    elif reps <= 3:
        record_type = RecordType.three_rm
    elif reps <= 5:
        record_type = RecordType.five_rm
    else:
        record_type = RecordType.max_weight_reps

    existing = (
        session.query(PersonalRecord)
        .filter(
            PersonalRecord.user_id == user_id,
            PersonalRecord.movement_id == movement_id,
            PersonalRecord.record_type == record_type,
        )
        .first()
    )

    is_pr = False
    if existing is None:
        pr = PersonalRecord(
            user_id=user_id,
            movement_id=movement_id,
            record_type=record_type,
            value=weight,
            reps=reps,
        )
        session.add(pr)
        is_pr = True
    elif weight > existing.value:
        existing.value = weight
        existing.reps = reps
        existing.achieved_at = datetime.now(timezone.utc)
        is_pr = True

    if is_pr:
        session.commit()
    return is_pr


class TestPRDetection:
    def test_first_result_is_pr(self, pr_db):
        result = detect_pr(pr_db, user_id=1, movement_id=1, weight=225, reps=3)
        assert result is True

    def test_higher_weight_is_pr(self, pr_db):
        detect_pr(pr_db, user_id=1, movement_id=1, weight=225, reps=3)
        result = detect_pr(pr_db, user_id=1, movement_id=1, weight=235, reps=3)
        assert result is True

    def test_same_weight_is_not_pr(self, pr_db):
        detect_pr(pr_db, user_id=1, movement_id=1, weight=225, reps=3)
        result = detect_pr(pr_db, user_id=1, movement_id=1, weight=225, reps=3)
        assert result is False

    def test_lower_weight_is_not_pr(self, pr_db):
        detect_pr(pr_db, user_id=1, movement_id=1, weight=225, reps=3)
        result = detect_pr(pr_db, user_id=1, movement_id=1, weight=215, reps=3)
        assert result is False

    def test_different_rep_ranges_separate_prs(self, pr_db):
        detect_pr(pr_db, user_id=1, movement_id=1, weight=315, reps=1)
        detect_pr(pr_db, user_id=1, movement_id=1, weight=275, reps=3)
        detect_pr(pr_db, user_id=1, movement_id=1, weight=245, reps=5)

        prs = pr_db.query(PersonalRecord).filter(
            PersonalRecord.user_id == 1,
            PersonalRecord.movement_id == 1,
        ).all()
        assert len(prs) == 3

        types = {pr.record_type for pr in prs}
        assert RecordType.one_rm in types
        assert RecordType.three_rm in types
        assert RecordType.five_rm in types

    def test_pr_value_updates_correctly(self, pr_db):
        detect_pr(pr_db, user_id=1, movement_id=1, weight=225, reps=3)
        detect_pr(pr_db, user_id=1, movement_id=1, weight=245, reps=3)

        pr = pr_db.query(PersonalRecord).filter(
            PersonalRecord.user_id == 1,
            PersonalRecord.movement_id == 1,
            PersonalRecord.record_type == RecordType.three_rm,
        ).first()
        assert pr.value == 245

    def test_high_reps_use_max_weight_reps_type(self, pr_db):
        detect_pr(pr_db, user_id=1, movement_id=1, weight=185, reps=10)

        pr = pr_db.query(PersonalRecord).filter(
            PersonalRecord.user_id == 1,
            PersonalRecord.movement_id == 1,
            PersonalRecord.record_type == RecordType.max_weight_reps,
        ).first()
        assert pr is not None
        assert pr.value == 185
