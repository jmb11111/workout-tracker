import { useState, useEffect, useCallback } from 'react';
import { format, addDays, subDays } from 'date-fns';
import { ChevronLeft, ChevronRight, AlertTriangle, ClipboardList } from 'lucide-react';
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
  const [showExerciseList, setShowExerciseList] = useState(false);

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
      setLog((prev) =>
        prev
          ? {
              ...prev,
              exercise_results: [...prev.exercise_results, ...results],
            }
          : prev,
      );
    },
    [ensureLog],
  );

  const handleConditioningSave = useCallback(
    async (result: ConditioningResultCreate) => {
      const currentLog = await ensureLog();
      const results = await saveConditioningResults(currentLog.id, [result]);
      setLog((prev) =>
        prev
          ? {
              ...prev,
              conditioning_results: [...prev.conditioning_results, ...results],
            }
          : prev,
      );
    },
    [ensureLog],
  );

  // Collect exercises from NON-conditioning blocks only (conditioning is logged per-block)
  const allExercises: Exercise[] =
    currentTrack?.blocks
      ?.filter((b) => !b.block_type.startsWith('conditioning'))
      .flatMap((b) => b.exercises) ?? [];
  // Collect conditioning blocks as whole units
  const conditioningBlocks = currentTrack?.blocks?.filter(
    (b) => b.block_type.startsWith('conditioning') && b.conditioning_workouts.length > 0,
  ) ?? [];
  // allConditioning used to be referenced but conditioningBlocks replaces it

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

      {/* Log Results CTA */}
      {workout && isAuthenticated && !loading && !sheetExercise && !sheetConditioning && (
        <div
          className="fixed bottom-20 left-0 right-0 z-40 px-4"
          style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
        >
          <div className="mx-auto max-w-lg">
            <button
              onClick={() => setShowExerciseList(true)}
              className="flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-blue-500 text-sm font-semibold text-white shadow-lg shadow-blue-500/25 transition-colors active:bg-blue-600"
            >
              <ClipboardList size={18} />
              Log Results
            </button>
          </div>
        </div>
      )}

      {/* Exercise list overlay */}
      {showExerciseList && (
        <div
          className="backdrop-enter fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowExerciseList(false);
          }}
        >
          <div
            className="sheet-enter fixed bottom-0 left-0 right-0 z-[60] max-h-[85dvh] overflow-y-auto rounded-t-2xl bg-white shadow-2xl dark:bg-gray-900"
            style={{ paddingBottom: 'env(safe-area-inset-bottom, 16px)' }}
          >
            <div className="sticky top-0 z-10 flex justify-center bg-white pb-2 pt-3 dark:bg-gray-900">
              <div className="h-1 w-10 rounded-full bg-gray-300 dark:bg-gray-600" />
            </div>
            <div className="px-5 pb-6">
              <h3 className="mb-4 text-lg font-bold text-gray-900 dark:text-gray-100">
                Log Results
              </h3>

              {/* Exercises */}
              {allExercises.length > 0 && (
                <div className="space-y-1.5">
                  {allExercises.map((ex) => {
                    const isCompleted = log?.exercise_results.some(
                      (r) => r.exercise_id === ex.id,
                    );
                    return (
                      <button
                        key={ex.id}
                        onClick={() => {
                          setShowExerciseList(false);
                          setSheetExercise(ex);
                        }}
                        className={`flex min-h-[48px] w-full items-center justify-between rounded-lg px-3 py-2.5 text-left transition-colors active:bg-gray-100 dark:active:bg-gray-800 ${
                          isCompleted
                            ? 'bg-green-500/10'
                            : 'bg-gray-50 dark:bg-gray-800/50'
                        }`}
                      >
                        <span
                          className={`text-sm font-medium ${
                            isCompleted
                              ? 'text-green-600 dark:text-green-400'
                              : 'text-gray-900 dark:text-gray-100'
                          }`}
                        >
                          {ex.movement?.name ?? 'Exercise'}
                        </span>
                        {isCompleted && (
                          <span className="text-green-500">
                            <svg width="18" height="18" viewBox="0 0 16 16" fill="none">
                              <path d="M3 8.5L6.5 12L13 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Conditioning blocks */}
              {conditioningBlocks.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
                    Conditioning
                  </p>
                  {conditioningBlocks.map((blk) => {
                    const cw = blk.conditioning_workouts[0];
                    if (!cw) return null;
                    const isCompleted = log?.conditioning_results.some(
                      (r) => r.conditioning_workout_id === cw.id,
                    );
                    const label = cw.benchmark_name
                      ?? `${blk.label ? blk.label + '. ' : ''}${cw.format.toUpperCase()}${cw.duration_minutes ? ` ${cw.duration_minutes}min` : ''}`;
                    return (
                      <button
                        key={cw.id}
                        onClick={() => {
                          setShowExerciseList(false);
                          setSheetConditioning(cw);
                        }}
                        className={`flex min-h-[48px] w-full items-center justify-between rounded-lg px-3 py-2.5 text-left transition-colors active:bg-gray-100 dark:active:bg-gray-800 ${
                          isCompleted
                            ? 'bg-green-500/10'
                            : 'bg-gray-50 dark:bg-gray-800/50'
                        }`}
                      >
                        <span
                          className={`text-sm font-medium ${
                            isCompleted
                              ? 'text-green-600 dark:text-green-400'
                              : 'text-gray-900 dark:text-gray-100'
                          }`}
                        >
                          {label}
                        </span>
                        {isCompleted && (
                          <span className="text-green-500">
                            <svg width="18" height="18" viewBox="0 0 16 16" fill="none">
                              <path d="M3 8.5L6.5 12L13 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
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
