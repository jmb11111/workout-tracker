"""
Deterministic post-processing for LLM-parsed workout data.

The v3 prompt reliably produces valid JSON with correct track_type assignments,
but sometimes misses structural details that small models struggle with:
- BURN section separation into its own track
- Named benchmark detection (Team "Barbara")
- Partner workout detection ("In teams of two")
- Accessory vs strength misclassification
- "Every X minutes" blocks mistyped as strength/other

This module applies rule-based fixes AFTER LLM parsing for reliable corrections.
"""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# --- Benchmark names ---
_KNOWN_BENCHMARKS = {
    "fran", "grace", "diane", "elizabeth", "helen", "barbara",
    "murph", "annie", "jackie", "karen", "isabel", "nancy",
    "linda", "cindy", "mary", "chelsea", "amanda", "angie",
    "kelly", "eva", "lynne", "nicole", "filthy fifty",
}

_BENCHMARK_RE = re.compile(
    r'["\u201c\u201d]([^"\u201c\u201d]+)["\u201c\u201d]'
    r"|Team\s+[\"'\u201c]?(\w+)[\"'\u201d]?",
    re.IGNORECASE,
)

# --- Partner detection ---
_PARTNER_RE = re.compile(
    r"(?:in\s+teams\s+of\s+two|partners?\s+alternate|with\s+a\s+partner|partner\s+workout)",
    re.IGNORECASE,
)

# --- EMOM detection ---
_EMOM_RE = re.compile(
    r"every\s+\d+\s*(?:minutes?|mins?)\b",
    re.IGNORECASE,
)

# --- BURN section detection in raw_text ---
_BURN_HEADER_RE = re.compile(
    r'(?:^|\n)\s*["\u201c]?BURN["\u201d]?\s*(?:\n|$)',
    re.IGNORECASE,
)

# --- Block set count from header text ---
_SET_COUNT_RE = re.compile(
    r"(?:two|three|four|five|six)\s+(?:quality\s+)?(?:working\s+)?sets?\s+(?:of|for)",
    re.IGNORECASE,
)
_SET_WORD_TO_NUM = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
}

# --- Strength indicators ---
_STRENGTH_MOVEMENTS = {
    "back squat", "front squat", "overhead squat", "deadlift",
    "sumo deadlift", "bench press", "overhead press", "strict press",
    "push press", "push jerk", "split jerk", "power clean",
    "hang clean", "squat clean", "power snatch", "hang snatch",
    "squat snatch", "clean and jerk", "snatch",
}

# --- Accessory indicators ---
_ACCESSORY_KEYWORDS = [
    "carry", "plank", "band", "curl", "raise", "fly",
    "pull apart", "face pull", "glute bridge", "cossack",
    "turkish get up", "farmer", "suitcase", "step-up",
]


def postprocess(data: dict, raw_text: str) -> dict:
    """
    Apply deterministic post-processing fixes to LLM-parsed workout data.

    Args:
        data: The parsed JSON from the LLM.
        raw_text: The original workout text (for pattern matching).

    Returns:
        The corrected data dict (modified in-place).
    """
    if not data or "tracks" not in data:
        return data

    _fix_burn_track_separation(data, raw_text)
    _fix_benchmark_detection(data, raw_text)
    _fix_partner_detection(data, raw_text)
    _fix_block_types(data)
    _fix_movement_types(data)
    _fix_set_inheritance(data)
    _fix_alternative_group_ids(data)
    _fix_display_orders(data)

    return data


def _fix_burn_track_separation(data: dict, raw_text: str) -> None:
    """
    If the raw text has a BURN section, ensure it's a separate track.

    The LLM often merges BURN blocks into the fitness_performance track.
    We detect BURN content via raw_text patterns and split it out.
    """
    raw_upper = raw_text.upper()

    # Check if there's a BURN section in the original text
    burn_pos = -1
    for pattern in ['"BURN"', '\u201cBURN\u201d', 'BURN\n', '"BURN"']:
        idx = raw_upper.find(pattern)
        if idx >= 0:
            burn_pos = idx
            break

    if burn_pos < 0:
        return  # No BURN section in workout

    # Find the fitness_performance track(s)
    fp_tracks = [t for t in data["tracks"] if t.get("track_type") == "fitness_performance"]
    if not fp_tracks:
        return

    # Check if BURN is already its own track (multiple fp tracks exist)
    if len(fp_tracks) > 1:
        return  # Already separated

    fp_track = fp_tracks[0]
    blocks = fp_track.get("blocks", [])
    if not blocks:
        return

    # Find blocks that belong to BURN by checking their raw_text
    burn_blocks = []
    fitness_blocks = []
    for block in blocks:
        block_raw = (block.get("raw_text", "") or "").upper()
        label = (block.get("label", "") or "").upper()

        is_burn = (
            "BURN" in block_raw[:50]
            or "BURN" in label
            or "30/30" in block_raw[:20]
        )

        if is_burn:
            burn_blocks.append(block)
        else:
            fitness_blocks.append(block)

    if not burn_blocks:
        # BURN section exists in raw text but no blocks matched.
        # Try matching by position: blocks after the last lettered block
        # might be BURN content that wasn't labeled.
        return

    # Split into two tracks
    fp_track["blocks"] = fitness_blocks
    burn_order = fp_track.get("display_order", 0) + 1

    # Adjust display_order for endurance track if it exists
    for track in data["tracks"]:
        if track.get("track_type") == "endurance":
            track["display_order"] = max(track.get("display_order", 0), burn_order + 1)

    burn_track = {
        "track_type": "fitness_performance",
        "display_order": burn_order,
        "blocks": burn_blocks,
    }

    # Insert BURN track after the fitness track
    fp_idx = data["tracks"].index(fp_track)
    data["tracks"].insert(fp_idx + 1, burn_track)

    logger.info("Post-process: separated BURN into its own track (%d blocks)", len(burn_blocks))


