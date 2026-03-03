"""
Three-tier parsing pipeline for workout text.

Tier 1: Ollama (local LLM - primary)
Tier 2: Claude API (fallback)
Tier 3: Regex (last resort)
"""

import json
import logging
import re
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.scraper.llm_prompt import build_prompt
from app.scraper.postprocess import postprocess

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

_REQUIRED_TOP_KEYS = {"tracks"}
_REQUIRED_TRACK_KEYS = {"track_type", "blocks"}
_REQUIRED_BLOCK_KEYS = {"label", "block_type", "exercises"}
_REQUIRED_EXERCISE_KEYS = {"movement_name"}

_VALID_TRACK_TYPES = {"fitness_performance", "endurance"}
_VALID_BLOCK_TYPES = {
    "strength", "accessory", "conditioning", "conditioning_amrap", "conditioning_emom",
    "conditioning_fortime", "conditioning_interval", "pump", "other",
}
_VALID_MOVEMENT_TYPES = {
    "barbell", "dumbbell", "kettlebell", "bodyweight", "machine", "cardio", "other",
}
_VALID_CONDITIONING_FORMATS = {"amrap", "for_time", "emom", "interval", "tabata"}
_VALID_MODALITIES = {"bike_erg", "run", "row", "ski", "other"}


def validate_parsed_data(data: Any) -> tuple[bool, list[str]]:
    """
    Validate that parsed data conforms to the expected schema shape.

    Returns:
        (is_valid, list_of_issues)
    """
    issues: list[str] = []

    if not isinstance(data, dict):
        return False, ["Root element must be a dict"]

    if "tracks" not in data:
        return False, ["Missing 'tracks' key at root"]

    if not isinstance(data["tracks"], list):
        return False, ["'tracks' must be a list"]

    if len(data["tracks"]) == 0:
        issues.append("No tracks found")
        return False, issues

    for t_idx, track in enumerate(data["tracks"]):
        if not isinstance(track, dict):
            issues.append(f"Track {t_idx} is not a dict")
            continue

        if "track_type" not in track:
            issues.append(f"Track {t_idx} missing 'track_type'")
        elif track["track_type"] not in _VALID_TRACK_TYPES:
            issues.append(f"Track {t_idx} invalid track_type: {track['track_type']}")

        if "blocks" not in track:
            issues.append(f"Track {t_idx} missing 'blocks'")
            continue

        if not isinstance(track["blocks"], list):
            issues.append(f"Track {t_idx} 'blocks' is not a list")
            continue

        for b_idx, block in enumerate(track["blocks"]):
            if not isinstance(block, dict):
                issues.append(f"Track {t_idx}, Block {b_idx} is not a dict")
                continue

            if "block_type" in block and block["block_type"] not in _VALID_BLOCK_TYPES:
                issues.append(
                    f"Track {t_idx}, Block {b_idx} invalid block_type: {block['block_type']}"
                )

            exercises = block.get("exercises", [])
            if not isinstance(exercises, list):
                issues.append(f"Track {t_idx}, Block {b_idx} 'exercises' is not a list")
                continue

            for e_idx, exercise in enumerate(exercises):
                if not isinstance(exercise, dict):
                    issues.append(
                        f"Track {t_idx}, Block {b_idx}, Exercise {e_idx} is not a dict"
                    )
                    continue

                if "movement_name" not in exercise or not exercise["movement_name"]:
                    issues.append(
                        f"Track {t_idx}, Block {b_idx}, Exercise {e_idx} missing 'movement_name'"
                    )

                if "movement_type" in exercise and exercise["movement_type"]:
                    if exercise["movement_type"] not in _VALID_MOVEMENT_TYPES:
                        issues.append(
                            f"Track {t_idx}, Block {b_idx}, Exercise {e_idx} "
                            f"invalid movement_type: {exercise['movement_type']}"
                        )

            # Validate conditioning object if present
            cond = block.get("conditioning")
            if cond is not None and cond is not False:
                if not isinstance(cond, dict):
                    issues.append(
                        f"Track {t_idx}, Block {b_idx} 'conditioning' is not a dict"
                    )
                else:
                    fmt = cond.get("format")
                    if fmt and fmt not in _VALID_CONDITIONING_FORMATS:
                        issues.append(
                            f"Track {t_idx}, Block {b_idx} invalid conditioning format: {fmt}"
                        )

                    intervals = cond.get("intervals", [])
                    if isinstance(intervals, list):
                        for i_idx, interval in enumerate(intervals):
                            if isinstance(interval, dict):
                                mod = interval.get("modality")
                                if mod and mod not in _VALID_MODALITIES:
                                    issues.append(
                                        f"Track {t_idx}, Block {b_idx}, "
                                        f"Interval {i_idx} invalid modality: {mod}"
                                    )

    is_valid = len(issues) == 0
    return is_valid, issues


