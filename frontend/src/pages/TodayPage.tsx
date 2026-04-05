import { useState, useEffect, useCallback } from 'react';
import { format, addDays, subDays } from 'date-fns';
import { ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react';
import { useWorkout } from '../hooks/useWorkout';
import { useAuth } from '../hooks/useAuth';
import {
  getLog,
  createLog,
  saveExerciseResults,
  saveConditioningResults,
  getMe,
} from '../api/client';
import type {
  WorkoutTrack,
  WorkoutLog,
  Exercise,
  ConditioningWorkout,
  ExerciseResultCreate,
  ConditioningResultCreate,
  User,
} from '../types';
import BlockCard from '../components/BlockCard';
import ResultSheet from '../components/ResultSheet';
import LoadingSpinner from '../components/LoadingSpinner';

export default function TodayPage() {
  const { workout, loading, error, loadDate, currentDate } = useWorkout();
  const { isAuthenticated } = useAuth();

  const [selectedTrack, setSelectedTrack] = useState<string>('fitness_performance');
  const [log, setLog] = useState<WorkoutLog | null>(null);
  const [user, setUser] = useState<User | null>(null);

  // ResultSheet state
  const [sheetExercise, setSheetExercise] = useState<Exercise | null>(null);
  const [sheetConditioning, setSheetConditioning] = useState<ConditioningWorkout | null>(null);

  // Load user
  useEffect(() => {
    if (isAuthenticated) {
      getMe().then(setUser).catch(() => {});
    }
  }, [isAuthenticated]);

  // Load existing log
  useEffect(() => {
    if (workout && isAuthenticated) {
      getLog(workout.id)
        .then((l) => setLog(l))
        .catch(() => setLog(null));
    } else {
      setLog(null);
    }
  }, [workout, isAuthenticated]);

  // Auto-select first track
  useEffect(() => {
    if (workout?.tracks?.length) {
      setSelectedTrack(workout.tracks[0].track_type);
    }
  }, [workout]);

  const currentTrack: WorkoutTrack | undefined = workout?.tracks?.find(
    (t) => t.track_type === selectedTrack,
  );

  const dateObj = new Date(currentDate + 'T12:00:00');
  const formattedDate = format(dateObj, 'EEEE, MMMM d');

  const goToPrev = () => {
    const prev = subDays(dateObj, 1);
    loadDate(format(prev, 'yyyy-MM-dd'));
  };

  const goToNext = () => {
    const next = addDays(dateObj, 1);
    loadDate(format(next, 'yyyy-MM-dd'));
  };

  // Ensure log exists before saving results
  const ensureLog = useCallback(async (): Promise<WorkoutLog> => {
    if (log) return log;
    if (!workout) throw new Error('No workout loaded');
    const newLog = await createLog({
      workout_day_id: workout.id,
      track_type: selectedTrack,
    });
    setLog(newLog);
    return newLog;
  }, [log, workout, selectedTrack]);

  const handleExerciseSave = useCallback(
    async (result: ExerciseResultCreate) => {
      const currentLog = await ensureLog();
      const results = await saveExerciseResults(currentLog.id, [result]);
      setLog((prev) => {
        if (!prev) return prev;
        // Upsert: replace existing results for the same exercise, append new ones
        const updatedIds = new Set(results.map((r) => r.exercise_id));
        const kept = prev.exercise_results.filter((r) => !updatedIds.has(r.exercise_id));
        return { ...prev, exercise_results: [...kept, ...results] };
      });
    },
    [ensureLog],
  );

  const handleConditioningSave = useCallback(
    async (result: ConditioningResultCreate) => {
      const currentLog = await ensureLog();
      const results = await saveConditioningResults(currentLog.id, [result]);
      setLog((prev) => {
        if (!prev) return prev;
        const updatedIds = new Set(results.map((r) => r.conditioning_workout_id));
        const kept = prev.conditioning_results.filter((r) => !updatedIds.has(r.conditioning_workout_id));
        return { ...prev, conditioning_results: [...kept, ...results] };
      });
    },
    [ensureLog],
  );

  const weightUnit = user?.weight_unit ?? 'lbs';

  return (
    <div className="mx-auto max-w-lg px-4 pt-4">
      {/* Date header with navigation */}
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={goToPrev}
          className="flex h-10 w-10 items-center justify-center rounded-full transition-colors active:bg-gray-100 dark:active:bg-gray-800"
        >
          <ChevronLeft size={22} className="text-gray-500 dark:text-gray-400" />
        </button>
        <h1 className="text-center text-lg font-bold text-gray-900 dark:text-gray-100">
          {formattedDate}
        </h1>
        <button
          onClick={goToNext}
          className="flex h-10 w-10 items-center justify-center rounded-full transition-colors active:bg-gray-100 dark:active:bg-gray-800"
        >
          <ChevronRight size={22} className="text-gray-500 dark:text-gray-400" />
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-20">
          <LoadingSpinner message="Loading workout..." />
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="rounded-xl bg-gray-50 px-4 py-12 text-center dark:bg-gray-900">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {error.includes('404') || error.includes('not found')
              ? 'No workout posted yet for this day.'
              : error}
          </p>
        </div>
      )}

      {/* Workout content */}
      {workout && !loading && (
        <>
          {/* Parse warning */}
          {workout.parse_flagged && (
            <div className="mb-4 flex items-center gap-2 rounded-lg bg-yellow-500/15 px-3 py-2 text-yellow-600 dark:text-yellow-400">
              <AlertTriangle size={16} />
              <span className="text-sm font-medium">
                This workout may not have parsed correctly
              </span>
            </div>
          )}

          {/* Track tabs */}
          {workout.tracks.length > 1 && (
            <div className="mb-4 flex gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800">
              {workout.tracks
                .sort((a, b) => a.display_order - b.display_order)
                .map((track) => {
                  const label =
                    track.track_type === 'fitness_performance'
                      ? 'Fitness & Performance'
                      : track.track_type === 'endurance'
                        ? 'Endurance'
                        : track.track_type.replace(/_/g, ' ');
                  return (
                    <button
                      key={track.id}
                      onClick={() => setSelectedTrack(track.track_type)}
                      className={`min-h-[40px] flex-1 rounded-lg px-3 py-2 text-xs font-semibold uppercase tracking-wide transition-colors ${
                        selectedTrack === track.track_type
                          ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-gray-100'
                          : 'text-gray-500 dark:text-gray-400'
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
            </div>
          )}

          {/* Blocks */}
          {currentTrack && (
            <div className="space-y-3 pb-6">
              {currentTrack.blocks
                .sort((a, b) => a.display_order - b.display_order)
                .map((block) => (
                  <BlockCard
                    key={block.id}
                    block={block}
                    weightUnit={weightUnit}
                    exerciseResults={log?.exercise_results ?? []}
                    conditioningResults={log?.conditioning_results ?? []}
                    onExerciseTap={(exerciseId) => {
                      const ex = block.exercises.find((e) => e.id === exerciseId);
                      if (ex) setSheetExercise(ex);
                    }}
                    onConditioningTap={(condId) => {
                      const cw = block.conditioning_workouts.find((c) => c.id === condId);
                      if (cw) setSheetConditioning(cw);
                    }}
                    onBlockConditioningTap={
                      block.block_type.startsWith('conditioning') && block.conditioning_workouts[0]
                        ? () => setSheetConditioning(block.conditioning_workouts[0])
                        : undefined
                    }
                  />
                ))}
            </div>
          )}

          {/* No track content */}
          {!currentTrack && (
            <div className="rounded-xl bg-gray-50 px-4 py-12 text-center dark:bg-gray-900">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No content for this track.
              </p>
            </div>
          )}
        </>
      )}

      {/* ResultSheet for strength */}
      {sheetExercise && (
        <ResultSheet
          mode="strength"
          exercise={sheetExercise}
          weightUnit={weightUnit}
          onSave={async (result) => {
            await handleExerciseSave(result);
          }}
          onClose={() => setSheetExercise(null)}
        />
      )}

      {/* ResultSheet for conditioning */}
      {sheetConditioning && (
        <ResultSheet
          mode="conditioning"
          conditioning={sheetConditioning}
          existingNotes={
            log?.conditioning_results.find(
              (r) => r.conditioning_workout_id === sheetConditioning.id,
            )?.notes
          }
          onSave={async (result) => {
            await handleConditioningSave(result);
          }}
          onClose={() => setSheetConditioning(null)}
        />
      )}
    </div>
  );
}
