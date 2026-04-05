import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { WorkoutBlock, ExerciseResult, ConditioningResult } from '../types';
import ExerciseCard from './ExerciseCard';

interface BlockCardProps {
  block: WorkoutBlock;
  weightUnit: 'lbs' | 'kg';
  exerciseResults: ExerciseResult[];
  conditioningResults: ConditioningResult[];
  onExerciseTap?: (exerciseId: number) => void;
  onConditioningTap?: (conditioningId: number) => void;
  onBlockConditioningTap?: () => void;
}

function isConditioningBlock(type: string): boolean {
  return type.startsWith('conditioning');
}

function blockTypeLabel(type: string): string {
  if (isConditioningBlock(type)) return 'Conditioning';
  const map: Record<string, string> = {
    strength: 'Strength',
    warmup: 'Warm-up',
    cooldown: 'Cool-down',
    accessory: 'Accessory',
    skill: 'Skill',
    mixed: 'Mixed',
    pump: 'Pump',
  };
  return map[type] || type.charAt(0).toUpperCase() + type.slice(1);
}

function blockTypeBadgeColor(type: string): string {
  if (isConditioningBlock(type)) return 'bg-orange-500/15 text-orange-500';
  const map: Record<string, string> = {
    strength: 'bg-blue-500/15 text-blue-500',
    warmup: 'bg-yellow-500/15 text-yellow-600 dark:text-yellow-400',
    cooldown: 'bg-cyan-500/15 text-cyan-500',
    accessory: 'bg-purple-500/15 text-purple-500',
    skill: 'bg-emerald-500/15 text-emerald-500',
    mixed: 'bg-gray-500/15 text-gray-500',
    pump: 'bg-pink-500/15 text-pink-500',
  };
  return map[type] || 'bg-gray-500/15 text-gray-500';
}

function conditioningFormatLabel(format: string): string {
  const map: Record<string, string> = {
    emom: 'EMOM',
    amrap: 'AMRAP',
    for_time: 'For Time',
    interval: 'Intervals',
    tabata: 'Tabata',
  };
  return map[format] || format.toUpperCase();
}