def _compute_confidence(data: dict, base: float) -> float:
    """
    Compute a confidence score based on how complete the parsed data is.

    Starts at base, reduces by 0.05 per missing field category.
    """
    confidence = base
    deductions = 0

    for track in data.get("tracks", []):
        if "display_order" not in track:
            deductions += 1
            break

    has_exercises = False
    has_sets_reps = False
    has_tempo = False
    has_rpe = False
    has_rest = False
    has_notes = False
    has_block_labels = False
    has_raw_text = False
    has_conditioning = False

    for track in data.get("tracks", []):
        for block in track.get("blocks", []):
            if block.get("label"):
                has_block_labels = True
            if block.get("raw_text"):
                has_raw_text = True

            for ex in block.get("exercises", []):
                has_exercises = True
                if ex.get("sets") is not None or ex.get("reps_min") is not None:
                    has_sets_reps = True
                if ex.get("tempo"):
                    has_tempo = True
                if ex.get("rpe_min") is not None:
                    has_rpe = True
                if ex.get("rest_seconds") is not None:
                    has_rest = True
                if ex.get("notes"):
                    has_notes = True

            cond = block.get("conditioning")
            if cond and isinstance(cond, dict) and cond.get("format"):
                has_conditioning = True

    categories = [
        has_exercises, has_sets_reps, has_block_labels, has_raw_text,
    ]
    # Optional categories - only deduct if they seem relevant
    optional_categories = [has_tempo, has_rpe, has_rest, has_notes]

    for cat in categories:
        if not cat:
            deductions += 1

    # Only deduct for optional categories if fewer than half are present
    optional_present = sum(1 for c in optional_categories if c)
    if optional_present < 2:
        deductions += 1

    confidence -= deductions * 0.05
    return max(0.0, min(1.0, round(confidence, 2)))


def _extract_json_from_response(text: str) -> Optional[dict]:
    """
    Extract a JSON object from an LLM response, handling common issues
    like markdown fences, leading text, etc.
    """
    # Strip whitespace
    text = text.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        # Find the end of the opening fence line
        first_newline = text.index("\n") if "\n" in text else 3
        text = text[first_newline + 1:]
        # Find the closing fence (may not be at EOF if model added explanation)
        closing_fence = text.rfind("```")
        if closing_fence >= 0:
            text = text[:closing_fence]
        text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object boundaries
    first_brace = text.find("{")
    if first_brace == -1:
        return None

    # Find matching closing brace
    depth = 0
    last_brace = -1
    in_string = False
    escape_next = False

    for i in range(first_brace, len(text)):
        char = text[i]
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                last_brace = i
                break

    if last_brace == -1:
        return None

    json_str = text[first_brace:last_brace + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Try fixing common issues: trailing commas
        cleaned = re.sub(r",\s*([}\]])", r"\1", json_str)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


# ---------------------------------------------------------------------------
# Tier 1: Ollama
# ---------------------------------------------------------------------------

def _parse_with_ollama(raw_text: str) -> Optional[tuple[dict, float, str]]:
    """
    Parse workout text using a local Ollama model.

    Returns:
        (parsed_data, confidence, "ollama") or None if failed.
    """
    prompt = build_prompt(raw_text)
    ollama_url = f"{settings.OLLAMA_URL}/api/generate"

    logger.info("Attempting Ollama parse with model %s", settings.OLLAMA_MODEL)

    try:
        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                ollama_url,
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 8192,
                    },
                },
            )
            response.raise_for_status()

        result = response.json()
        response_text = result.get("response", "")

        if not response_text:
            logger.warning("Ollama returned empty response")
            return None

        parsed = _extract_json_from_response(response_text)
        if parsed is None:
            logger.warning("Could not extract valid JSON from Ollama response")
            logger.debug("Ollama raw response (first 500 chars): %s", response_text[:500])
            return None

        is_valid, issues = validate_parsed_data(parsed)
        if not is_valid:
            logger.warning("Ollama response failed validation: %s", "; ".join(issues))
            return None

        confidence = _compute_confidence(parsed, base=1.0)
        # Clamp to 0.85-1.0 range for Ollama
        confidence = max(0.85, confidence)

        logger.info("Ollama parse succeeded with confidence %.2f", confidence)
        return parsed, confidence, "ollama"

    except httpx.ConnectError:
        logger.warning("Could not connect to Ollama at %s", settings.OLLAMA_URL)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("Ollama HTTP error: %s", exc.response.status_code)
        return None
    except httpx.TimeoutException:
        logger.warning("Ollama request timed out")
        return None
    except Exception:
        logger.exception("Unexpected error during Ollama parse")
        return None


