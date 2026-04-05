import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { Trophy, Filter } from 'lucide-react';
import { getRecords, getBenchmarks } from '../api/client';
import type { GroupedPersonalRecords, BenchmarkGroup } from '../types';
import PRBadge from '../components/PRBadge';
import LoadingSpinner from '../components/LoadingSpinner';

const RECORD_TYPE_LABELS: Record<string, string> = {
  '1rm': '1RM',
  '3rm': '3RM',
  '5rm': '5RM',
  max_reps: 'Max Reps',
  best_time: 'Best Time',
};

export default function RecordsPage() {
  const [tab, setTab] = useState<'prs' | 'benchmarks'>('prs');
  const [records, setRecords] = useState<GroupedPersonalRecords[]>([]);
  const [benchmarks, setBenchmarks] = useState<BenchmarkGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [movementType, setMovementType] = useState('');
  const [muscleGroup, setMuscleGroup] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const navigate = useNavigate();

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    try {
      const params: { movement_type?: string; muscle_group?: string } = {};
      if (movementType) params.movement_type = movementType;
      if (muscleGroup) params.muscle_group = muscleGroup;
      const data = await getRecords(params);
      setRecords(data);
    } catch {
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [movementType, muscleGroup]);

  const fetchBenchmarks = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getBenchmarks();
      setBenchmarks(data);
    } catch {
      setBenchmarks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === 'prs') {
      fetchRecords();
    } else {
      fetchBenchmarks();
    }
  }, [tab, fetchRecords, fetchBenchmarks]);

  // Collect unique types for filter dropdowns
  const movementTypes = [...new Set(records.map((r) => r.movement.movement_type).filter(Boolean))];
  const muscleGroups = [...new Set(records.flatMap((r) => r.movement.muscle_groups))];

  return (
    <div className="mx-auto max-w-lg px-4 pt-4">
      <h1 className="mb-4 text-xl font-bold text-gray-900 dark:text-gray-100">
        Records
      </h1>

      {/* Tabs */}
      <div className="mb-4 flex gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800">
        <button
          onClick={() => setTab('prs')}
          className={`min-h-[40px] flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
            tab === 'prs'
              ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-gray-100'
              : 'text-gray-500 dark:text-gray-400'
          }`}
        >
          Personal Records
        </button>
        <button
          onClick={() => setTab('benchmarks')}
          className={`min-h-[40px] flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
            tab === 'benchmarks'
              ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-gray-100'
              : 'text-gray-500 dark:text-gray-400'
          }`}
        >
          Benchmarks
        </button>
      </div>

      {/* Filters for PRs */}
      {tab === 'prs' && (
        <div className="mb-4">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex min-h-[36px] items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 transition-colors active:bg-gray-200 dark:bg-gray-800 dark:text-gray-300"
          >
            <Filter size={14} />
            Filters
            {(movementType || muscleGroup) && (
              <span className="ml-1 h-1.5 w-1.5 rounded-full bg-blue-500" />
            )}
          </button>

          {showFilters && (
            <div className="mt-2 flex gap-2">
              <select
                value={movementType}
                onChange={(e) => setMovementType(e.target.value)}
                className="h-10 flex-1 rounded-lg bg-gray-100 px-2 text-sm text-gray-700 dark:bg-gray-800 dark:text-gray-300"
              >
                <option value="">All Types</option>
                {movementTypes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <select
                value={muscleGroup}
                onChange={(e) => setMuscleGroup(e.target.value)}
                className="h-10 flex-1 rounded-lg bg-gray-100 px-2 text-sm text-gray-700 dark:bg-gray-800 dark:text-gray-300"
              >
                <option value="">All Muscles</option>
                {muscleGroups.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-10">
          <LoadingSpinner />
        </div>
      )}

      {/* Personal Records */}
      {!loading && tab === 'prs' && (
        <div className="space-y-3 pb-6">
          {records.length === 0 && (
            <div className="rounded-xl bg-gray-50 px-4 py-12 text-center dark:bg-gray-900">
              <Trophy size={32} className="mx-auto mb-2 text-gray-400 dark:text-gray-500" />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No personal records yet. Start logging workouts!
              </p>
            </div>
          )}

          {records.map((group) => (
            <div
              key={group.movement.id}
              onClick={() => navigate(`/movement/${group.movement.id}`)}
              role="button"
              tabIndex={0}
              className="cursor-pointer rounded-xl bg-gray-50 p-4 transition-colors active:bg-gray-100 dark:bg-gray-900 dark:active:bg-gray-800"
            >
              <div className="mb-2 flex items-center gap-2">
                <h3 className="text-sm font-bold text-gray-900 dark:text-gray-100">
                  {group.movement.name}
                </h3>
                <span className="rounded-md bg-gray-200 px-1.5 py-0.5 text-xs text-gray-500 dark:bg-gray-700 dark:text-gray-400">
                  {group.movement.movement_type}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {Object.entries(group.records).map(([type, record]) => (
                  <div
                    key={type}
                    className="rounded-lg bg-white px-3 py-2 dark:bg-gray-800"
                  >
                    <p className="text-xs font-medium text-gray-400 dark:text-gray-500">
                      {RECORD_TYPE_LABELS[type] ?? type}
                    </p>
                    <div className="flex items-baseline gap-1">
                      <span className="text-lg font-bold text-gray-900 dark:text-gray-100">
                        {type === 'best_time'
                          ? `${Math.floor(record.value / 60)}:${String(
                              Math.round(record.value % 60),
                            ).padStart(2, '0')}`
                          : record.value}
                      </span>
                      {type !== 'best_time' && type !== 'max_reps' && (
                        <span className="text-xs text-gray-400 dark:text-gray-500">
                          lbs
                        </span>
                      )}
                    </div>
                    {record.achieved_at && (
                      <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
                        {format(new Date(record.achieved_at), 'MMM d, yyyy')}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Benchmarks */}
      {!loading && tab === 'benchmarks' && (
        <div className="space-y-3 pb-6">
          {benchmarks.length === 0 && (
            <div className="rounded-xl bg-gray-50 px-4 py-12 text-center dark:bg-gray-900">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No benchmark workouts completed yet.
              </p>
            </div>
          )}

          {benchmarks.map((group) => (
            <div
              key={group.benchmark_name}
              className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900"
            >
              <h3 className="mb-3 text-sm font-bold text-gray-900 dark:text-gray-100">
                {group.benchmark_name}
              </h3>

              <div className="space-y-2">
                {group.attempts.map((attempt, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-lg bg-white px-3 py-2 dark:bg-gray-800"
                  >
                    <div>
                      {attempt.rounds_completed != null && (
                        <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                          {attempt.rounds_completed} rounds
                          {attempt.reps_completed
                            ? ` + ${attempt.reps_completed} reps`
                            : ''}
                        </span>
                      )}
                      {attempt.time_seconds != null && (
                        <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                          {Math.floor(attempt.time_seconds / 60)}:
                          {String(attempt.time_seconds % 60).padStart(2, '0')}
                        </span>
                      )}
                      {attempt.notes && (
                        <p className="text-xs text-gray-400 dark:text-gray-500">
                          {attempt.notes}
                        </p>
                      )}
                    </div>
                    {attempt.date && (
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        {format(new Date(attempt.date), 'MMM d')}
                      </span>
                    )}
                    {i === 0 && group.attempts.length > 1 && <PRBadge />}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
