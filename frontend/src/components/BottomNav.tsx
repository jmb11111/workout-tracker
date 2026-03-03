import { NavLink } from 'react-router-dom';
import {
  Home,
  Calendar,
  Trophy,
  Search,
  UserCircle,
} from 'lucide-react';

const navItems = [
  { to: '/', icon: Home, label: 'Today' },
  { to: '/history', icon: Calendar, label: 'History' },
  { to: '/records', icon: Trophy, label: 'Records' },
  { to: '/search', icon: Search, label: 'Search' },
  { to: '/profile', icon: UserCircle, label: 'Profile' },
];

export default function BottomNav() {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950"
      style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
    >
      <div className="mx-auto flex max-w-lg items-center justify-around">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex min-h-[44px] min-w-[44px] flex-col items-center justify-center gap-0.5 px-3 py-2 text-xs transition-colors ${
                isActive
                  ? 'text-blue-500'
                  : 'text-gray-500 dark:text-gray-400'
              }`
            }
          >
            <Icon size={22} />
            <span>{label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