# ---------------------------------------------------------------------------
# Tier 2: Claude API
# ---------------------------------------------------------------------------

def _parse_with_claude(raw_text: str) -> Optional[tuple[dict, float, str]]:
    """
    Parse workout text using the Claude API (Haiku model).

    Returns:
        (parsed_data, confidence, "claude") or None if failed.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.info("No ANTHROPIC_API_KEY configured, skipping Claude tier")
        return None

    prompt = build_prompt(raw_text)

    logger.info("Attempting Claude parse with claude-sonnet-4-20250514")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        response_text = ""
        for content_block in message.content:
            if content_block.type == "text":
                response_text += content_block.text

        if not response_text:
            logger.warning("Claude returned empty response")
            return None

        parsed = _extract_json_from_response(response_text)
        if parsed is None:
            logger.warning("Could not extract valid JSON from Claude response")
            logger.debug("Claude raw response (first 500 chars): %s", response_text[:500])
            return None

        is_valid, issues = validate_parsed_data(parsed)
        if not is_valid:
            logger.warning("Claude response failed validation: %s", "; ".join(issues))
            return None

        confidence = _compute_confidence(parsed, base=1.0)
        # Clamp to 0.80-1.0 range for Claude
        confidence = max(0.80, confidence)

        logger.info("Claude parse succeeded with confidence %.2f", confidence)
        return parsed, confidence, "claude"

    except ImportError:
        logger.error("anthropic package not installed")
        return None
    except Exception:
        logger.exception("Unexpected error during Claude parse")
        return None


# ---------------------------------------------------------------------------
# Tier 3: Regex
# ---------------------------------------------------------------------------

_BLOCK_LABEL_RE = re.compile(
    r"^(?:"
    r"([A-F])\."            # Single letter label: A. B. C. etc.
    r"|([A-F])\)"           # Letter with paren: A) B)
    r"|([A-F])\s*[-:—]"    # Letter with dash/colon: A: A - A —
    r"|Option\s+(\d+)"     # Option N
    r"|Part\s+([A-F\d]+)"  # Part A, Part 1
    r")",
    re.IGNORECASE | re.MULTILINE,
)

_SETS_REPS_RE = re.compile(
    r"(\d+)\s*[xX×]\s*(\d+)(?:\s*[-–]\s*(\d+))?"  # 3x5 or 3x5-8
    r"|(\d+)\s+sets?\s+(?:of\s+)?(\d+)(?:\s*[-–]\s*(\d+))?"  # 3 sets of 5 or 3 sets 5-8
)

_TEMPO_RE = re.compile(r"\b([0-9X]{4})\b", re.IGNORECASE)

_RPE_RE = re.compile(
    r"(?:@?\s*RPE\s*(\d+(?:\.\d+)?)(?:\s*[-–]\s*(\d+(?:\.\d+)?))?)"
    r"|(?:(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*/\s*10)",
    re.IGNORECASE,
)

_REST_RE = re.compile(
    r"[Rr]est\s+(?:(\d+):(\d+)|(\d+)\s*(?:sec|seconds?|s\b)|(\d+)\s*(?:min|minutes?|m\b))",
)

_PERCENT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*%"
    r"|(?:at\s+)?(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

_CONDITIONING_TYPE_RE = re.compile(
    r"\b(AMRAP|EMOM|For Time|Tabata)\b",
    re.IGNORECASE,
)

_DURATION_RE = re.compile(
    r"(\d+)\s*(?:min(?:ute)?s?|')\b",
    re.IGNORECASE,
)

_DISTANCE_RE = re.compile(
    r"(\d+)\s*(?:m(?:eter)?s?)\b",
    re.IGNORECASE,
)

_CALORIE_RE = re.compile(
    r"(\d+)(?:/\d+)?\s*[Cc]al(?:orie)?s?",
)

_MOVEMENT_LINE_RE = re.compile(
    r"^(?:\d+\s*[xX×]\s*\d+|[\d]+\s+)?\s*(.+?)(?:\s*[-–]\s*|\s*@\s*|\s*$)",
    re.MULTILINE,
)

_NAMED_WORKOUT_RE = re.compile(
    r'"([^"]+)"'
    r'|["""]([^"""]+)["""]'
    r"|(?:Baseline|Benchmark)\s*:?\s*(.+?)$",
    re.IGNORECASE | re.MULTILINE,
)


