// MetricCard — Clean, dense, unbloated KPI card for financial operations

import React, { useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Info } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  secondaryLine?: string;
  description?: string;
  icon?: LucideIcon;
  trend?: 'up' | 'down' | 'neutral';
  trendLabel?: string;
  accent?: 'default' | 'green' | 'amber' | 'red' | 'cyan';
  loading?: boolean;
  tooltip?: string;
}

const DOT_COLORS: Record<string, string> = {
  default: 'bg-slate-500',
  cyan: 'bg-cyan-400',
  green: 'bg-emerald-400',
  amber: 'bg-amber-400',
  red: 'bg-red-400',
};

export function MetricCard({
  label,
  value,
  subValue,
  secondaryLine,
  description,
  accent = 'default',
  loading,
  tooltip,
}: MetricCardProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const dotColor = DOT_COLORS[accent] ?? DOT_COLORS.default;

  return (
    <div
      className="relative bg-slate-900/80 border border-slate-800/90 hover:border-slate-700/80 rounded-xl p-4 sm:p-5 flex flex-col justify-between transition-all duration-150 hover:-translate-y-0.5 shadow-sm min-w-0"
    >
      {/* Header: Label with tiny semantic indicator dot and tooltip */}
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColor}`} />
          <span className="text-[11px] font-medium text-slate-400 tracking-wider uppercase leading-none truncate">
            {label}
          </span>
        </div>

        {tooltip && (
          <div
            className="relative inline-flex flex-shrink-0"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            <Info
              size={12}
              className="text-slate-600 hover:text-slate-400 cursor-help transition-colors"
            />
            {showTooltip && (
              <div className="absolute right-0 top-full mt-1.5 z-50 w-60 p-2.5 bg-slate-900 border border-slate-700 rounded-lg shadow-xl text-[11px] font-normal normal-case text-slate-200 leading-relaxed pointer-events-none">
                {tooltip}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Value Row */}
      <div className="my-auto py-0.5">
        {loading ? (
          <div className="h-7 bg-slate-800/80 rounded animate-pulse w-24 my-1" />
        ) : (
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl sm:text-[28px] font-bold text-slate-100 tracking-tight font-mono tabular-nums leading-none">
                {value}
              </span>
              {subValue && (
                <span className="text-xs text-slate-400 font-medium leading-none">{subValue}</span>
              )}
            </div>
            {secondaryLine && (
              <div className="text-[11px] text-slate-500 font-mono mt-1.5 leading-none">
                {secondaryLine}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Description / Contextual Line */}
      {description && (
        <div className="pt-3 mt-2 border-t border-slate-800/60 text-[11px] text-slate-400 font-normal truncate">
          {description}
        </div>
      )}
    </div>
  );
}
