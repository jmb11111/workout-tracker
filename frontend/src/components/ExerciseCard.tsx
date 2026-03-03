import { useNavigate } from 'react-router-dom';
import { Clock, Gauge, Percent } from 'lucide-react';
import type { Exercise } from '../types';
import PRBadge from './PRBadge';

interface ExerciseCardProps {
  exercise: Exercise;
  weightUnit: 'lbs' | 'kg';
  completed?: boolean;
  onTap?: () => void;
}

function formatLastResult(exercise: Exercise, unit: 'lbs' | 'kg'): string | null {
  const r = exercise.last_result;
  if (!r) return null;

  const weights = unit === 'lbs' ? r.weight_per_set_lbs : r.weight_per_set_kg;
  const reps = r.reps_per_set;

  if (!weights?.length && !reps?.length) return null;

  const parts: string[] = [];
  if (weights?.length) {
    const maxWeight = Math.max(...weights);
    parts.push(`${maxWeight}${unit}`);
  }
  if (reps?.length) {
    parts.push(reps.join(','));
  }

  return parts.join(' x ');
}

export default function ExerciseCard({ exercise, weightUnit, completed, onTap }: ExerciseCardProps) {
  const navigate = useNavigate();
  const movementName = exercise.movement?.name ?? 'Unknown Movement';
  const lastResultText = formatLastResult(exercise, weightUnit);

  const badges: { label: string; icon?: React.ReactNode }[] = [];

  // Sets x Reps
  if (exercise.sets) {
    let repText = '';
    if (exercise.reps_min && exercise.reps_max && exercise.reps_min !== exercise.reps_max) {
      repText = `${exercise.reps_min}-${exercise.reps_max}`;
    } else if (exercise.reps_min) {
      repText = `${exercise.reps_min}`;
    } else if (exercise.duration_seconds) {
      repText = `${exercise.duration_seconds}s`;
    }
    if (repText) {
      badges.push({ label: `${exercise.sets}x${repText}` });
    } else {
      badges.push({ label: `${exercise.sets} sets` });
    }
  }

  // Tempo
  if (exercise.tempo) {
    badges.push({ label: exercise.tempo, icon: <Clock size={12} /> });
  }

  // RPE
  if (exercise.rpe_min || exercise.rpe_max) {
    const rpeText = exercise.rpe_min && exercise.rpe_max && exercise.rpe_min !== exercise.rpe_max
      ? `RPE ${exercise.rpe_min}-${exercise.rpe_max}`
      : `RPE ${exercise.rpe_max ?? exercise.rpe_min}`;
    badges.push({ label: rpeText, icon: <Gauge size={12} /> });
  }

  // %1RM
  if (exercise.percent_1rm_min || exercise.percent_1rm_max) {
    const pctText = exercise.percent_1rm_min && exercise.percent_1rm_max && exercise.percent_1rm_min !== exercise.percent_1rm_max
      ? `${exercise.percent_1rm_min}-${exercise.percent_1rm_max}%`
      : `${exercise.percent_1rm_max ?? exercise.percent_1rm_min}%`;
    badges.push({ label: pctText, icon: <Percent size={12} /> });
  }

  return (
    <div
      className={`rounded-lg px-3 py-2.5 transition-colors ${
        completed
          ? 'bg-green-500/10 dark:bg-green-500/10'
          : 'bg-gray-50 dark:bg-gray-800/50'
      }`}
      onClick={onTap}
      role={onTap ? 'button' : undefined}
      tabIndex={onTap ? 0 : undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className={`text-sm font-semibold ${
          completed
            ? 'text-green-600 dark:text-green-400'
            : 'text-gray-900 dark:text-gray-100'
        }`}>
          {movementName}
          {exercise.is_alternative && (
            <span className="ml-1.5 text-xs font-normal text-gray-400 dark:text-gray-500">
              (alt)
            </span>
          )}
        </h4>
        {completed && (
          <span className="checkmark-animate mt-0.5 text-green-500">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3 8.5L6.5 12L13 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        )}
        {exercise.last_result?.is_pr && <PRBadge />}
      </div>

      {/* Badges */}
      {badges.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {badges.map((badge, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-md bg-gray-200/70 px-1.5 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300"
            >
              {badge.icon}
              {badge.label}
            </span>
          ))}
        </div>
      )}

      {/* Notes */}
      {exercise.notes && (
        <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
          {exercise.notes}
        </p>
      )}

      {/* Last result chip */}
      {lastResultText && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (exercise.movement_id) {
              navigate(`/movement/${exercise.movement_id}`);
            }
          }}
          className="mt-2 inline-flex min-h-[32px] items-center gap-1 rounded-full bg-blue-500/10 px-2.5 py-1 text-xs font-medium text-blue-500 transition-colors active:bg-blue-500/20"
        >
          Last: {lastResultText}
        </button>
      )}
    </div>
  );
}
