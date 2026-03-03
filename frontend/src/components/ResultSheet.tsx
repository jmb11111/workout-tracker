import { useState, useEffect, useRef, useCallback } from 'react';
import { X, Plus, Trash2, Trophy, Check, Info } from 'lucide-react';
import type {
  Exercise,
  ConditioningWorkout,
  ExerciseResultCreate,
  ConditioningResultCreate,
} from '../types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StrengthSheetProps {
  mode: 'strength';
  exercise: Exercise;
  weightUnit: 'lbs' | 'kg';
  onSave: (result: ExerciseResultCreate) => Promise<void>;
  onClose: () => void;
}

interface ConditioningSheetProps {
  mode: 'conditioning';
  conditioning: ConditioningWorkout;
  existingNotes?: string | null;
  onSave: (result: ConditioningResultCreate) => Promise<void>;
  onClose: () => void;
}

type ResultSheetProps = StrengthSheetProps | ConditioningSheetProps;

// ---------------------------------------------------------------------------
// Set row for strength mode
// ---------------------------------------------------------------------------

interface SetRow {
  reps: string;
  weight: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildInfoItems(exercise: Exercise): { label: string; value: string }[] {
  const items: { label: string; value: string }[] = [];

  if (exercise.tempo) {
    items.push({ label: 'Tempo', value: exercise.tempo });
  }

  if (exercise.rpe_min || exercise.rpe_max) {
    const val =
      exercise.rpe_min && exercise.rpe_max && exercise.rpe_min !== exercise.rpe_max
        ? `${exercise.rpe_min}–${exercise.rpe_max}`
        : `${exercise.rpe_max ?? exercise.rpe_min}`;
    items.push({ label: 'RPE', value: val });
  }

  if (exercise.percent_1rm_min || exercise.percent_1rm_max) {
    const val =
      exercise.percent_1rm_min && exercise.percent_1rm_max && exercise.percent_1rm_min !== exercise.percent_1rm_max
        ? `${exercise.percent_1rm_min}–${exercise.percent_1rm_max}%`
        : `${exercise.percent_1rm_max ?? exercise.percent_1rm_min}%`;
    items.push({ label: '%1RM', value: val });
  }

  if (exercise.rest_seconds) {
    const secs = exercise.rest_seconds;
    const val = secs >= 60 ? `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}` : `${secs}s`;
    items.push({ label: 'Rest', value: val });
  }

  return items;
}

function prescribedReps(exercise: Exercise): string {
  if (exercise.reps_min && exercise.reps_max && exercise.reps_min !== exercise.reps_max) {
    return `${exercise.reps_min}–${exercise.reps_max}`;
  }
  if (exercise.reps_min) return `${exercise.reps_min}`;
  if (exercise.duration_seconds) return `${exercise.duration_seconds}s`;
  return '';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ResultSheet(props: ResultSheetProps) {
  const { onClose } = props;
  const backdropRef = useRef<HTMLDivElement>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Strength state
  const [sets, setSets] = useState<SetRow[]>([{ reps: '', weight: '' }]);
  const [notes, setNotes] = useState('');

  // Conditioning state
  const [condNotes, setCondNotes] = useState(
    props.mode === 'conditioning' ? (props.existingNotes ?? '') : '',
  );

  // PR detection state
  const [isPR, setIsPR] = useState(false);

  // Pre-populate from prescription and/or last result
  useEffect(() => {
    if (props.mode === 'strength') {
      const ex = props.exercise;
      const lr = ex.last_result;
      const numSets = ex.sets || 1;
      const defaultReps = ex.reps_min ? String(ex.reps_min) : '';

      if (lr && lr.reps_per_set && lr.reps_per_set.length > 0) {
        // Pre-populate from last result
        const weights = props.weightUnit === 'lbs' ? lr.weight_per_set_lbs : lr.weight_per_set_kg;
        const newSets: SetRow[] = [];
        for (let i = 0; i < numSets; i++) {
          newSets.push({
            reps: lr.reps_per_set[i] != null ? String(lr.reps_per_set[i]) : defaultReps,
            weight: weights && weights[i] != null ? String(weights[i]) : '',
          });
        }
        setSets(newSets);
      } else {
        // Just use prescribed reps
        setSets(
          Array.from({ length: numSets }, () => ({
            reps: defaultReps,
            weight: '',
          })),
        );
      }
    }
  }, [props]);

  // Simple PR check
  useEffect(() => {
    if (props.mode !== 'strength') return;
    const lr = props.exercise.last_result;
    if (!lr) return;

    const lastWeights = props.weightUnit === 'lbs' ? lr.weight_per_set_lbs : lr.weight_per_set_kg;
    const maxLast = lastWeights?.length ? Math.max(...lastWeights) : 0;

    const currentWeights = sets
      .map((s) => parseFloat(s.weight))
      .filter((w) => !isNaN(w));
    const maxCurrent = currentWeights.length ? Math.max(...currentWeights) : 0;

    setIsPR(maxCurrent > maxLast);
  }, [sets, props]);

  const addSet = () => {
    const lastSet = sets[sets.length - 1];
    setSets([...sets, { reps: lastSet?.reps || '', weight: lastSet?.weight || '' }]);
  };

  const removeSet = (index: number) => {
    if (sets.length <= 1) return;
    setSets(sets.filter((_, i) => i !== index));
  };

  const updateSet = (index: number, field: keyof SetRow, value: string) => {
    setSets(sets.map((s, i) => (i === index ? { ...s, [field]: value } : s)));
  };

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      if (props.mode === 'strength') {
        const repsArr = sets.map((s) => parseInt(s.reps) || 0);
        const weightsArr = sets.map((s) => parseFloat(s.weight) || 0);

        const result: ExerciseResultCreate = {
          exercise_id: props.exercise.id,
          movement_id: props.exercise.movement_id,
          sets_completed: sets.length,
          reps_per_set: repsArr,
          ...(props.weightUnit === 'lbs'
            ? { weight_per_set_lbs: weightsArr }
            : { weight_per_set_kg: weightsArr }),
          notes: notes || null,
        };

        await props.onSave(result);
      } else {
        const result: ConditioningResultCreate = {
          conditioning_workout_id: props.conditioning.id,
          result_type: 'notes_only',
          notes: condNotes || null,
        };

        await props.onSave(result);
      }

      setSaved(true);
      setTimeout(() => {
        onClose();
      }, 800);
    } catch (err) {
      console.error('Failed to save result:', err);
      setSaving(false);
    }
  }, [props, sets, notes, condNotes, onClose]);

  // Close on backdrop tap
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === backdropRef.current) {
      onClose();
    }
  };

  // Touch drag to dismiss
  const dragStartY = useRef<number | null>(null);
  const handleTouchStart = (e: React.TouchEvent) => {
    if ((e.target as HTMLElement).closest('.sheet-scrollable')) return;
    dragStartY.current = e.touches[0].clientY;
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    if (dragStartY.current === null) return;
    const deltaY = e.changedTouches[0].clientY - dragStartY.current;
    if (deltaY > 100) {
      onClose();
    }
    dragStartY.current = null;
  };

  // Build info items for strength
  const infoItems = props.mode === 'strength' ? buildInfoItems(props.exercise) : [];
  const rxReps = props.mode === 'strength' ? prescribedReps(props.exercise) : '';
  const exerciseNotes = props.mode === 'strength' ? props.exercise.notes : null;

  return (
    <div
      ref={backdropRef}
      className="backdrop-enter fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm"
      onClick={handleBackdropClick}
    >
      <div
        className="sheet-enter fixed bottom-0 left-0 right-0 z-[60] max-h-[85dvh] overflow-y-auto rounded-t-2xl bg-white shadow-2xl dark:bg-gray-900"
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 16px)' }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {/* Drag handle */}
        <div className="sticky top-0 z-10 flex justify-center bg-white pb-2 pt-3 dark:bg-gray-900">
          <div className="h-1 w-10 rounded-full bg-gray-300 dark:bg-gray-600" />
        </div>

        <div className="px-5 pb-6">
          {/* Header */}
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">
              {props.mode === 'strength'
                ? props.exercise.movement?.name ?? 'Log Result'
                : props.conditioning.benchmark_name ?? props.conditioning.format.toUpperCase()}
            </h3>
            <button
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-gray-100 transition-colors active:bg-gray-200 dark:bg-gray-800 dark:active:bg-gray-700"
            >
              <X size={18} className="text-gray-500" />
            </button>
          </div>

          {/* Success state */}
          {saved && (
            <div className="flex flex-col items-center justify-center gap-3 py-12">
              <div className="checkmark-animate flex h-16 w-16 items-center justify-center rounded-full bg-green-500">
                <Check size={32} className="text-white" />
              </div>
              <p className="text-lg font-semibold text-green-500">Saved!</p>
              {isPR && props.mode === 'strength' && (
                <div className="flex items-center gap-2 rounded-full bg-amber-400/20 px-4 py-2 text-amber-500">
                  <Trophy size={20} />
                  <span className="font-bold">New PR!</span>
                </div>
              )}
            </div>
          )}

          {/* ============================================================= */}
          {/* Strength mode                                                  */}
          {/* ============================================================= */}
          {!saved && props.mode === 'strength' && (
            <>
              {/* Prescription subtitle */}
              {(props.exercise.sets || rxReps) && (
                <p className="mb-3 text-sm text-gray-500 dark:text-gray-400">
                  Rx: {props.exercise.sets ? `${props.exercise.sets} sets` : ''}
                  {props.exercise.sets && rxReps ? ' x ' : ''}
                  {rxReps ? `${rxReps} reps` : ''}
                </p>
              )}

              {/* Info panel — tempo, RPE, %1RM, rest, notes */}
              {(infoItems.length > 0 || exerciseNotes) && (
                <div className="mb-4 rounded-lg bg-blue-500/10 px-3 py-2.5">
                  <div className="mb-1 flex items-center gap-1.5 text-blue-500">
                    <Info size={14} />
                    <span className="text-xs font-semibold uppercase tracking-wide">Intention</span>
                  </div>
                  {infoItems.length > 0 && (
                    <div className="flex flex-wrap gap-x-4 gap-y-0.5">
                      {infoItems.map((item) => (
                        <span key={item.label} className="text-sm text-gray-700 dark:text-gray-300">
                          <span className="font-medium">{item.label}:</span> {item.value}
                        </span>
                      ))}
                    </div>
                  )}
                  {exerciseNotes && (
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                      {exerciseNotes}
                    </p>
                  )}
                </div>
              )}

              {/* PR indicator */}
              {isPR && (
                <div className="mb-4 flex items-center gap-2 rounded-lg bg-amber-400/15 px-3 py-2 text-amber-500">
                  <Trophy size={18} />
                  <span className="text-sm font-bold">New PR!</span>
                </div>
              )}

              {/* Sets — weight + reps */}
              <div className="mb-4">
                <div className="mb-2 grid grid-cols-[auto_1fr_1fr_auto] items-center gap-2">
                  <span className="w-6 text-center text-xs font-medium text-gray-400 dark:text-gray-500">Set</span>
                  <span className="text-xs font-medium text-gray-400 dark:text-gray-500">Weight</span>
                  <span className="text-xs font-medium text-gray-400 dark:text-gray-500">Reps</span>
                  <span className="w-8" />
                </div>
                {sets.map((set, i) => (
                  <div key={i} className="mb-1.5 grid grid-cols-[auto_1fr_1fr_auto] items-center gap-2">
                    <span className="w-6 text-center text-xs font-bold text-gray-400 dark:text-gray-500">
                      {i + 1}
                    </span>
                    <input
                      type="number"
                      inputMode="decimal"
                      placeholder={props.weightUnit}
                      value={set.weight}
                      onChange={(e) => updateSet(i, 'weight', e.target.value)}
                      className="h-11 rounded-lg bg-gray-100 px-3 text-sm text-gray-900 outline-none ring-1 ring-transparent focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                    />
                    <input
                      type="number"
                      inputMode="numeric"
                      placeholder="reps"
                      value={set.reps}
                      onChange={(e) => updateSet(i, 'reps', e.target.value)}
                      className="h-11 rounded-lg bg-gray-100 px-3 text-sm text-gray-900 outline-none ring-1 ring-transparent focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                    />
                    <button
                      onClick={() => removeSet(i)}
                      disabled={sets.length <= 1}
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition-colors active:text-red-500 disabled:opacity-30"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
                <button
                  onClick={addSet}
                  className="mt-1 flex min-h-[40px] w-full items-center justify-center gap-1 rounded-lg border border-dashed border-gray-300 text-sm font-medium text-gray-500 transition-colors active:bg-gray-100 dark:border-gray-600 dark:text-gray-400 dark:active:bg-gray-800"
                >
                  <Plus size={16} />
                  Add Set
                </button>
              </div>

              {/* Notes */}
              <div className="mb-5">
                <label className="mb-1.5 block text-xs font-medium text-gray-400 dark:text-gray-500">
                  Notes
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Any notes..."
                  rows={2}
                  className="w-full rounded-lg bg-gray-100 px-3 py-2.5 text-sm text-gray-900 outline-none ring-1 ring-transparent focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                />
              </div>
            </>
          )}

          {/* ============================================================= */}
          {/* Conditioning mode — just a text box                            */}
          {/* ============================================================= */}
          {!saved && props.mode === 'conditioning' && (
            <div className="mb-5">
              <textarea
                value={condNotes}
                onChange={(e) => setCondNotes(e.target.value)}
                placeholder="How did it go? Times, rounds, notes..."
                rows={5}
                className="w-full rounded-lg bg-gray-100 px-3 py-2.5 text-sm text-gray-900 outline-none ring-1 ring-transparent focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
                autoFocus
              />
            </div>
          )}

          {/* Save button */}
          {!saved && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex min-h-[48px] w-full items-center justify-center rounded-xl bg-blue-500 text-sm font-semibold text-white transition-colors active:bg-blue-600 disabled:opacity-60"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
