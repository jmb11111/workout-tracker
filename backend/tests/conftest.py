import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import *  # noqa: F401,F403


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # SQLite doesn't support ARRAY type — skip column-level checks for those
    Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_workout_text():
    return """
FITNESS & PERFORMANCE

A. Back Squat
5 x 3 @RPE 7-8
Tempo: 20X1
Rest 2:00 between sets
*Consider the weights you used last week*

B. Accessory Work
B1. Romanian Deadlift
3 x 8-10 @65-70% 1RM
Tempo: 30X1

B2. Walking Lunges
3 x 12 each leg

C. Conditioning
Option 1: Partner Conditioning
AMRAP 12:
10 Cal Bike Erg
15 Wall Balls (20/14)
20 Double Unders

OR

Option 2: PUMP / Strength Endurance
4 Rounds For Time:
12 Dumbbell Bench Press
15 Bent Over Rows
20 Banded Pull Aparts
Time Cap: 15:00

---

ENDURANCE (SWEAT SESH)

3 Rounds:
500m Row @80%
Rest 2:00
1000m Bike Erg @85%
Rest 1:30
200m Run @90%
Rest 3:00
"""


@pytest.fixture
def sample_parsed_data():
    return {
        "tracks": [
            {
                "track_type": "fitness_performance",
                "display_order": 0,
                "blocks": [
                    {
                        "label": "A",
                        "block_type": "strength",
                        "raw_text": "Back Squat\n5 x 3 @RPE 7-8\nTempo: 20X1\nRest 2:00",
                        "display_order": 0,
                        "exercises": [
                            {
                                "movement_name": "Back Squat",
                                "movement_type": "barbell",
                                "sets": 5,
                                "reps_min": 3,
                                "reps_max": 3,
                                "tempo": "20X1",
                                "rpe_min": 7.0,
                                "rpe_max": 8.0,
                                "percent_1rm_min": None,
                                "percent_1rm_max": None,
                                "rest_seconds": 120,
                                "notes": "Consider the weights you used last week",
                                "is_alternative": False,
                                "alternative_group_id": None,
                                "duration_seconds": None,
                            }
                        ],
                        "conditioning": None,
                    },
                    {
                        "label": "B",
                        "block_type": "accessory",
                        "raw_text": "Romanian Deadlift\n3 x 8-10 @65-70% 1RM\nWalking Lunges\n3 x 12 each leg",
                        "display_order": 1,
                        "exercises": [
                            {
                                "movement_name": "Romanian Deadlift",
                                "movement_type": "barbell",
                                "sets": 3,
                                "reps_min": 8,
                                "reps_max": 10,
                                "tempo": "30X1",
                                "rpe_min": None,
                                "rpe_max": None,
                                "percent_1rm_min": 65.0,
                                "percent_1rm_max": 70.0,
                                "rest_seconds": None,
                                "notes": None,
                                "is_alternative": False,
                                "alternative_group_id": None,
                                "duration_seconds": None,
                            },
                            {
                                "movement_name": "Walking Lunges",
                                "movement_type": "bodyweight",
                                "sets": 3,
                                "reps_min": 12,
                                "reps_max": 12,
                                "tempo": None,
                                "rpe_min": None,
                                "rpe_max": None,
                                "percent_1rm_min": None,
                                "percent_1rm_max": None,
                                "rest_seconds": None,
                                "notes": "each leg",
                                "is_alternative": False,
                                "alternative_group_id": None,
                                "duration_seconds": None,
                            },
                        ],
                        "conditioning": None,
                    },
                    {
                        "label": "C - Option 1",
                        "block_type": "conditioning_amrap",
                        "raw_text": "AMRAP 12: 10 Cal Bike Erg, 15 Wall Balls, 20 Double Unders",
                        "display_order": 2,
                        "exercises": [
                            {
                                "movement_name": "Bike Erg",
                                "movement_type": "cardio",
                                "sets": None,
                                "reps_min": 10,
                                "reps_max": 10,
                                "tempo": None,
                                "rpe_min": None,
                                "rpe_max": None,
                                "percent_1rm_min": None,
                                "percent_1rm_max": None,
                                "rest_seconds": None,
                                "notes": "calories",
                                "is_alternative": True,
                                "alternative_group_id": 1,
                                "duration_seconds": None,
                            },
                        ],
                        "conditioning": {
                            "format": "amrap",
                            "duration_minutes": 12,
                            "rounds": None,
                            "time_cap_minutes": None,
                            "is_partner": True,
                            "is_named_benchmark": False,
                            "benchmark_name": None,
                            "intervals": [],
                        },
                    },
                ],
            },
            {
                "track_type": "endurance",
                "display_order": 1,
                "blocks": [
                    {
                        "label": "Endurance",
                        "block_type": "conditioning_interval",
                        "raw_text": "3 Rounds: 500m Row @80%, Rest 2:00, 1000m Bike Erg @85%, Rest 1:30, 200m Run @90%, Rest 3:00",
                        "display_order": 0,
                        "exercises": [],
                        "conditioning": {
                            "format": "interval",
                            "duration_minutes": None,
                            "rounds": 3,
                            "time_cap_minutes": None,
                            "is_partner": False,
                            "is_named_benchmark": False,
                            "benchmark_name": None,
                            "intervals": [
                                {
                                    "interval_order": 0,
                                    "modality": "row",
                                    "distance_meters": 500,
                                    "calories": None,
                                    "duration_seconds": None,
                                    "effort_percent": 80,
                                },
                                {
                                    "interval_order": 1,
                                    "modality": "bike_erg",
                                    "distance_meters": 1000,
                                    "calories": None,
                                    "duration_seconds": None,
                                    "effort_percent": 85,
                                },
                                {
                                    "interval_order": 2,
                                    "modality": "run",
                                    "distance_meters": 200,
                                    "calories": None,
                                    "duration_seconds": None,
                                    "effort_percent": 90,
                                },
                            ],
                        },
                    }
                ],
            },
        ]
    }
