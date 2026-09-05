// StatusBadge — displays reconciliation status with correct color coding

import React from 'react';
import type { ReconciliationStatus, ExceptionCategory } from '../../types';

interface StatusBadgeProps {
  status: ReconciliationStatus | string;
  size?: 'sm' | 'md';
}

const STATUS_STYLES: Record<string, string> = {
  'Exact Match':    'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  'Fee Match':      'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  'Probable Match': 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  'Human Review':   'bg-amber-500/15 text-amber-400 border-amber-500/30',
  'Unresolved':     'bg-red-500/15 text-red-400 border-red-500/30',
};

const STATUS_DOTS: Record<string, string> = {
  'Exact Match':    'bg-emerald-400',
  'Fee Match':      'bg-cyan-400',
  'Probable Match': 'bg-blue-400',
  'Human Review':   'bg-amber-400',
  'Unresolved':     'bg-red-400',
};

export function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? 'bg-slate-500/15 text-slate-400 border-slate-500/30';
  const dot = STATUS_DOTS[status] ?? 'bg-slate-400';
  const sizeClass = size === 'md' ? 'px-3 py-1 text-xs' : 'px-2 py-0.5 text-[11px]';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded border font-medium tracking-wide ${style} ${sizeClass}`}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  );
}

interface ExceptionBadgeProps {
  category: ExceptionCategory | string;
  size?: 'sm' | 'md';
}

const EXCEPTION_STYLES: Record<string, string> = {
  'Missing Settlement':  'bg-red-500/15 text-red-400 border-red-500/30',
  'Amount Mismatch':     'bg-orange-500/15 text-orange-400 border-orange-500/30',
  'Duplicate':           'bg-purple-500/15 text-purple-400 border-purple-500/30',
  'Partial Payment':     'bg-amber-500/15 text-amber-400 border-amber-500/30',
  'Refund Discrepancy':  'bg-pink-500/15 text-pink-400 border-pink-500/30',
  'Ambiguous Match':     'bg-slate-500/15 text-slate-400 border-slate-500/30',
};

export function ExceptionBadge({ category, size = 'sm' }: ExceptionBadgeProps) {
  const style = EXCEPTION_STYLES[category] ?? 'bg-slate-500/15 text-slate-400 border-slate-500/30';
  const sizeClass = size === 'md' ? 'px-3 py-1 text-xs' : 'px-2 py-0.5 text-[11px]';

  return (
    <span className={`inline-flex items-center rounded border font-medium tracking-wide ${style} ${sizeClass}`}>
      {category}
    </span>
  );
}
