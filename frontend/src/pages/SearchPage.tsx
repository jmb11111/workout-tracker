import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { getMovements } from '../api/client';
import type { Movement } from '../types';
import LoadingSpinner from '../components/LoadingSpinner';

const MOVEMENT_TYPES = [
  'barbell',
  'dumbbell',
  'kettlebell',
  'machine',
  'cable',
  'bodyweight',
  'cardio',
  'other',
];

export default function SearchPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [movements, setMovements] = useState<Movement[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  // Autofocus on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const search = useCallback(async () => {
    if (!query && !typeFilter) {
      setMovements([]);
      setSearched(false);
      return;
    }
    setLoading(true);
    setSearched(true);
    try {
      const params: { q?: string; movement_type?: string } = {};
      if (query) params.q = query;
      if (typeFilter) params.movement_type = typeFilter;
      const data = await getMovements(params);
      setMovements(data);
    } catch {
      setMovements([]);
    } finally {
      setLoading(false);
    }
  }, [query, typeFilter]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(search, 300);
    return () => clearTimeout(timer);
  }, [search]);

  return (
    <div className="mx-auto max-w-lg px-4 pt-4">
      {/* Search input */}
      <div className="relative mb-3">
        <Search
          size={18}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500"
        />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search movements..."
          className="h-12 w-full rounded-xl bg-gray-100 pl-10 pr-10 text-base text-gray-900 outline-none ring-1 ring-transparent focus:ring-blue-500 dark:bg-gray-800 dark:text-gray-100"
        />
        {query && (
          <button
            onClick={() => setQuery('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 active:text-gray-600 dark:text-gray-500"
          >
            <X size={18} />
          </button>
        )}
      </div>

      {/* Type filter chips */}
      <div className="mb-4 flex gap-1.5 overflow-x-auto pb-1">
        {MOVEMENT_TYPES.map((type) => (
          <button
            key={type}
            onClick={() => setTypeFilter(typeFilter === type ? '' : type)}
            className={`min-h-[32px] shrink-0 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              typeFilter === type
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
            }`}
          >
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </button>
        ))}
      </div>

      {/* Results */}
      {loading && (
        <div className="flex justify-center py-10">
          <LoadingSpinner size={24} />
        </div>
      )}

      {!loading && searched && movements.length === 0 && (
        <div className="rounded-xl bg-gray-50 px-4 py-12 text-center dark:bg-gray-900">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            No movements found.
          </p>
        </div>
      )}

      {!loading && movements.length > 0 && (
        <div className="space-y-1.5 pb-6">
          {movements.map((movement) => (
            <button
              key={movement.id}
              onClick={() => navigate(`/movement/${movement.id}`)}
              className="flex min-h-[52px] w-full items-center gap-3 rounded-xl bg-gray-50 px-4 py-3 text-left transition-colors active:bg-gray-100 dark:bg-gray-900 dark:active:bg-gray-800"
            >
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                  {movement.name}
                </p>
                <div className="mt-0.5 flex flex-wrap gap-1">
                  <span className="rounded-md bg-gray-200 px-1.5 py-0.5 text-xs text-gray-500 dark:bg-gray-700 dark:text-gray-400">
                    {movement.movement_type}
                  </span>
                  {movement.muscle_groups.slice(0, 3).map((mg) => (
                    <span
                      key={mg}
                      className="rounded-md bg-blue-500/10 px-1.5 py-0.5 text-xs text-blue-500"
                    >
                      {mg}
                    </span>
                  ))}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Initial empty state */}
      {!loading && !searched && (
        <div className="px-4 py-12 text-center">
          <Search size={40} className="mx-auto mb-3 text-gray-300 dark:text-gray-600" />
          <p className="text-sm text-gray-400 dark:text-gray-500">
            Search for a movement to see its history and records.
          </p>
        </div>
      )}
    </div>
  );
}