def _fix_benchmark_detection(data: dict, raw_text: str) -> None:
    """
    Detect named benchmarks from the raw text and set flags on conditioning blocks.
    """
    matches = _BENCHMARK_RE.findall(raw_text)
    if not matches:
        return

    for quoted, team_name in matches:
        name = quoted or team_name
        if not name:
            continue
        name_clean = name.strip()
        name_lower = name_clean.lower()

        # Must be a known benchmark or short enough to be a name
        if name_lower not in _KNOWN_BENCHMARKS and len(name_clean) > 20:
            continue

        # Find conditioning blocks and set the benchmark flag
        for track in data.get("tracks", []):
            for block in track.get("blocks", []):
                block_raw = (block.get("raw_text", "") or "").lower()
                if name_lower in block_raw:
                    cond = block.get("conditioning")
                    if cond and isinstance(cond, dict):
                        if not cond.get("is_named_benchmark"):
                            cond["is_named_benchmark"] = True
                            cond["benchmark_name"] = name_clean
                            logger.info(
                                "Post-process: detected benchmark '%s'", name_clean
                            )
                    elif block.get("block_type", "").startswith("conditioning"):
                        # Block is conditioning but missing the object
                        block["conditioning"] = block.get("conditioning") or {}
                        block["conditioning"]["is_named_benchmark"] = True
                        block["conditioning"]["benchmark_name"] = name_clean


def _fix_partner_detection(data: dict, raw_text: str) -> None:
    """
    Detect partner workout patterns and set is_partner on conditioning blocks.
    """
    if not _PARTNER_RE.search(raw_text):
        return

    for track in data.get("tracks", []):
        for block in track.get("blocks", []):
            block_raw = block.get("raw_text", "") or ""
            if _PARTNER_RE.search(block_raw):
                cond = block.get("conditioning")
                if cond and isinstance(cond, dict):
                    if not cond.get("is_partner"):
                        cond["is_partner"] = True
                        logger.info("Post-process: detected partner workout in block '%s'",
                                    block.get("label", "?"))


def _fix_block_types(data: dict) -> None:
    """
    Fix common block_type misclassifications.

    Key insight: "Every X minutes" is used for BOTH strength rest timers
    and conditioning circuits. A block with ONE compound lift on a timer
    is strength. A block with MULTIPLE movements on a timer is conditioning.
    """
    for track in data.get("tracks", []):
        for block in track.get("blocks", []):
            block_raw = (block.get("raw_text", "") or "").lower()
            block_type = block.get("block_type", "")
            exercises = block.get("exercises", [])

            # Count distinct movements (excluding alternatives of the same group)
            movement_count = len(exercises)

            # For timed blocks, distinguish strength-on-timer from conditioning
            has_timer = bool(_EMOM_RE.search(block_raw))

            if has_timer and block_type in ("strength", "other"):
                # ONE movement on a timer with RPE/tempo = strength (keep it)
                # MULTIPLE movements on a timer = conditioning
                has_rpe = any(e.get("rpe_min") or e.get("rpe_max") for e in exercises)
                has_tempo = any(e.get("tempo") for e in exercises)

                if movement_count >= 3 and not has_rpe and not has_tempo:
                    block["block_type"] = "conditioning_emom"
                    logger.info(
                        "Post-process: reclassified block '%s' to 'conditioning_emom' "
                        "(%d movements, no RPE/tempo)",
                        block.get("label", "?"), movement_count,
                    )
                # Otherwise trust the LLM's strength classification

            # Fix AMRAP detection
            if block_type not in ("conditioning_amrap",):
                if "amrap" in block_raw or "as many rounds" in block_raw:
                    block["block_type"] = "conditioning_amrap"

            # Fix "against a X-minute clock" -> for_time
            if block_type not in ("conditioning_fortime",):
                if "against a" in block_raw and "clock" in block_raw:
                    block["block_type"] = "conditioning_fortime"

            # Fix strength -> accessory when exercises are all accessory-type
            if block_type == "strength" and exercises:
                movement_names = [
                    (e.get("movement_name", "") or "").lower() for e in exercises
                ]
                all_accessory = all(
                    any(kw in name for kw in _ACCESSORY_KEYWORDS)
                    for name in movement_names
                    if name
                )
                has_strength = any(
                    name in _STRENGTH_MOVEMENTS
                    or any(name.startswith(s) for s in _STRENGTH_MOVEMENTS)
                    for name in movement_names
                    if name
                )
                if all_accessory and not has_strength:
                    block["block_type"] = "accessory"
                    logger.info(
                        "Post-process: reclassified block '%s' from 'strength' to 'accessory'",
                        block.get("label", "?"),
                    )


