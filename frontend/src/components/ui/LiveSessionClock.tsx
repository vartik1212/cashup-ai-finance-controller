// LiveSessionClock — Real-time high-precision financial session clock
// Updates every second with local time and current date; zero page refresh required.

import React, { useState, useEffect } from 'react';
import { Clock } from 'lucide-react';

export function LiveSessionClock() {
  const [now, setNow] = useState<Date>(new Date());

  useEffect(() => {
    // Synchronize to the nearest second
    const timer = setInterval(() => {
      setNow(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  // Format time (HH:MM:SS AM/PM or locale 24h)
  const timeString = now.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });

  // Format date (e.g. Sat, Sep 5, 2026)
  const dateString = now.toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div
      className="flex items-center gap-2.5 px-2.5 py-1 bg-slate-900/90 border border-slate-700/60 rounded-lg text-xs shadow-inner select-none transition-colors flex-shrink-0"
      title="Live Controller Session Time (updates every second)"
    >
      {/* Live heartbeat indicator */}
      <span className="relative flex h-2 w-2 flex-shrink-0">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
      </span>

      <Clock size={12} className="text-slate-400 flex-shrink-0" />

      {/* Date - visible on 2xl screens to avoid header crowding */}
      <span className="text-[11px] text-slate-400 font-medium hidden 2xl:inline">
        {dateString}
      </span>

      <span className="text-slate-700 hidden 2xl:inline">|</span>

      {/* Real-time seconds clock */}
      <span className="font-mono text-xs font-semibold text-slate-200 tracking-wider">
        {timeString}
      </span>
    </div>
  );
}
