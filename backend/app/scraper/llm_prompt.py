"""
Structured prompt for workout parsing via LLM (Ollama or Claude).

This module contains the prompt template used by both the local Ollama
model and the Claude API fallback.
"""

WORKOUT_PARSE_PROMPT = """\
Parse this CrossFit gym's daily workout into JSON. Return ONLY the JSON object — no markdown, no explanation.

STRUCTURE:
{"tracks": [{"track_type": "fitness_performance|endurance", "display_order": 0, "blocks": [BLOCKS]}]}

Each BLOCK:
{"label": "A", "block_type": "TYPE", "raw_text": "verbatim text of this section", "display_order": 0, "exercises": [EXERCISES], "conditioning": null_or_COND_OBJ}

Each EXERCISE (only for strength/accessory/pump blocks — NOT for conditioning):
{"movement_name": "Back Squat", "movement_type": "barbell|dumbbell|kettlebell|bodyweight|machine|cardio|other", "sets": 5, "reps_min": 3, "reps_max": null, "tempo": "20X1", "rpe_min": 7.0, "rpe_max": 8.0, "percent_1rm_min": null, "percent_1rm_max": null, "rest_seconds": 120, "notes": null, "is_alternative": false, "alternative_group_id": null, "duration_seconds": null, "display_order": 0}

COND_OBJ (only for conditioning blocks):
{"format": "amrap|for_time|emom|interval|tabata", "duration_minutes": null, "rounds": null, "time_cap_minutes": null, "is_partner": false, "is_named_benchmark": false, "benchmark_name": null, "intervals": []}

=== CRITICAL: BLOCK TYPE CLASSIFICATION ===

The MOST IMPORTANT rule: "Every X minutes" does NOT automatically mean conditioning.
This gym uses timers for BOTH strength rest periods AND conditioning circuits.

STRENGTH ("strength") — ONE main barbell/dumbbell lift with load progression:
- "Every 3 minutes, for 12 minutes (4 sets): Tempo Back Squat" → STRENGTH
- "Every 2:30, for 12:30 (5 sets): Close Grip Bench Press" → STRENGTH
- "Every 90 seconds, for 12 minutes (8 sets): Power Clean x 1 rep" → STRENGTH
- "Every 2 minutes, for 10 minutes (5 sets): Back Squat" → STRENGTH
- "Four sets of: Tempo Front Squat x 4 reps @ 32X1" → STRENGTH
- "Five sets of: Sumo Deadlift @ 21X1" → STRENGTH
- "Take 12 minutes to establish a 5-Rep Max Strict Overhead Press" → STRENGTH
- Pattern: ONE primary compound movement, RPE targets per set, tempo, loading builds
- The timer is for REST between heavy sets — it does NOT make it conditioning
- exercises array: YES, include the movement(s) with full detail

CONDITIONING — MULTIPLE movements done as a timed circuit:
- "Every 5 minutes, for 15 minutes: 30 Cal Row, 20 Wall Balls, 10 HPC" → conditioning_emom
- "AMRAP 12 min: Wall Balls, Ski, Power Cleans" → conditioning_amrap
- "Against a 90-second clock: 18 Cal Echo Bike, Ball Slams max reps" → conditioning_fortime
- "30 sec Row / Rest 30 sec / 30 sec Bike / Rest 30 sec x 10 rounds" → conditioning_interval
- Pattern: MULTIPLE movements done together for metabolic effect
- exercises array: EMPTY [] — put full description in raw_text instead
- conditioning object: include format, duration, partner/benchmark info

How to tell the difference:
- Count the movements. ONE heavy lift on a timer = strength. TWO OR MORE movements as a circuit = conditioning.
- Look for RPE/tempo targets = strength. Look for cal/distance targets = conditioning.
- "Every 3 min: Back Squat, RPE 7-8-9" = STRENGTH (one lift, RPE targets)
- "Every 5 min: 30 Cal Row + 20 Wall Balls + 10 HPC" = CONDITIONING (three movements, circuit)

ACCESSORY ("accessory") — Supplementary exercises in supersets:
- "Two or three sets of: Filly Carry, Band Pull Aparts, Side Plank"
- "Three sets of: DB Row, Plank, Face Pulls"
- Pattern: multiple lighter exercises with rest periods, superset format
- exercises array: YES, include each exercise

PUMP ("pump") — Hypertrophy work, explicitly labeled "PUMP":
- Only use when text explicitly says "PUMP"
- exercises array: YES, include each exercise

SKILL ("other") — Gymnastic/skill practice:
- Handstand holds, L-sits, muscle-up progressions
- exercises array: YES, include each exercise

=== TRACK RULES ===

Split into SEPARATE tracks based on section headers:
- "FITNESS" & "PERFORMANCE" or "FITNESS & PERFORMANCE" → ONE track: "fitness_performance"
- "FITNESS" alone → "fitness_performance" track
- "PERFORMANCE" alone → "fitness_performance" track
- "BURN" → separate "fitness_performance" track
- "ENDURANCE" or "ENDURANCE (AKA SWEAT SESH)" → ALWAYS "endurance" track
- "PUMP" as a standalone track header → "fitness_performance" track
- If "FITNESS" has "B. Same as Performance" or "B. See below", merge into one track

=== EXERCISE DETAIL RULES ===

SETS — extract the number:
- "Two or three sets of:" → sets=3 (use higher number)
- "Three working sets of:" → sets=3
- "Four sets:" → sets=4
- "3 x 5" → sets=3
- "(4 working sets)" in timer description → sets=4
- Exercises in a superset block inherit the block's set count

TEMPO — 4-character codes like "20X1", "32X1", "21X0", "30X1":
- Copy EXACT 4-character string, X is literal
- "Tempo Back Squat x 4 reps @ 32X1" → tempo="32X1"

RPE — escalating across sets:
- "Set 1 RPE 7, Set 2 RPE 8, Set 3 RPE 9" → rpe_min=7.0, rpe_max=9.0
- "RPE 7-8" or "7-8/10" → rpe_min=7.0, rpe_max=8.0
- If a final set has "Max Reps" at different scheme, create a SECOND exercise entry

REST:
- "Rest 2 minutes" → rest_seconds=120
- "Rest 60-90 seconds" → rest_seconds=90 (use higher)

ALTERNATIVES — split "OR" into separate exercises:
- "Power Cleans or Russian KB Swings" → TWO exercises, both is_alternative=true, same alternative_group_id
- "Side Plank or Star Plank" → TWO alternatives
- "Pull-ups (or Jumping Pull-ups)" → TWO alternatives

OPTION 1 / OPTION 2 — create separate blocks:
- "Option 1: Conditioning" → label="C - Option 1"
- "Option 2: PUMP" → label="C - Option 2", block_type="pump"
- "OR" between major sections (B. Conditioning OR "PUMP") → two blocks with different labels

GENDER-SCALED VALUES — use the higher (male) number:
- "30/25 Calorie Row" → in raw_text as-is
- "300/270 Meter Ski" → in raw_text as-is

NAMED BENCHMARKS:
- Names in quotes: Team "Barbara" → is_named_benchmark=true, benchmark_name="Barbara"

PARTNER WORKOUTS:
- "In teams of two" or "partners alternate" → is_partner=true

MOVEMENT TYPES:
- barbell: Squat, Deadlift, Press, Clean, Snatch, Thruster, Jerk
- dumbbell: DB/Dumbbell anything
- kettlebell: KB/Kettlebell, Turkish Get Up, Filly Carry, Goblet (when KB specified)
- bodyweight: Pull-up, Push-up, Burpee, Plank, V-Up, Lunge (unweighted), Muscle-Up
- cardio: Bike Erg, Row, Ski, Run, Echo Bike, Air Runner
- other: Band work, plate exercises

=== RAW_TEXT RULES ===

For EVERY block, raw_text must contain the COMPLETE verbatim text of that section.
For conditioning blocks, raw_text is especially important since exercises array is empty.
Include all movements, reps, weights, rest periods, and coaching notes in raw_text.

=== WORKOUT TEXT ===

{workout_text}

=== JSON OUTPUT ==="""


def build_prompt(raw_text: str) -> str:
    """
    Build the complete prompt by inserting the workout text.

    Args:
        raw_text: The cleaned plain text of the workout post.

    Returns:
        The full prompt string ready to send to an LLM.
    """
    return WORKOUT_PARSE_PROMPT.replace("{workout_text}", raw_text)