export default function BlockCard({
  block,
  weightUnit,
  exerciseResults,
  conditioningResults,
  onExerciseTap,
  onConditioningTap,
  onBlockConditioningTap,
}: BlockCardProps) {
  const [showRawText, setShowRawText] = useState(false);

  const isConditioning = isConditioningBlock(block.block_type);

  // Check if this conditioning block has been logged
  const blockConditioningLogged = conditioningResults.some(
    (r) => block.conditioning_workouts.some((cw) => cw.id === r.conditioning_workout_id),
  );

  // Determine if block has option groups (alternatives)
  const alternativeGroups = new Map<number, typeof block.exercises>();
  const regularExercises: typeof block.exercises = [];

  for (const ex of block.exercises) {
    if (ex.alternative_group_id !== null && ex.alternative_group_id !== undefined) {
      const group = alternativeGroups.get(ex.alternative_group_id) || [];
      group.push(ex);
      alternativeGroups.set(ex.alternative_group_id, group);
    } else {
      regularExercises.push(ex);
    }
  }

  const [selectedOptions, setSelectedOptions] = useState<Record<number, number>>(() => {
    const defaults: Record<number, number> = {};
    alternativeGroups.forEach((exercises, groupId) => {
      if (exercises.length > 0) {
        defaults[groupId] = 0;
      }
    });
    return defaults;
  });

  const completedExerciseIds = new Set(exerciseResults.map((r) => r.exercise_id));

  return (
    <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900">
      {/* Header */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {block.label && (
          <span className="flex h-7 shrink-0 items-center justify-center rounded-lg bg-gray-200 px-2 text-xs font-bold text-gray-700 dark:bg-gray-700 dark:text-gray-200">
            {block.label}
          </span>
        )}
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${blockTypeBadgeColor(block.block_type)}`}
        >
          {blockTypeLabel(block.block_type)}
        </span>
        {/* Conditioning format sub-badge */}
        {isConditioning && block.conditioning_workouts.length > 0 && (
          <span className="rounded-full bg-orange-500/10 px-1.5 py-0.5 text-xs font-medium text-orange-400">
            {conditioningFormatLabel(block.conditioning_workouts[0].format)}
            {block.conditioning_workouts[0].duration_minutes
              ? ` ${block.conditioning_workouts[0].duration_minutes}min`
              : ''}
          </span>
        )}
        {/* Conditioning completed check */}
        {isConditioning && blockConditioningLogged && (
          <span className="checkmark-animate text-green-500">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3 8.5L6.5 12L13 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
        )}
      </div>

      {/* Conditioning blocks: show raw_text as the description */}
      {isConditioning && (
        <div
          className={`rounded-lg px-3 py-2.5 ${
            blockConditioningLogged
              ? 'bg-green-500/10'
              : 'bg-gray-50 dark:bg-gray-800/50'
          }`}
          onClick={
            onBlockConditioningTap
              ? onBlockConditioningTap
              : onConditioningTap && block.conditioning_workouts[0]
                ? () => onConditioningTap(block.conditioning_workouts[0].id)
                : undefined
          }
          role={onBlockConditioningTap || onConditioningTap ? 'button' : undefined}
          tabIndex={onBlockConditioningTap || onConditioningTap ? 0 : undefined}
        >
          {block.conditioning_workouts[0]?.is_partner && (
            <span className="mb-2 inline-block rounded-full bg-purple-500/15 px-1.5 py-0.5 text-xs font-medium text-purple-500">
              Partner
            </span>
          )}
          {block.raw_text && (
            <pre className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700 dark:text-gray-300 font-sans">
              {block.raw_text}
            </pre>
          )}
        </div>
      )}

      {/* Non-conditioning blocks: show individual exercises */}
      {!isConditioning && (
        <>
          {/* Regular exercises */}
          <div className="space-y-2">
            {regularExercises
              .sort((a, b) => a.display_order - b.display_order)
              .map((exercise) => (
                <ExerciseCard
                  key={exercise.id}
                  exercise={exercise}
                  weightUnit={weightUnit}
                  completed={completedExerciseIds.has(exercise.id)}
                  onTap={onExerciseTap ? () => onExerciseTap(exercise.id) : undefined}
                />
              ))}
          </div>

          {/* Alternative groups */}
          {Array.from(alternativeGroups.entries()).map(([groupId, exercises]) => (
            <div key={groupId} className="mt-3">
              {/* Option selector */}
              <div className="mb-2 flex gap-1">
                {exercises.map((ex, idx) => (
                  <button
                    key={ex.id}
                    onClick={() =>
                      setSelectedOptions((prev) => ({ ...prev, [groupId]: idx }))
                    }
                    className={`min-h-[36px] rounded-lg px-3 py-1 text-xs font-medium transition-colors ${
                      selectedOptions[groupId] === idx
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                    }`}
                  >
                    Option {idx + 1}
                  </button>
                ))}
              </div>
              {/* Selected option */}
              {exercises[selectedOptions[groupId]] && (
                <ExerciseCard
                  exercise={exercises[selectedOptions[groupId]]}
                  weightUnit={weightUnit}
                  completed={completedExerciseIds.has(exercises[selectedOptions[groupId]].id)}
                  onTap={
                    onExerciseTap
                      ? () => onExerciseTap(exercises[selectedOptions[groupId]].id)
                      : undefined
                  }
                />
              )}
            </div>
          ))}
        </>
      )}

      {/* Raw text toggle (only for non-conditioning blocks that have raw_text) */}
      {!isConditioning && block.raw_text && (
        <div className="mt-3 border-t border-gray-200 pt-2 dark:border-gray-700">
          <button
            onClick={() => setShowRawText(!showRawText)}
            className="flex min-h-[36px] items-center gap-1 text-xs text-gray-400 transition-colors active:text-gray-600 dark:text-gray-500"
          >
            {showRawText ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            Raw text
          </button>
          {showRawText && (
            <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded-md bg-gray-100 p-2 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400">
              {block.raw_text}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
