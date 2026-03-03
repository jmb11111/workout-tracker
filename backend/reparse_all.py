"""Re-parse all existing workouts with the updated prompt."""
import sys
sys.path.insert(0, "/app")

from app.core.database import SessionLocal
from app.models.workout import (
    WorkoutDay, WorkoutTrack, WorkoutBlock, Exercise,
    ConditioningWorkout, ConditioningInterval, Movement,
)
from app.scraper.parsers import parse_workout
from app.scraper.postprocess import postprocess

db = SessionLocal()

days = db.query(WorkoutDay).order_by(WorkoutDay.date).all()
print(f"Found {len(days)} workout days to re-parse")

def safe_int(val):
    """Convert to int or return None."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


success = 0
failed = 0

for day in days:
    if not day.raw_text:
        print(f"  {day.date}: no raw_text, skipping")
        continue

    print(f"\n{'='*60}")
    print(f"Re-parsing {day.date}...")

    # Delete old tracks (cascades to blocks, exercises, conditioning)
    for track in day.tracks:
        db.delete(track)
    db.flush()

    # Re-parse
    try:
        parsed, confidence, method = parse_workout(day.raw_text)
    except Exception as e:
        print(f"  FAILED to parse: {e}")
        db.rollback()
        failed += 1
        continue

    day.parse_confidence = confidence
    day.parse_method = method
    day.parse_flagged = confidence < 0.8

    try:
        # Rebuild tracks/blocks/exercises
        for t_data in parsed.get("tracks", []):
            track = WorkoutTrack(
                workout_day=day,
                track_type=t_data["track_type"],
                display_order=t_data.get("display_order", 0),
            )
            db.add(track)
            db.flush()

            for b_data in t_data.get("blocks", []):
                block = WorkoutBlock(
                    track=track,
                    label=b_data.get("label"),
                    block_type=b_data.get("block_type", "other"),
                    raw_text=b_data.get("raw_text"),
                    display_order=b_data.get("display_order", 0),
                )
                db.add(block)
                db.flush()

                # Add exercises
                for e_data in b_data.get("exercises", []):
                    movement_name = e_data.get("movement_name", "").strip()
                    if not movement_name:
                        continue

                    # Find or create movement
                    movement = db.query(Movement).filter(
                        Movement.name == movement_name
                    ).first()
                    if not movement:
                        movement = Movement(
                            name=movement_name,
                            movement_type=e_data.get("movement_type", "other"),
                        )
                        db.add(movement)
                        db.flush()

                    exercise = Exercise(
                        block=block,
                        movement=movement,
                        display_order=e_data.get("display_order", 0),
                        sets=safe_int(e_data.get("sets")),
                        reps_min=safe_int(e_data.get("reps_min")),
                        reps_max=safe_int(e_data.get("reps_max")),
                        duration_seconds=safe_int(e_data.get("duration_seconds")),
                        tempo=e_data.get("tempo"),
                        rpe_min=e_data.get("rpe_min"),
                        rpe_max=e_data.get("rpe_max"),
                        percent_1rm_min=e_data.get("percent_1rm_min"),
                        percent_1rm_max=e_data.get("percent_1rm_max"),
                        rest_seconds=safe_int(e_data.get("rest_seconds")),
                        notes=e_data.get("notes"),
                        is_alternative=e_data.get("is_alternative", False),
                        alternative_group_id=safe_int(e_data.get("alternative_group_id")),
                    )
                    db.add(exercise)

                # Add conditioning
                cond_data = b_data.get("conditioning")
                if cond_data and isinstance(cond_data, dict) and cond_data.get("format"):
                    cw = ConditioningWorkout(
                        block=block,
                        format=cond_data["format"],
                        duration_minutes=cond_data.get("duration_minutes"),
                        rounds=safe_int(cond_data.get("rounds")),
                        time_cap_minutes=cond_data.get("time_cap_minutes"),
                        is_partner=cond_data.get("is_partner", False),
                        is_named_benchmark=cond_data.get("is_named_benchmark", False),
                        benchmark_name=cond_data.get("benchmark_name"),
                    )
                    db.add(cw)
                    db.flush()

                    for i_data in cond_data.get("intervals", []):
                        if isinstance(i_data, dict):
                            interval = ConditioningInterval(
                                conditioning_workout=cw,
                                interval_order=safe_int(i_data.get("interval_order")) or 0,
                                modality=i_data.get("modality", "other"),
                                distance_meters=safe_int(i_data.get("distance_meters")),
                                calories=safe_int(i_data.get("calories")),
                                duration_seconds=safe_int(i_data.get("duration_seconds")),
                                effort_percent=safe_int(i_data.get("effort_percent")),
                            )
                            db.add(interval)

        db.flush()

        # Print summary
        for track in day.tracks:
            print(f"  Track: {track.track_type}")
            blocks = db.query(WorkoutBlock).filter(WorkoutBlock.track_id == track.id).order_by(WorkoutBlock.display_order).all()
            for b in blocks:
                ex_count = db.query(Exercise).filter(Exercise.block_id == b.id).count()
                cw_count = db.query(ConditioningWorkout).filter(ConditioningWorkout.block_id == b.id).count()
                print(f"    {b.label}: {b.block_type} ({ex_count} exercises, {cw_count} conditioning)")

        print(f"  Confidence: {day.parse_confidence}, Method: {day.parse_method}")
        db.commit()
        success += 1

    except Exception as e:
        print(f"  FAILED to save: {e}")
        db.rollback()
        failed += 1

print(f"\nDone! {success} succeeded, {failed} failed out of {len(days)} workout days.")
db.close()
