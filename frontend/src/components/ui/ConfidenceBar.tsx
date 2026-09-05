// ConfidenceBar — visual score indicator with threshold color coding

import React from 'react';

interface ConfidenceBarProps {
  score: number;
  showLabel?: boolean;
  compact?: boolean;
}

function normalizeScore(score: number): number {
  if (score > 1) return score / 100;
  return score;
}

function getBarColor(norm: number): string {
  if (norm >= 0.85) return 'bg-emerald-500';
  if (norm >= 0.70) return 'bg-cyan-500';
  if (norm >= 0.50) return 'bg-amber-500';
  return 'bg-red-500';
}

function getTextColor(norm: number): string {
  if (norm >= 0.85) return 'text-emerald-400';
  if (norm >= 0.70) return 'text-cyan-400';
  if (norm >= 0.50) return 'text-amber-400';
  return 'text-red-400';
}

export function ConfidenceBar({ score, showLabel = true, compact = false }: ConfidenceBarProps) {
  const norm = normalizeScore(score);
  const pct = Math.round(norm * 100);
  const barColor = getBarColor(norm);
  const textColor = getTextColor(norm);
  const height = compact ? 'h-1' : 'h-1.5';

  return (
    <div className={`flex items-center gap-2 ${compact ? 'w-24' : 'w-full'}`}>
      {showLabel && (
        <span className={`text-xs font-mono font-medium w-9 text-right ${textColor}`}>
          {pct}%
        </span>
      )}
      <div className={`flex-1 bg-slate-700/60 rounded-full overflow-hidden ${height}`}>
        <div
          className={`${height} rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function TableConfidenceBar({ score }: { score: number }) {
  const norm = normalizeScore(score);
  const pct = Math.round(norm * 100);
  const textColor = getTextColor(norm);
  const barColor = getBarColor(norm);

  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <span className={`text-xs font-mono font-semibold ${textColor}`}>{pct}%</span>
      <div className="flex-1 bg-slate-700/60 rounded-full h-1.5 min-w-[40px]">
        <div className={`h-1.5 rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
