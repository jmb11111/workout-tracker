// ---------------------------------------------------------------------------
// Movements
// ---------------------------------------------------------------------------

export interface Movement {
  id: number;
  name: string;
  movement_type: string;
  is_named_benchmark: boolean;
  aliases: string[];
  muscle_groups: string[];
}

// ---------------------------------------------------------------------------
// Conditioning
// ---------------------------------------------------------------------------

export interface ConditioningInterval {
  id: number;
  interval_order: number;
  modality: string;
  distance_meters: number | null;
  calories: number | null;
  duration_seconds: number | null;
  effort_percent: number | null;
}

export interface ConditioningWorkout {
  id: number;
  format: string;
  duration_minutes: number | null;
  rounds: number | null;
  time_cap_minutes: number | null;
  is_partner: boolean;
  is_named_benchmark: boolean;
  benchmark_name: string | null;
  intervals: ConditioningInterval[];
}

// ---------------------------------------------------------------------------
// Exercises
// ---------------------------------------------------------------------------

export interface ExerciseResult {
  id: number;
  log_id: number;
  exercise_id: number | null;
  movement_id: number | null;
  sets_completed: number | null;
  reps_per_set: number[] | null;
  weight_per_set_lbs: number[] | null;
  weight_per_set_kg: number[] | null;
  tempo_used: string | null;
  rpe_actual: number | null;
  notes: string | null;
  is_pr: boolean;
}

export interface Exercise {
  id: number;
  movement_id: number | null;
  movement: Movement | null;
  display_order: number;
  sets: number | null;
  reps_min: number | null;
  reps_max: number | null;
  duration_seconds: number | null;
  tempo: string | null;
  rpe_min: number | null;
  rpe_max: number | null;
  percent_1rm_min: number | null;
  percent_1rm_max: number | null;
  rest_seconds: number | null;
  notes: string | null;
  is_alternative: boolean;
  alternative_group_id: number | null;
  last_result: ExerciseResult | null;
}

// ---------------------------------------------------------------------------
// Workout blocks
// ---------------------------------------------------------------------------

export interface WorkoutBlock {
  id: number;
  label: string | null;
  block_type: string;
  raw_text: string | null;
  display_order: number;
  exercises: Exercise[];
  conditioning_workouts: ConditioningWorkout[];
}

// ---------------------------------------------------------------------------
// Workout tracks
// ---------------------------------------------------------------------------

export interface WorkoutTrack {
  id: number;
  track_type: string;
  display_order: number;
  blocks: WorkoutBlock[];
}

// ---------------------------------------------------------------------------
// Workout day
// ---------------------------------------------------------------------------

export interface WorkoutDay {
  id: number;
  date: string;
  source_url: string | null;
  raw_text: string | null;
  parse_confidence: number;
  parse_flagged: boolean;
  parse_method: string | null;
  created_at: string | null;
  updated_at: string | null;
  tracks: WorkoutTrack[];
}

// ---------------------------------------------------------------------------
// Calendar
// ---------------------------------------------------------------------------

export interface CalendarDay {
  date: string;
  has_workout: boolean;
  user_logged: boolean;
}

export interface CalendarResponse {
  year: number;
  month: number;
  days: CalendarDay[];
}

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------

export interface ExerciseResultCreate {
  exercise_id?: number | null;
  movement_id?: number | null;
  sets_completed?: number | null;
  reps_per_set?: number[] | null;
  weight_per_set_lbs?: number[] | null;
  weight_per_set_kg?: number[] | null;
  tempo_used?: string | null;
  rpe_actual?: number | null;
  notes?: string | null;
}

export interface ConditioningResultCreate {
  conditioning_workout_id?: number | null;
  result_type?: string | null;
  rounds_completed?: number | null;
  reps_completed?: number | null;
  time_seconds?: number | null;
  total_reps?: number | null;
  notes?: string | null;
  is_named_benchmark?: boolean;
}

