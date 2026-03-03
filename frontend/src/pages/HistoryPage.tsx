import { useState, useEffect, useCallback } from 'react';
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  getDay,
  addMonths,
  subMonths,
  isSameDay,
} from 'date-fns';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { getCalendar, getWorkout, getLog } from '../api/client';
import type { CalendarDay, WorkoutDay, WorkoutLog } from '../types';
import LoadingSpinner from '../components/LoadingSpinner';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function HistoryPage() {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [calendarDays, setCalendarDays] = useState<CalendarDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedWorkout, setSelectedWorkout] = useState<WorkoutDay | null>(null);
  const [selectedLog, setSelectedLog] = useState<WorkoutLog | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth() + 1;

  const fetchCalendar = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCalendar(year, month);
      setCalendarDays(data.days);
    } catch {
      setCalendarDays([]);
    } finally {
      setLoading(false);
    }
  }, [year, month]);

  useEffect(() => {
    fetchCalendar();
  }, [fetchCalendar]);

  const handleDayClick = async (dateStr: string) => {
    if (selectedDate === dateStr) {
      setSelectedDate(null);
      setSelectedWorkout(null);
      setSelectedLog(null);
      return;
    }

    setSelectedDate(dateStr);
    setDetailLoading(true);
    try {
      const workout = await getWorkout(dateStr);
      setSelectedWorkout(workout);
      try {
        const log = await getLog(workout.id);
        setSelectedLog(log);
      } catch {
        setSelectedLog(null);
      }
    } catch {
      setSelectedWorkout(null);
      setSelectedLog(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const start = startOfMonth(currentMonth);
  const end = endOfMonth(currentMonth);
  const daysInMonth = eachDayOfInterval({ start, end });
  const startDayOfWeek = getDay(start);

  // Map calendar days for quick lookup
  const dayMap = new Map(calendarDays.map((d) => [d.date, d]));

  return (
    <div className="mx-auto max-w-lg px-4 pt-4">
      {/* Month header */}
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
          className="flex h-10 w-10 items-center justify-center rounded-full transition-colors active:bg-gray-100 dark:active:bg-gray-800"
        >
          <ChevronLeft size={22} className="text-gray-500 dark:text-gray-400" />
        </button>
        <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">
          {format(currentMonth, 'MMMM yyyy')}
        </h1>
        <button
          onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
          className="flex h-10 w-10 items-center justify-center rounded-full transition-colors active:bg-gray-100 dark:active:bg-gray-800"
        >
          <ChevronRight size={22} className="text-gray-500 dark:text-gray-400" />
        </button>
      </div>

      {loading && (
        <div className="flex justify-center py-10">
          <LoadingSpinner />
        </div>
      )}

      {!loading && (
        <>
          {/* Weekday headers */}
          <div className="mb-1 grid grid-cols-7 text-center">
            {WEEKDAYS.map((day) => (
              <span
                key={day}
                className="py-1 text-xs font-medium text-gray-400 dark:text-gray-500"
              >
                {day}
              </span>
            ))}
          </div>

          {/* Calendar grid */}
          <div className="grid grid-cols-7 gap-0.5">
            {/* Empty cells for offset */}
            {Array.from({ length: startDayOfWeek }).map((_, i) => (
              <div key={`empty-${i}`} className="aspect-square" />
            ))}

            {daysInMonth.map((day) => {
              const dateStr = format(day, 'yyyy-MM-dd');
              const calDay = dayMap.get(dateStr);
              const hasWorkout = calDay?.has_workout ?? false;
              const userLogged = calDay?.user_logged ?? false;
              const isSelected = selectedDate === dateStr;
              const isToday = isSameDay(day, new Date());

              return (
                <button
                  key={dateStr}
                  onClick={() => handleDayClick(dateStr)}
                  className={`relative flex aspect-square min-h-[40px] flex-col items-center justify-center rounded-lg text-sm transition-colors ${
                    isSelected
                      ? 'bg-blue-500 text-white'
                      : isToday
                        ? 'bg-blue-500/10 font-bold text-blue-500'
                        : 'text-gray-700 active:bg-gray-100 dark:text-gray-300 dark:active:bg-gray-800'
                  }`}
                >
                  {format(day, 'd')}
                  {/* Dots */}
                  {(hasWorkout || userLogged) && (
                    <div className="absolute bottom-1.5 flex gap-0.5">
                      {hasWorkout && (
                        <span
                          className={`h-1 w-1 rounded-full ${
                            isSelected ? 'bg-white/70' : 'bg-gray-400 dark:bg-gray-500'
                          }`}
                        />
                      )}
                      {userLogged && (
                        <span
                          className={`h-1 w-1 rounded-full ${
                            isSelected ? 'bg-white' : 'bg-green-500'
                          }`}
                        />
                      )}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Legend */}
          <div className="mt-3 flex items-center justify-center gap-4 text-xs text-gray-400 dark:text-gray-500">
            <span className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-gray-400 dark:bg-gray-500" />
              Workout
            </span>
            <span className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
              Logged
            </span>
          </div>
        </>
      )}

      {/* Selected day details */}
      {selectedDate && (
        <div className="mt-4 rounded-xl bg-gray-50 p-4 dark:bg-gray-900">
          <h3 className="mb-2 text-sm font-bold text-gray-900 dark:text-gray-100">
            {format(new Date(selectedDate + 'T12:00:00'), 'EEEE, MMMM d')}
          </h3>

          {detailLoading && <LoadingSpinner size={24} />}

          {!detailLoading && !selectedWorkout && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              No workout found for this day.
            </p>
          )}

          {!detailLoading && selectedWorkout && (
            <>
              {/* Tracks summary */}
              {selectedWorkout.tracks.map((track) => (
                <div key={track.id} className="mb-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">
                    {track.track_type.replace(/_/g, ' ')}
                  </p>
                  {track.blocks.map((block) => (
                    <div key={block.id} className="mt-1">
                      {block.exercises.map((ex) => (
                        <p
                          key={ex.id}
                          className="text-sm text-gray-700 dark:text-gray-300"
                        >
                          {ex.movement?.name ?? 'Exercise'}
                          {ex.sets ? ` - ${ex.sets}x${ex.reps_min ?? ''}` : ''}
                        </p>
                      ))}
                      {block.conditioning_workouts.map((cw) => (
                        <p
                          key={cw.id}
                          className="text-sm text-gray-700 dark:text-gray-300"
                        >
                          {cw.benchmark_name ?? cw.format} conditioning
                        </p>
                      ))}
                    </div>
                  ))}
                </div>
              ))}

              {/* User results summary */}
              {selectedLog && (
                <div className="mt-3 border-t border-gray-200 pt-3 dark:border-gray-700">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-green-500">
                    Your Results
                  </p>
                  {selectedLog.exercise_results.map((r) => (
                    <p
                      key={r.id}
                      className="text-sm text-gray-700 dark:text-gray-300"
                    >
                      {r.sets_completed} sets
                      {r.weight_per_set_lbs?.[0]
                        ? ` @ ${r.weight_per_set_lbs[0]}lbs`
                        : r.weight_per_set_kg?.[0]
                          ? ` @ ${r.weight_per_set_kg[0]}kg`
                          : ''}
                      {r.reps_per_set?.length
                        ? ` x ${r.reps_per_set.join(',')}`
                        : ''}
                      {r.rpe_actual ? ` RPE ${r.rpe_actual}` : ''}
                    </p>
                  ))}
                  {selectedLog.conditioning_results.map((r) => (
                    <p
                      key={r.id}
                      className="text-sm text-gray-700 dark:text-gray-300"
                    >
                      {r.rounds_completed != null && `${r.rounds_completed} rounds`}
                      {r.reps_completed != null && ` + ${r.reps_completed} reps`}
                      {r.time_seconds != null &&
                        ` ${Math.floor(r.time_seconds / 60)}:${String(r.time_seconds % 60).padStart(2, '0')}`}
                      {r.notes ? ` - ${r.notes}` : ''}
                    </p>
                  ))}
                  {selectedLog.completed && (
                    <span className="mt-1 inline-block rounded-full bg-green-500/15 px-2 py-0.5 text-xs font-medium text-green-500">
                      Completed
                    </span>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