def _fix_movement_types(data: dict) -> None:
    """
    Fix invalid movement_type values.

    The LLM often uses conditioning modality names (row, ski, bike_erg, bike,
    ski_erg) as movement_type instead of "cardio". Also fixes "banded" -> "other".
    """
    _MODALITY_TO_CARDIO = {
        "row", "ski", "bike", "bike_erg", "ski_erg", "run",
        "echo bike", "assault bike", "air runner", "rower",
    }
    _REMAP_TO_OTHER = {"banded", "band", "plate", "band work"}

    from app.scraper.parsers import _VALID_MOVEMENT_TYPES

    for track in data.get("tracks", []):
        for block in track.get("blocks", []):
            for ex in block.get("exercises", []):
                mt = ex.get("movement_type")
                if mt and mt not in _VALID_MOVEMENT_TYPES:
                    if mt.lower() in _MODALITY_TO_CARDIO:
                        ex["movement_type"] = "cardio"
                    elif mt.lower() in _REMAP_TO_OTHER:
                        ex["movement_type"] = "other"
                    else:
                        ex["movement_type"] = "other"
                        logger.info(
                            "Post-process: unknown movement_type '%s' on '%s' -> 'other'",
                            mt, ex.get("movement_name", "?"),
                        )

            # Also fix bare "conditioning" block_type -> infer subtype
            block_type = block.get("block_type", "")
            if block_type == "conditioning":
                block_raw = (block.get("raw_text", "") or "").lower()
                if _EMOM_RE.search(block_raw):
                    block["block_type"] = "conditioning_emom"
                elif "amrap" in block_raw or "as many rounds" in block_raw:
                    block["block_type"] = "conditioning_amrap"
                elif "for time" in block_raw or ("against" in block_raw and "clock" in block_raw):
                    block["block_type"] = "conditioning_fortime"
                elif "rest" in block_raw and ("sec" in block_raw or "second" in block_raw):
                    block["block_type"] = "conditioning_interval"
                else:
                    block["block_type"] = "conditioning_fortime"
                logger.info(
                    "Post-process: refined block_type 'conditioning' -> '%s'",
                    block["block_type"],
                )


def _fix_set_inheritance(data: dict) -> None:
    """
    Ensure exercises in superset/circuit blocks inherit the block's set count.

    If block raw_text says 'Two or three sets of:' but exercises have sets=null,
    fill them in.
    """
    for track in data.get("tracks", []):
        for block in track.get("blocks", []):
            block_raw = (block.get("raw_text", "") or "").lower()
            exercises = block.get("exercises", [])

            if not exercises:
                continue

            # Check for set count in block header
            match = _SET_COUNT_RE.search(block_raw)
            if not match:
                continue

            word = match.group(0).split()[0].lower()
            set_count = _SET_WORD_TO_NUM.get(word)
            if not set_count:
                continue

            # Apply to exercises missing sets
            for ex in exercises:
                if ex.get("sets") is None:
                    ex["sets"] = set_count


def _fix_alternative_group_ids(data: dict) -> None:
    """
    Ensure alternative_group_id values are integers (or None).

    The LLM sometimes returns string IDs like "row1" instead of integers.
    Convert string group IDs to sequential integers per block.
    """
    for track in data.get("tracks", []):
        for block in track.get("blocks", []):
            exercises = block.get("exercises", [])
            # Collect all unique non-None group IDs
            group_map: dict[Any, int] = {}
            next_id = 1
            for ex in exercises:
                gid = ex.get("alternative_group_id")
                if gid is None:
                    continue
                if isinstance(gid, int):
                    continue
                # String or other non-int: map to sequential int
                if gid not in group_map:
                    group_map[gid] = next_id
                    next_id += 1
                ex["alternative_group_id"] = group_map[gid]


def _fix_display_orders(data: dict) -> None:
    """
    Ensure all display_order values are sequential and 0-based.
    """
    for t_idx, track in enumerate(data.get("tracks", [])):
        track["display_order"] = t_idx
        for b_idx, block in enumerate(track.get("blocks", [])):
            block["display_order"] = b_idx
            for e_idx, exercise in enumerate(block.get("exercises", [])):
                exercise["display_order"] = e_idx