def _classify_movement_type(name: str) -> str:
    """Guess movement_type from movement name."""
    name_lower = name.lower()

    barbell_keywords = [
        "squat", "deadlift", "bench press", "overhead press", "clean",
        "snatch", "jerk", "thruster", "barbell", "back squat", "front squat",
        "power clean", "hang clean", "push press", "strict press",
    ]
    dumbbell_keywords = ["dumbbell", "db "]
    kettlebell_keywords = ["kettlebell", "kb ", "turkish get"]
    bodyweight_keywords = [
        "pull-up", "pullup", "push-up", "pushup", "muscle-up", "muscleup",
        "handstand", "dip", "ring", "burpee", "sit-up", "situp", "plank",
        "pistol", "lunge", "air squat", "toes to bar", "t2b", "knees to",
        "hollow", "l-sit",
    ]
    machine_keywords = ["machine", "cable", "leg press", "hack squat", "lat pulldown"]
    cardio_keywords = [
        "row", "run", "bike", "ski", "assault", "echo", "cal ", "calorie",
        "sprint", "jog",
    ]

    for kw in barbell_keywords:
        if kw in name_lower:
            return "barbell"
    for kw in dumbbell_keywords:
        if kw in name_lower:
            return "dumbbell"
    for kw in kettlebell_keywords:
        if kw in name_lower:
            return "kettlebell"
    for kw in bodyweight_keywords:
        if kw in name_lower:
            return "bodyweight"
    for kw in machine_keywords:
        if kw in name_lower:
            return "machine"
    for kw in cardio_keywords:
        if kw in name_lower:
            return "cardio"

    return "other"


