import React from 'react';
import { Platform } from '../types';

interface PlatformBadgeProps {
  platform: Platform;
  size?: 'sm' | 'md';
}

export const PlatformBadge: React.FC<PlatformBadgeProps> = ({ platform, size = 'sm' }) => {
  const configs: Record<Platform, { label: string; bg: string; text: string; border: string }> = {
    instagram: {
      label: 'Instagram',
      bg: 'bg-gradient-to-r from-pink-500/10 via-purple-500/10 to-orange-500/10',
      text: 'text-pink-400',
      border: 'border-pink-500/30'
    },
    facebook: {
      label: 'Facebook',
      bg: 'bg-blue-600/10',
      text: 'text-blue-400',
      border: 'border-blue-500/30'
    },
    youtube: {
      label: 'YouTube Shorts',
      bg: 'bg-red-600/10',
      text: 'text-red-400',
      border: 'border-red-500/30'
    }
  };

  const c = configs[platform] || { label: platform, bg: 'bg-slate-800', text: 'text-slate-300', border: 'border-slate-700' };
  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-3 py-1';

  return (
    <span className={`inline-flex items-center font-medium rounded-full border ${c.bg} ${c.text} ${c.border} ${sizeClasses}`}>
      {c.label}
    </span>
  );
};
