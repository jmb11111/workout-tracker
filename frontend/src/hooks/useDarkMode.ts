import { useState, useEffect, useCallback } from 'react';
import { updateMe } from '../api/client';
import type { User } from '../types';

export function useDarkMode(user: User | null) {
  const [isDark, setIsDark] = useState(() => {
    // Default to dark mode; override with user preference if available
    if (user) return user.dark_mode;
    const stored = localStorage.getItem('dark_mode');
    if (stored !== null) return stored === 'true';
    return true;
  });

  // Sync with user profile when it changes
  useEffect(() => {
    if (user) {
      setIsDark(user.dark_mode);
    }
  }, [user]);

  // Apply class to document
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('dark_mode', String(isDark));
  }, [isDark]);

  const toggleDark = useCallback(async () => {
    const newValue = !isDark;
    setIsDark(newValue);

    // Persist to backend if authenticated
    try {
      await updateMe({ dark_mode: newValue });
    } catch {
      // Silently fail — local state is already set
    }
  }, [isDark]);

  return { isDark, toggleDark };
}
