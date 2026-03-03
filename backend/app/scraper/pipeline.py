"""
Main scraper orchestrator.

Fetches workout HTML, parses via the three-tier pipeline, and
persists the structured data to the database.
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.cache import cache_delete
from app.models.workout import (
    WorkoutDay,
    WorkoutTrack,
    WorkoutBlock,
    Exercise,
    Movement,
    ConditioningWorkout,
    ConditioningInterval,
    TrackType,
    BlockType,
    ParseMethod,
    ConditioningFormat,
    MovementType,
    Modality,
)
from app.scraper.fetcher import fetch_workout, FetchError
from app.scraper.parsers import parse_workout, validate_parsed_data

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Movement normalization
# ---------------------------------------------------------------------------

def _normalize_movement_name(name: str) -> str:
    """
    Normalize a movement name for consistent lookups.

    Lowercases, strips extra whitespace, and standardizes common
    abbreviations.
    """
    name = name.strip().lower()
    # Standardize common abbreviations
    replacements = {
        "db ": "dumbbell ",
        "kb ": "kettlebell ",
        "bb ": "barbell ",
        "ohp": "overhead press",
        "rdl": "romanian deadlift",
        "sldl": "stiff leg deadlift",
        "hspu": "handstand push-up",
        "t2b": "toes to bar",
        "c2b": "chest to bar",
        "ghr": "glute ham raise",
        "ghd": "ghd sit-up",
    }
    for abbrev, full in replacements.items():
        if name.startswith(abbrev) or f" {abbrev}" in name:
            name = name.replace(abbrev, full)

    # Title-case the result for consistent storage
    name = name.title()
    return name


def _get_or_create_movement(
    db: Session,
    name: str,
    movement_type_str: Optional[str] = None,
) -> Movement:
    """
    Get an existing Movement by normalized name, or create a new one.
    """
    normalized = _normalize_movement_name(name)

    movement = db.query(Movement).filter(Movement.name == normalized).first()

    if movement is None:
        # Check aliases
        movement = (
            db.query(Movement)
            .filter(Movement.aliases.any(normalized.lower()))
            .first()
        )

    if movement is None:
        # Resolve movement type
        mv_type = MovementType.other
        if movement_type_str:
            try:
                mv_type = MovementType(movement_type_str)
            except ValueError:
                mv_type = MovementType.other

        movement = Movement(
            name=normalized,
            movement_type=mv_type,
        )
        db.add(movement)
        db.flush()  # Get the ID
        logger.debug("Created new Movement: %s (id=%d)", normalized, movement.id)

    return movement


# ---------------------------------------------------------------------------
# Enum resolution helpers
# ---------------------------------------------------------------------------

def _resolve_track_type(value: str) -> TrackType:
    try:
        return TrackType(value)
    except ValueError:
        logger.warning("Unknown track_type '%s', defaulting to fitness_performance", value)
        return TrackType.fitness_performance


def _resolve_block_type(value: str) -> BlockType:
    try:
        return BlockType(value)
    except ValueError:
        logger.warning("Unknown block_type '%s', defaulting to other", value)
        return BlockType.other


def _resolve_conditioning_format(value: str) -> ConditioningFormat:
    try:
        return ConditioningFormat(value)
    except ValueError:
        logger.warning("Unknown conditioning format '%s', defaulting to amrap", value)
        return ConditioningFormat.amrap


def _resolve_modality(value: str) -> Modality:
    try:
        return Modality(value)
    except ValueError:
        return Modality.other


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------

def _clear_workout_day_children(db: Session, workout_day: WorkoutDay) -> None:
    """
    Remove all child records (tracks, blocks, exercises, conditioning)
    for a WorkoutDay so we can re-create them from fresh parsed data.
    """
    for track in workout_day.tracks:
        for block in track.blocks:
            # Conditioning workouts and intervals cascade
            for cw in block.conditioning_workouts:
                db.delete(cw)
            # Exercises cascade
            for ex in block.exercises:
                db.delete(ex)
            db.delete(block)
        db.delete(track)
    db.flush()


def _save_parsed_data(
    db: Session,
    workout_day: WorkoutDay,
    parsed_data: dict,
    confidence: float,
    method: str,
) -> None:
    """
    Persist the parsed workout data to the database.

    Creates or updates WorkoutTracks, WorkoutBlocks, Exercises,
    Movements, ConditioningWorkouts, and ConditioningIntervals.
    """
    # Update WorkoutDay metadata
    try:
        workout_day.parse_method = ParseMethod(method)
    except ValueError:
        workout_day.parse_method = ParseMethod.regex

    workout_day.parse_confidence = confidence
    workout_day.parse_flagged = confidence < 0.75
    workout_day.updated_at = datetime.now(timezone.utc)

    # Clear existing child records for re-parse
    _clear_workout_day_children(db, workout_day)

    # Create tracks
    for track_data in parsed_data.get("tracks", []):
        track = WorkoutTrack(
            workout_day_id=workout_day.id,
            track_type=_resolve_track_type(track_data.get("track_type", "fitness_performance")),
            display_order=track_data.get("display_order", 0),
        )
        db.add(track)
        db.flush()

        # Create blocks
        for block_data in track_data.get("blocks", []):
            block = WorkoutBlock(
                track_id=track.id,
                label=block_data.get("label"),
                block_type=_resolve_block_type(block_data.get("block_type", "other")),
                raw_text=block_data.get("raw_text"),
                display_order=block_data.get("display_order", 0),
            )
            db.add(block)
            db.flush()

            # Create exercises
            for ex_idx, ex_data in enumerate(block_data.get("exercises", [])):
                movement_name = ex_data.get("movement_name", "Unknown")
                movement_type_str = ex_data.get("movement_type")

                movement = _get_or_create_movement(db, movement_name, movement_type_str)

                exercise = Exercise(
                    block_id=block.id,
                    movement_id=movement.id,
                    display_order=ex_data.get("display_order", ex_idx),
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

            # Create conditioning workout if present
            cond_data = block_data.get("conditioning")
            if cond_data and isinstance(cond_data, dict) and cond_data.get("format"):
                cond_workout = ConditioningWorkout(
                    block_id=block.id,
                    format=_resolve_conditioning_format(cond_data["format"]),
                    duration_minutes=cond_data.get("duration_minutes"),
                    rounds=cond_data.get("rounds"),
                    time_cap_minutes=cond_data.get("time_cap_minutes"),
                    is_partner=cond_data.get("is_partner", False),
                    is_named_benchmark=cond_data.get("is_named_benchmark", False),
                    benchmark_name=cond_data.get("benchmark_name"),
                )
                db.add(cond_workout)
                db.flush()

                # Create intervals
                for interval_data in cond_data.get("intervals", []):
                    if not isinstance(interval_data, dict):
                        continue
                    interval = ConditioningInterval(
                        conditioning_workout_id=cond_workout.id,
                        interval_order=interval_data.get("interval_order", 0),
                        modality=_resolve_modality(interval_data.get("modality", "other")),
                        distance_meters=interval_data.get("distance_meters"),
                        calories=interval_data.get("calories"),
                        duration_seconds=interval_data.get("duration_seconds"),
                        effort_percent=interval_data.get("effort_percent"),
                    )
                    db.add(interval)

    db.flush()


# ---------------------------------------------------------------------------
# Alert webhook
# ---------------------------------------------------------------------------

def _send_alert(workout_date: date, confidence: float, method: str) -> None:
    """
    Send a low-confidence parse alert to the configured webhook.
    """
    if not settings.ALERT_WEBHOOK_URL:
        return

    payload = {
        "date": workout_date.isoformat(),
        "confidence": confidence,
        "method": method,
        "message": (
            f"Workout parse for {workout_date.isoformat()} flagged "
            f"with confidence {confidence:.2f} (method: {method})"
        ),
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(settings.ALERT_WEBHOOK_URL, json=payload)
            resp.raise_for_status()
            logger.info("Alert webhook sent successfully for %s", workout_date.isoformat())
    except Exception:
        logger.exception("Failed to send alert webhook for %s", workout_date.isoformat())


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(target_date: Optional[date] = None) -> dict:
    """
    Run the full scraper pipeline for a given date.

    Steps:
    1. Fetch HTML/text from the blog
    2. Parse via three-tier pipeline
    3. Save to database
    4. Send alert if flagged

    Args:
        target_date: The date to scrape. Defaults to today.

    Returns:
        dict with pipeline result summary.
    """
    if target_date is None:
        target_date = date.today()

    logger.info("Starting scraper pipeline for %s", target_date.isoformat())
    result = {
        "date": target_date.isoformat(),
        "success": False,
        "method": None,
        "confidence": 0.0,
        "flagged": False,
        "error": None,
    }

    # Step 1: Fetch
    try:
        fetched = fetch_workout(target_date)
    except FetchError as exc:
        logger.error("Fetch failed for %s: %s", target_date.isoformat(), exc)
        result["error"] = f"Fetch failed: {exc}"
        return result

    raw_html = fetched["raw_html"]
    raw_text = fetched["raw_text"]
    source_url = fetched["source_url"]

    # Step 2: Parse
    try:
        parsed_data, confidence, method = parse_workout(raw_text)
    except ValueError as exc:
        logger.error("All parsers failed for %s: %s", target_date.isoformat(), exc)
        # Still save the raw data even if parsing failed
        db = SessionLocal()
        try:
            workout_day = db.query(WorkoutDay).filter(
                WorkoutDay.date == target_date
            ).first()
            if workout_day is None:
                workout_day = WorkoutDay(
                    date=target_date,
                    source_url=source_url,
                    raw_html=raw_html,
                    raw_text=raw_text,
                    parse_confidence=0.0,
                    parse_flagged=True,
                )
                db.add(workout_day)
            else:
                workout_day.source_url = source_url
                workout_day.raw_html = raw_html
                workout_day.raw_text = raw_text
                workout_day.parse_confidence = 0.0
                workout_day.parse_flagged = True
                workout_day.updated_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to save raw data for %s", target_date.isoformat())
        finally:
            db.close()

        result["error"] = f"Parse failed: {exc}"
        result["flagged"] = True
        _send_alert(target_date, 0.0, "none")
        return result

    result["method"] = method
    result["confidence"] = confidence

    # Step 3: Save to database
    db = SessionLocal()
    try:
        workout_day = db.query(WorkoutDay).filter(
            WorkoutDay.date == target_date
        ).first()

        if workout_day is None:
            workout_day = WorkoutDay(
                date=target_date,
                source_url=source_url,
                raw_html=raw_html,
                raw_text=raw_text,
            )
            db.add(workout_day)
            db.flush()
            logger.info("Created new WorkoutDay for %s (id=%d)", target_date.isoformat(), workout_day.id)
        else:
            workout_day.source_url = source_url
            workout_day.raw_html = raw_html
            workout_day.raw_text = raw_text
            logger.info("Updating existing WorkoutDay for %s (id=%d)", target_date.isoformat(), workout_day.id)

        _save_parsed_data(db, workout_day, parsed_data, confidence, method)
        db.commit()

        # Invalidate cache for this date
        cache_delete(f"workout:{target_date.isoformat()}")
        cache_delete(f"workout_day:{workout_day.id}")

        result["success"] = True
        result["flagged"] = workout_day.parse_flagged
        result["workout_day_id"] = workout_day.id

        logger.info(
            "Pipeline completed for %s: method=%s confidence=%.2f flagged=%s",
            target_date.isoformat(),
            method,
            confidence,
            workout_day.parse_flagged,
        )

    except Exception:
        db.rollback()
        logger.exception("Database error saving parsed data for %s", target_date.isoformat())
        result["error"] = "Database error during save"
        return result
    finally:
        db.close()

    # Step 4: Alert if flagged
    if result["flagged"]:
        _send_alert(target_date, confidence, method)

    return result


def reparse(workout_day_id: int) -> dict:
    """
    Re-run the parsing pipeline on a stored WorkoutDay's raw_text
    without re-fetching from the blog.

    Args:
        workout_day_id: The ID of the WorkoutDay to reparse.

    Returns:
        dict with reparse result summary.
    """
    logger.info("Starting reparse for WorkoutDay id=%d", workout_day_id)
    result = {
        "workout_day_id": workout_day_id,
        "success": False,
        "method": None,
        "confidence": 0.0,
        "flagged": False,
        "error": None,
    }

    db = SessionLocal()
    try:
        workout_day = db.query(WorkoutDay).filter(
            WorkoutDay.id == workout_day_id
        ).first()

        if workout_day is None:
            result["error"] = f"WorkoutDay {workout_day_id} not found"
            logger.error(result["error"])
            return result

        if not workout_day.raw_text:
            result["error"] = f"WorkoutDay {workout_day_id} has no raw_text to parse"
            logger.error(result["error"])
            return result

        # Run the parsing pipeline
        try:
            parsed_data, confidence, method = parse_workout(workout_day.raw_text)
        except ValueError as exc:
            result["error"] = f"All parsers failed: {exc}"
            workout_day.parse_flagged = True
            workout_day.parse_confidence = 0.0
            workout_day.updated_at = datetime.now(timezone.utc)
            db.commit()
            _send_alert(workout_day.date, 0.0, "none")
            return result

        result["method"] = method
        result["confidence"] = confidence

        # Save the new parsed data
        _save_parsed_data(db, workout_day, parsed_data, confidence, method)
        db.commit()

        # Invalidate cache
        cache_delete(f"workout:{workout_day.date.isoformat()}")
        cache_delete(f"workout_day:{workout_day.id}")

        result["success"] = True
        result["flagged"] = workout_day.parse_flagged
        result["date"] = workout_day.date.isoformat()

        logger.info(
            "Reparse completed for WorkoutDay id=%d: method=%s confidence=%.2f flagged=%s",
            workout_day_id,
            method,
            confidence,
            workout_day.parse_flagged,
        )

    except Exception:
        db.rollback()
        logger.exception("Database error during reparse for WorkoutDay id=%d", workout_day_id)
        result["error"] = "Database error during reparse"
        return result
    finally:
        db.close()

    # Alert if flagged
    if result["flagged"]:
        _send_alert(
            workout_day.date,
            confidence,
            method,
        )

    return result
