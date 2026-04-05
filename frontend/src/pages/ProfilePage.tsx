import { useState, useEffect } from 'react';
import { LogOut, Moon, Sun } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useDarkMode } from '../hooks/useDarkMode';
import { getMe, updateMe } from '../api/client';
import type { User } from '../types';
import LoadingSpinner from '../components/LoadingSpinner';

export default function ProfilePage() {
  const { isAuthenticated, login, logout, loginError, loading: authLoading } = useAuth();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const { isDark, toggleDark } = useDarkMode(user);

  useEffect(() => {
    if (isAuthenticated) {
      setLoading(true);
      getMe()
        .then(setUser)
        .catch(() => setUser(null))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [isAuthenticated]);

  const handleWeightUnitChange = async (unit: 'lbs' | 'kg') => {
    try {
      const updated = await updateMe({ weight_unit: unit });
      setUser(updated);
    } catch {
      // ignore
    }
  };

  if (authLoading || loading) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner message="Loading profile..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="mx-auto max-w-lg px-4 pt-4">
        <h1 className="mb-6 text-xl font-bold text-gray-900 dark:text-gray-100">
          Profile
        </h1>
        <div className="rounded-xl bg-gray-50 px-4 py-12 text-center dark:bg-gray-900">
          <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
            Sign in to track your workouts and personal records.
          </p>
          <button
            onClick={login}
            className="min-h-[48px] rounded-xl bg-blue-500 px-8 py-3 text-sm font-semibold text-white transition-colors active:bg-blue-600"
          >
            Sign In
          </button>
          {loginError && (
            <p className="mt-4 text-sm text-amber-500">
              {loginError}
            </p>
          )}
        </div>

        {/* Dark mode toggle available without auth */}
        <div className="mt-6 rounded-xl bg-gray-50 p-4 dark:bg-gray-900">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {isDark ? (
                <Moon size={20} className="text-gray-400" />
              ) : (
                <Sun size={20} className="text-gray-400" />
              )}
              <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                Dark Mode
              </span>
            </div>
            <button
              onClick={toggleDark}
              role="switch"
              aria-checked={isDark}
              className={`relative inline-flex h-[31px] w-[51px] shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
                isDark ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-[27px] w-[27px] rounded-full bg-white shadow-md ring-0 transition-transform duration-200 ease-in-out ${
                  isDark ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg px-4 pt-4 pb-6">
      <h1 className="mb-6 text-xl font-bold text-gray-900 dark:text-gray-100">
        Profile
      </h1>

      {/* User info */}
      {user && (
        <div className="mb-4 rounded-xl bg-gray-50 p-4 dark:bg-gray-900">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-500 text-lg font-bold text-white">
              {user.display_name?.charAt(0)?.toUpperCase() ?? user.email?.charAt(0)?.toUpperCase() ?? '?'}
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                {user.display_name ?? 'User'}
              </p>
              {user.email && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {user.email}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Weight unit */}
      <div className="mb-4 rounded-xl bg-gray-50 p-4 dark:bg-gray-900">
        <p className="mb-3 text-sm font-semibold text-gray-900 dark:text-gray-100">
          Weight Unit
        </p>
        <div className="flex gap-2">
          {(['lbs', 'kg'] as const).map((unit) => (
            <button
              key={unit}
              onClick={() => handleWeightUnitChange(unit)}
              className={`min-h-[44px] flex-1 rounded-xl text-sm font-semibold transition-colors ${
                user?.weight_unit === unit
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
              }`}
            >
              {unit.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Dark mode */}
      <div className="mb-4 rounded-xl bg-gray-50 p-4 dark:bg-gray-900">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isDark ? (
              <Moon size={20} className="text-gray-400" />
            ) : (
              <Sun size={20} className="text-gray-400" />
            )}
            <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
              Dark Mode
            </span>
          </div>
          <button
            onClick={toggleDark}
            role="switch"
            aria-checked={isDark}
            className={`relative inline-flex h-[31px] w-[51px] shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out ${
              isDark ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-600'
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-[27px] w-[27px] rounded-full bg-white shadow-md ring-0 transition-transform duration-200 ease-in-out ${
                isDark ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Logout */}
      <button
        onClick={logout}
        className="flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-red-500/10 text-sm font-semibold text-red-500 transition-colors active:bg-red-500/20"
      >
        <LogOut size={18} />
        Sign Out
      </button>
    </div>
  );
}
