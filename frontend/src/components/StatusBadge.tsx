import React from 'react';
import { PublishingStatus, ApprovalStatus } from '../types';

interface StatusBadgeProps {
  status: PublishingStatus | ApprovalStatus | string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const configs: Record<string, { label: string; bg: string; text: string; dot: string }> = {
    scheduled: { label: 'Scheduled', bg: 'bg-blue-500/10 border-blue-500/30', text: 'text-blue-400', dot: 'bg-blue-400' },
    publishing: { label: 'Publishing...', bg: 'bg-amber-500/10 border-amber-500/30', text: 'text-amber-400', dot: 'bg-amber-400 animate-pulse' },
    published: { label: 'Published', bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400', dot: 'bg-emerald-400' },
    failed: { label: 'Failed', bg: 'bg-red-500/10 border-red-500/30', text: 'text-red-400', dot: 'bg-red-400' },
    cancelled: { label: 'Cancelled', bg: 'bg-slate-500/10 border-slate-500/30', text: 'text-slate-400', dot: 'bg-slate-400' },
    pending: { label: 'Pending', bg: 'bg-slate-500/10 border-slate-500/30', text: 'text-slate-300', dot: 'bg-slate-400' },
    approved: { label: 'Approved', bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400', dot: 'bg-emerald-400' },
    rejected: { label: 'Rejected', bg: 'bg-rose-500/10 border-rose-500/30', text: 'text-rose-400', dot: 'bg-rose-400' },
    pending_approval: { label: 'Awaiting Review', bg: 'bg-amber-500/10 border-amber-500/30', text: 'text-amber-300', dot: 'bg-amber-400' },
    ready: { label: 'Ready', bg: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400', dot: 'bg-emerald-400' },
    processing: { label: 'Processing...', bg: 'bg-indigo-500/10 border-indigo-500/30', text: 'text-indigo-400', dot: 'bg-indigo-400 animate-pulse' },
  };

  const c = configs[status.toLowerCase()] || { label: status, bg: 'bg-slate-800 border-slate-700', text: 'text-slate-400', dot: 'bg-slate-400' };

  return (
    <span className={`inline-flex items-center text-xs px-2.5 py-0.5 rounded-full border ${c.bg} ${c.text} font-medium`}>
      <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${c.dot}`} />
      {c.label}
    </span>
  );
};
