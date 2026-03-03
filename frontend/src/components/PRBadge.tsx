import { Trophy } from 'lucide-react';

interface PRBadgeProps {
  className?: string;
  size?: 'sm' | 'md';
}

export default function PRBadge({ className = '', size = 'sm' }: PRBadgeProps) {
  const sizeClasses = size === 'sm'
    ? 'px-1.5 py-0.5 text-xs gap-0.5'
    : 'px-2 py-1 text-sm gap-1';

  const iconSize = size === 'sm' ? 12 : 14;

  return (
    <span
      className={`inline-flex items-center font-semibold rounded-full bg-amber-400/20 text-amber-400 ${sizeClasses} ${className}`}
    >
      <Trophy size={iconSize} />
      PR
    </span>
  );
}
