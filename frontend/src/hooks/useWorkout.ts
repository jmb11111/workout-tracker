import { useState, useEffect, useCallback } from 'react';
import { getToday, getWorkout } from '../api/client';
import type { WorkoutDay } from '../types';

interface UseWorkoutReturn {
  workout: WorkoutDay | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  loadDate: (date: string) => void;
  currentDate: string;
}

export function useWorkout(): UseWorkoutReturn {
  const [workout, setWorkout] = useState<WorkoutDay | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentDate, setCurrentDate] = useState(() => {
    const now = new Date();
    return now.toISOString().split('T')[0];
  });

  const fetchWorkout = useCallback(async (date?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = date ? await getWorkout(date) : await getToday();
      setWorkout(data);
      if (data?.date) {
        setCurrentDate(data.date);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load workout';
      setError(message);
      setWorkout(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkout();
  }, [fetchWorkout]);

  const refresh = useCallback(() => {
    fetchWorkout(currentDate);
  }, [fetchWorkout, currentDate]);

  const loadDate = useCallback(
    (date: string) => {
      setCurrentDate(date);
      fetchWorkout(date);
    },
    [fetchWorkout],
  );

  return { workout, loading, error, refresh, loadDate, currentDate };
}