def _classify_modality(text: str) -> str:
    """Guess conditioning modality from text."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["bike", "assault", "echo", "airdyne"]):
        return "bike_erg"
    if any(w in text_lower for w in ["row", "rower", "erg"]):
        return "row"
    if any(w in text_lower for w in ["ski"]):
        return "ski"
    if any(w in text_lower for w in ["run", "sprint", "jog"]):
        return "run"
    return "other"


def _parse_with_regex(raw_text: str) -> Optional[tuple[dict, float, str]]:
    """
    Parse workout text using regex patterns as a last resort.

    Returns:
        (parsed_data, confidence, "regex") or None if catastrophic failure.
    """
    logger.info("Attempting regex-based parse")

    confidence = 0.5
    lines = raw_text.split("\n")

    # Split text into blocks by label
    blocks_raw: list[dict] = []
    current_block: Optional[dict] = None

    for line in lines:
        label_match = _BLOCK_LABEL_RE.match(line.strip())
        if label_match:
            if current_block:
                blocks_raw.append(current_block)
            # Extract the label from whichever group matched
            label = next(
                (g for g in label_match.groups() if g is not None), "?"
            )
            current_block = {"label": label, "lines": [line.strip()], "raw_text": line.strip()}
        elif current_block:
            current_block["lines"].append(line.strip())
            current_block["raw_text"] += "\n" + line.strip()
        else:
            # Lines before first label - start a default block
            if line.strip():
                current_block = {"label": "A", "lines": [line.strip()], "raw_text": line.strip()}

    if current_block:
        blocks_raw.append(current_block)

    if blocks_raw:
        confidence += 0.1  # Found block labels

    # Determine if we have multiple tracks
    text_lower = raw_text.lower()
    has_endurance = any(
        kw in text_lower for kw in ["endurance", "endurance track", "mono-structural"]
    )

    # Process each block
    parsed_blocks: list[dict] = []

    for block_data in blocks_raw:
        block_text = "\n".join(block_data["lines"])
        exercises: list[dict] = []
        conditioning = None

        # Detect conditioning type
        cond_match = _CONDITIONING_TYPE_RE.search(block_text)
        cond_format = None
        if cond_match:
            cond_type = cond_match.group(1).lower()
            format_map = {
                "amrap": "amrap",
                "emom": "emom",
                "for time": "for_time",
                "tabata": "tabata",
            }
            cond_format = format_map.get(cond_type, cond_type)

        # Determine block_type
        block_type = "other"
        if cond_format:
            block_type_map = {
                "amrap": "conditioning_amrap",
                "emom": "conditioning_emom",
                "for_time": "conditioning_fortime",
                "interval": "conditioning_interval",
                "tabata": "conditioning_interval",
            }
            block_type = block_type_map.get(cond_format, "other")
        elif any(kw in block_text.lower() for kw in ["squat", "deadlift", "press", "clean", "snatch"]):
            # Likely strength if it has major compound lifts
            block_type = "strength"
        elif any(kw in block_text.lower() for kw in ["pump", "accessory"]):
            block_type = "accessory"

        # Parse exercises from lines
        exercise_order = 0
        for line in block_data["lines"]:
            stripped = line.strip()
            if not stripped or len(stripped) < 3:
                continue

            # Skip header/label lines
            if _BLOCK_LABEL_RE.match(stripped) and len(stripped) < 20:
                continue
            if _CONDITIONING_TYPE_RE.match(stripped):
                continue

            # Try to extract sets x reps
            sr_match = _SETS_REPS_RE.search(stripped)
            sets_val = None
            reps_min_val = None
            reps_max_val = None

            if sr_match:
                groups = sr_match.groups()
                if groups[0] is not None:  # NxM pattern
                    sets_val = int(groups[0])
                    reps_min_val = int(groups[1])
                    reps_max_val = int(groups[2]) if groups[2] else None
                elif groups[3] is not None:  # N sets of M pattern
                    sets_val = int(groups[3])
                    reps_min_val = int(groups[4])
                    reps_max_val = int(groups[5]) if groups[5] else None

            # Extract tempo
            tempo_val = None
            tempo_match = _TEMPO_RE.search(stripped)
            if tempo_match:
                candidate = tempo_match.group(1).upper()
                # Validate: should have at least one digit and look like tempo
                if any(c.isdigit() for c in candidate) and len(candidate) == 4:
                    tempo_val = candidate

            # Extract RPE
            rpe_min_val = None
            rpe_max_val = None
            rpe_match = _RPE_RE.search(stripped)
            if rpe_match:
                groups = rpe_match.groups()
                if groups[0] is not None:
                    rpe_min_val = float(groups[0])
                    rpe_max_val = float(groups[1]) if groups[1] else None
                elif groups[2] is not None:
                    rpe_min_val = float(groups[2])
                    rpe_max_val = float(groups[3]) if groups[3] else None

            # Extract rest
            rest_val = None
            rest_match = _REST_RE.search(stripped)
            if rest_match:
                groups = rest_match.groups()
                if groups[0] is not None:  # M:SS format
                    rest_val = int(groups[0]) * 60 + int(groups[1])
                elif groups[2] is not None:  # N sec
                    rest_val = int(groups[2])
                elif groups[3] is not None:  # N min
                    rest_val = int(groups[3]) * 60

            # Extract percentage
            pct_min_val = None
            pct_max_val = None
            pct_match = _PERCENT_RE.search(stripped)
            if pct_match:
                groups = pct_match.groups()
                if groups[0] is not None:  # range N-M%
                    pct_min_val = float(groups[0]) / 100
                    pct_max_val = float(groups[1]) / 100
                elif groups[2] is not None:  # single N%
                    pct_min_val = float(groups[2]) / 100

            # Determine movement name: remove sets/reps/tempo/rpe patterns
            movement_name = stripped
            # Remove sets x reps
            if sr_match:
                movement_name = movement_name[:sr_match.start()] + movement_name[sr_match.end():]
            # Remove tempo
            if tempo_match:
                movement_name = movement_name[:tempo_match.start()] + movement_name[tempo_match.end():]
            # Remove RPE
            if rpe_match:
                movement_name = movement_name[:rpe_match.start()] + movement_name[rpe_match.end():]
            # Remove rest
            if rest_match:
                movement_name = movement_name[:rest_match.start()] + movement_name[rest_match.end():]
            # Remove percentage
            if pct_match:
                movement_name = movement_name[:pct_match.start()] + movement_name[pct_match.end():]
            # Remove label prefix
            movement_name = _BLOCK_LABEL_RE.sub("", movement_name)
            # Clean up
            movement_name = re.sub(r"^\s*[-–—:;.)\]]+\s*", "", movement_name)
            movement_name = re.sub(r"\s*[-–—:;]+\s*$", "", movement_name)
            movement_name = re.sub(r"\s+", " ", movement_name).strip()

            # Skip lines that are just numbers or very short after cleaning
            if not movement_name or len(movement_name) < 2:
                continue
            # Skip lines that are purely rest instructions
            if re.match(r"^rest\b", movement_name, re.IGNORECASE):
                continue

            # Only create an exercise if we found something meaningful
            if sets_val is not None or reps_min_val is not None or movement_name:
                exercise = {
                    "movement_name": movement_name,
                    "movement_type": _classify_movement_type(movement_name),
                    "sets": sets_val,
                    "reps_min": reps_min_val,
                    "reps_max": reps_max_val,
                    "tempo": tempo_val,
                    "rpe_min": rpe_min_val,
                    "rpe_max": rpe_max_val,
                    "percent_1rm_min": pct_min_val,
                    "percent_1rm_max": pct_max_val,
                    "rest_seconds": rest_val,
                    "notes": None,
                    "is_alternative": False,
                    "alternative_group_id": None,
                    "duration_seconds": None,
                    "display_order": exercise_order,
                }
                exercises.append(exercise)
                exercise_order += 1

        # Build conditioning object if applicable
        if cond_format:
            duration_match = _DURATION_RE.search(block_text)
            duration_minutes = float(duration_match.group(1)) if duration_match else None

            # Check for named benchmark
            benchmark_match = _NAMED_WORKOUT_RE.search(block_text)
            is_benchmark = benchmark_match is not None
            benchmark_name = None
            if benchmark_match:
                benchmark_name = next(
                    (g for g in benchmark_match.groups() if g is not None), None
                )

            # Extract intervals for cardio
            intervals: list[dict] = []
            dist_matches = _DISTANCE_RE.finditer(block_text)
            cal_matches = _CALORIE_RE.finditer(block_text)

            for i, dm in enumerate(dist_matches):
                context_start = max(0, dm.start() - 50)
                context = block_text[context_start:dm.end() + 20]
                intervals.append({
                    "interval_order": i,
                    "modality": _classify_modality(context),
                    "distance_meters": int(dm.group(1)),
                    "calories": None,
                    "duration_seconds": None,
                    "effort_percent": None,
                })

            for i, cm in enumerate(cal_matches):
                context_start = max(0, cm.start() - 50)
                context = block_text[context_start:cm.end() + 20]
                intervals.append({
                    "interval_order": len(intervals),
                    "modality": _classify_modality(context),
                    "distance_meters": None,
                    "calories": int(cm.group(1)),
                    "duration_seconds": None,
                    "effort_percent": None,
                })

            conditioning = {
                "format": cond_format,
                "duration_minutes": duration_minutes,
                "rounds": None,
                "time_cap_minutes": None,
                "is_partner": any(
                    kw in block_text.lower()
                    for kw in ["partner", "teams of", "with a partner"]
                ),
                "is_named_benchmark": is_benchmark,
                "benchmark_name": benchmark_name,
                "intervals": intervals,
            }

        parsed_block = {
            "label": block_data["label"],
            "block_type": block_type,
            "raw_text": block_data["raw_text"],
            "display_order": len(parsed_blocks),
            "exercises": exercises,
            "conditioning": conditioning,
        }
        parsed_blocks.append(parsed_block)

    # Count found categories for confidence
    any_sets_reps = any(
        ex.get("sets") is not None or ex.get("reps_min") is not None
        for b in parsed_blocks for ex in b.get("exercises", [])
    )
    any_tempo = any(
        ex.get("tempo") is not None
        for b in parsed_blocks for ex in b.get("exercises", [])
    )
    any_rpe = any(
        ex.get("rpe_min") is not None
        for b in parsed_blocks for ex in b.get("exercises", [])
    )
    any_rest = any(
        ex.get("rest_seconds") is not None
        for b in parsed_blocks for ex in b.get("exercises", [])
    )
    any_percent = any(
        ex.get("percent_1rm_min") is not None
        for b in parsed_blocks for ex in b.get("exercises", [])
    )
    any_conditioning = any(b.get("conditioning") is not None for b in parsed_blocks)

    for found in [any_sets_reps, any_tempo, any_rpe, any_rest, any_percent, any_conditioning]:
        if found:
            confidence += 0.1

    confidence = min(confidence, 0.79)  # Regex never exceeds 0.79

    # Build track structure
    tracks = []
    if has_endurance:
        # Try to split blocks into fitness and endurance
        fitness_blocks = []
        endurance_blocks = []
        endurance_started = False

        for b in parsed_blocks:
            block_raw = b.get("raw_text", "").lower()
            if "endurance" in block_raw or endurance_started:
                endurance_started = True
                endurance_blocks.append(b)
            else:
                fitness_blocks.append(b)

        if fitness_blocks:
            tracks.append({
                "track_type": "fitness_performance",
                "display_order": 0,
                "blocks": fitness_blocks,
            })
        if endurance_blocks:
            tracks.append({
                "track_type": "endurance",
                "display_order": 1,
                "blocks": endurance_blocks,
            })
    else:
        tracks.append({
            "track_type": "fitness_performance",
            "display_order": 0,
            "blocks": parsed_blocks,
        })

    if not tracks or all(len(t.get("blocks", [])) == 0 for t in tracks):
        logger.warning("Regex parser produced no usable blocks")
        return None

    data = {"tracks": tracks}
    logger.info("Regex parse completed with confidence %.2f", confidence)
    return data, confidence, "regex"


# ---------------------------------------------------------------------------
# Main parse function
# ---------------------------------------------------------------------------

def parse_workout(raw_text: str) -> tuple[dict, float, str]:
    """
    Parse workout text through the three-tier pipeline, then apply
    deterministic post-processing to fix common LLM mistakes.

    Args:
        raw_text: Clean plain text of the workout post.

    Returns:
        (parsed_data, confidence, method)

    Raises:
        ValueError: if all three tiers fail to produce any result.
    """
    # Tier 1: Claude API (fast, accurate)
    result = _parse_with_claude(raw_text)
    if result is not None:
        parsed, confidence, method = result
        parsed = postprocess(parsed, raw_text)
        return parsed, confidence, method

    logger.info("Claude parse failed or unavailable, falling back to Ollama")

    # Tier 2: Ollama (free local fallback)
    result = _parse_with_ollama(raw_text)
    if result is not None:
        parsed, confidence, method = result
        parsed = postprocess(parsed, raw_text)
        return parsed, confidence, method

    logger.info("Ollama parse failed or unavailable, falling back to regex")

    # Tier 3: Regex
    result = _parse_with_regex(raw_text)
    if result is not None:
        parsed, confidence, method = result
        parsed = postprocess(parsed, raw_text)
        return parsed, confidence, method

    raise ValueError("All three parsing tiers failed to produce a valid result")