export interface ConditioningResult {
  id: number;
  log_id: number;
  conditioning_workout_id: number | null;
  result_type: string | null;
  rounds_completed: number | null;
  reps_completed: number | null;
  time_seconds: number | null;
  total_reps: number | null;
  notes: string | null;
  is_named_benchmark: boolean;
}

// ---------------------------------------------------------------------------
// Workout logs
// ---------------------------------------------------------------------------

export interface WorkoutLogCreate {
  workout_day_id: number;
  track_type: string;
  selected_option?: string | null;
}

export interface WorkoutLogUpdate {
  overall_notes?: string | null;
  completed?: boolean | null;
}

export interface WorkoutLog {
  id: number;
  user_id: number;
  workout_day_id: number;
  track_type: string;
  logged_at: string | null;
  overall_notes: string | null;
  completed: boolean;
  selected_option: string | null;
  exercise_results: ExerciseResult[];
  conditioning_results: ConditioningResult[];
}

// ---------------------------------------------------------------------------
// Personal records
// ---------------------------------------------------------------------------

export interface PersonalRecord {
  id: number;
  user_id: number;
  movement_id: number;
  movement_name: string | null;
  record_type: string;
  value: number;
  reps: number | null;
  set_count: number | null;
  tempo: string | null;
  notes: string | null;
  achieved_at: string | null;
  exercise_result_id: number | null;
}

export interface GroupedPersonalRecords {
  movement: Movement;
  records: Record<string, PersonalRecord>;
}

export interface BenchmarkAttempt {
  date: string | null;
  result_type: string | null;
  rounds_completed: number | null;
  reps_completed: number | null;
  time_seconds: number | null;
  total_reps: number | null;
  notes: string | null;
}

export interface BenchmarkGroup {
  benchmark_name: string;
  attempts: BenchmarkAttempt[];
}

// ---------------------------------------------------------------------------
// Movement history and stats
// ---------------------------------------------------------------------------

export interface MovementHistoryEntry {
  date: string;
  exercise_result_id: number;
  sets_completed: number | null;
  reps_per_set: number[] | null;
  weight_per_set_lbs: number[] | null;
  weight_per_set_kg: number[] | null;
  rpe_actual: number | null;
  notes: string | null;
  is_pr: boolean;
}

export interface MovementHistoryResponse {
  movement: Movement;
  history: MovementHistoryEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface MovementStatsResponse {
  movement: Movement;
  best_1rm: number | null;
  best_3rm: number | null;
  best_5rm: number | null;
  total_sessions: number;
  volume_over_time: VolumeDataPoint[];
}

export interface VolumeDataPoint {
  date: string;
  volume: number;
  max_weight: number;
  sets: number;
}

// ---------------------------------------------------------------------------
// User
// ---------------------------------------------------------------------------

export interface User {
  id: number;
  authentik_sub: string;
  display_name: string | null;
  email: string | null;
  weight_unit: 'lbs' | 'kg';
  dark_mode: boolean;
  created_at: string | null;
}

export interface UserUpdate {
  weight_unit?: string | null;
  dark_mode?: boolean | null;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number | null;
  refresh_token: string | null;
}

export interface LoginUrlResponse {
  authorization_url: string;
}

// ---------------------------------------------------------------------------
// Scraper
// ---------------------------------------------------------------------------

export interface ScraperStatusResponse {
  last_run_at: string | null;
  last_run_success: boolean | null;
  last_run_method: string | null;
  last_run_confidence: number | null;
  last_run_error: string | null;
  next_run_at: string | null;
  scheduler_running: boolean;
}

export interface ScraperTriggerResponse {
  date: string;
  success: boolean;
  method: string | null;
  confidence: number;
  flagged: boolean;
  error: string | null;
  workout_day_id: number | null;
}

export interface ReparseResponse {
  workout_day_id: number;
  success: boolean;
  method: string | null;
  confidence: number;
  flagged: boolean;
  error: string | null;
  date: string | null;
}
