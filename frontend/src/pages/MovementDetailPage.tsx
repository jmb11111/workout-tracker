import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { ArrowLeft, ChevronDown } from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { getMovementHistory, getMovementStats } from '../api/client';
import type {
  MovementHistoryResponse,
  MovementStatsResponse,
  MovementHistoryEntry,
} from '../types';
import PRBadge from '../components/PRBadge';
import LoadingSpinner from '../components/LoadingSpinner';

export default function MovementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const movementId = parseInt(id || '0');

  const [historyData, setHistoryData] = useState<MovementHistoryResponse | null>(null);
  const [stats, setStats] = useState<MovementStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [allHistory, setAllHistory] = useState<MovementHistoryEntry[]>([]);
  const [hasMore, setHasMore] = useState(true);
  const [activeSection, setActiveSection] = useState<'prs' | 'history' | 'charts'>('prs');

  const fetchData = useCallback(async () => {
    if (!movementId) return;
    setLoading(true);
    try {
      const [histResp, statsResp] = await Promise.all([
        getMovementHistory(movementId, 1, 20),
        getMovementStats(movementId),
      ]);
      setHistoryData(histResp);
      setStats(statsResp);
      setAllHistory(histResp.history);
      setHasMore(histResp.history.length < histResp.total);
      setPage(1);
    } catch {
      setHistoryData(null);
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, [movementId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const loadMore = async () => {
    const nextPage = page + 1;
    try {
      const resp = await getMovementHistory(movementId, nextPage, 20);
      setAllHistory((prev) => [...prev, ...resp.history]);
      setHasMore(allHistory.length + resp.history.length < resp.total);
      setPage(nextPage);
    } catch {
      // ignore
    }
  };

  const movement = historyData?.movement ?? stats?.movement;

  // Prepare chart data
  const weightOverTime = (stats?.volume_over_time ?? []).map((d) => ({
    date: format(new Date(d.date), 'MMM d'),
    weight: d.max_weight,
  }));

  const volumeOverTime = (stats?.volume_over_time ?? []).map((d) => ({
    date: format(new Date(d.date), 'MMM d'),
    volume: d.volume,
  }));

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner message="Loading movement..." />
      </div>
    );
  }

  if (!movement) {
    return (
      <div className="mx-auto max-w-lg px-4 pt-4">
        <button
          onClick={() => navigate(-1)}
          className="mb-4 flex min-h-[40px] items-center gap-1 text-sm text-gray-500 dark:text-gray-400"
        >
          <ArrowLeft size={18} />
          Back
        </button>
        <p className="text-center text-sm text-gray-500 dark:text-gray-400">
          Movement not found.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 pt-4 pb-6">
      {/* Header */}
      <button
        onClick={() => navigate(-1)}
        className="mb-2 flex min-h-[40px] items-center gap-1 text-sm text-gray-500 dark:text-gray-400"
      >
        <ArrowLeft size={18} />
        Back
      </button>

      <div className="mb-4">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
          {movement.name}
        </h1>
        <div className="mt-1 flex gap-1.5">
          <span className="rounded-md bg-gray-200 px-1.5 py-0.5 text-xs text-gray-500 dark:bg-gray-700 dark:text-gray-400">
            {movement.movement_type}
          </span>
          {movement.muscle_groups.map((mg) => (
            <span
              key={mg}
              className="rounded-md bg-blue-500/10 px-1.5 py-0.5 text-xs text-blue-500"
            >
              {mg}
            </span>
          ))}
        </div>
      </div>

      {/* Section tabs */}
      <div className="mb-4 flex gap-1 rounded-xl bg-gray-100 p-1 dark:bg-gray-800">
        {(['prs', 'history', 'charts'] as const).map((section) => (
          <button
            key={section}
            onClick={() => setActiveSection(section)}
            className={`min-h-[36px] flex-1 rounded-lg px-2 py-1.5 text-xs font-semibold capitalize transition-colors ${
              activeSection === section
                ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-gray-100'
                : 'text-gray-500 dark:text-gray-400'
            }`}
          >
            {section === 'prs' ? 'PRs' : section}
          </button>
        ))}
      </div>

      {/* PRs Section */}
      {activeSection === 'prs' && stats && (
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: '1RM', value: stats.best_1rm },
            { label: '3RM', value: stats.best_3rm },
            { label: '5RM', value: stats.best_5rm },
          ].map(
            ({ label, value }) =>
              value != null && (
                <div
                  key={label}
                  className="rounded-xl bg-gray-50 px-3 py-3 text-center dark:bg-gray-900"
                >
                  <p className="text-xs font-medium text-gray-400 dark:text-gray-500">
                    {label}
                  </p>
                  <p className="mt-1 text-xl font-bold text-gray-900 dark:text-gray-100">
                    {value}
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-500">lbs</p>
                </div>
              ),
          )}
          <div className="rounded-xl bg-gray-50 px-3 py-3 text-center dark:bg-gray-900">
            <p className="text-xs font-medium text-gray-400 dark:text-gray-500">
              Sessions
            </p>
            <p className="mt-1 text-xl font-bold text-gray-900 dark:text-gray-100">
              {stats.total_sessions}
            </p>
          </div>
        </div>
      )}

      {activeSection === 'prs' && !stats?.best_1rm && !stats?.best_3rm && !stats?.best_5rm && (
        <div className="rounded-xl bg-gray-50 px-4 py-8 text-center dark:bg-gray-900">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            No PRs recorded yet for this movement.
          </p>
        </div>
      )}

      {/* History Section */}
      {activeSection === 'history' && (
        <div className="space-y-2">
          {allHistory.length === 0 && (
            <div className="rounded-xl bg-gray-50 px-4 py-8 text-center dark:bg-gray-900">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No history found.
              </p>
            </div>
          )}

          {allHistory.map((entry) => {
            const weights = entry.weight_per_set_lbs ?? entry.weight_per_set_kg ?? [];
            const reps = entry.reps_per_set ?? [];
            const maxWeight = weights.length ? Math.max(...weights) : null;
            const unit = entry.weight_per_set_lbs?.length ? 'lbs' : 'kg';

            return (
              <div
                key={entry.exercise_result_id}
                className="rounded-xl bg-gray-50 px-4 py-3 dark:bg-gray-900"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-400 dark:text-gray-500">
                    {format(new Date(entry.date), 'MMM d, yyyy')}
                  </span>
                  <div className="flex items-center gap-2">
                    {entry.rpe_actual && (
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        RPE {entry.rpe_actual}
                      </span>
                    )}
                    {entry.is_pr && <PRBadge />}
                  </div>
                </div>
                <div className="mt-1">
                  {maxWeight != null && (
                    <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
                      {maxWeight}{unit}
                    </span>
                  )}
                  {reps.length > 0 && (
                    <span className="ml-1 text-sm text-gray-600 dark:text-gray-300">
                      x {reps.join(', ')}
                    </span>
                  )}
                  {entry.sets_completed && (
                    <span className="ml-1 text-xs text-gray-400 dark:text-gray-500">
                      ({entry.sets_completed} sets)
                    </span>
                  )}
                </div>
                {entry.notes && (
                  <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                    {entry.notes}
                  </p>
                )}
              </div>
            );
          })}

          {hasMore && (
            <button
              onClick={loadMore}
              className="flex min-h-[44px] w-full items-center justify-center gap-1 rounded-xl bg-gray-100 text-sm font-medium text-gray-500 transition-colors active:bg-gray-200 dark:bg-gray-800 dark:text-gray-400"
            >
              <ChevronDown size={16} />
              Load more
            </button>
          )}
        </div>
      )}

      {/* Charts Section */}
      {activeSection === 'charts' && (
        <div className="space-y-6">
          {weightOverTime.length === 0 && (
            <div className="rounded-xl bg-gray-50 px-4 py-8 text-center dark:bg-gray-900">
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Not enough data to display charts.
              </p>
            </div>
          )}

          {weightOverTime.length > 0 && (
            <>
              {/* Weight over time */}
              <div>
                <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                  Weight Over Time
                </h3>
                <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900">
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={weightOverTime}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 10, fill: '#9ca3af' }}
                        axisLine={{ stroke: '#374151' }}
                      />
                      <YAxis
                        tick={{ fontSize: 10, fill: '#9ca3af' }}
                        axisLine={{ stroke: '#374151' }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1f2937',
                          border: 'none',
                          borderRadius: '8px',
                          fontSize: '12px',
                          color: '#f3f4f6',
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="weight"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        dot={{ r: 3, fill: '#3b82f6' }}
                        activeDot={{ r: 5 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Volume over time */}
              <div>
                <h3 className="mb-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                  Volume Over Time
                </h3>
                <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900">
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={volumeOverTime}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 10, fill: '#9ca3af' }}
                        axisLine={{ stroke: '#374151' }}
                      />
                      <YAxis
                        tick={{ fontSize: 10, fill: '#9ca3af' }}
                        axisLine={{ stroke: '#374151' }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1f2937',
                          border: 'none',
                          borderRadius: '8px',
                          fontSize: '12px',
                          color: '#f3f4f6',
                        }}
                      />
                      <Bar dataKey="volume" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
