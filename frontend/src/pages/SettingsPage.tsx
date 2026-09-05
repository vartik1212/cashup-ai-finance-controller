// Settings Page — stub for configuration

import React from 'react';
import { Settings, Key, Database, Info } from 'lucide-react';
import { useApp } from '../store/AppContext';

export function SettingsPage() {
  const { aiAvailable, dataStatus } = useApp();

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-slate-100 mb-1">Settings</h1>
        <p className="text-xs text-slate-500">System configuration and status.</p>
      </div>

      {/* AI Configuration */}
      <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-5">
        <div className="flex items-center gap-2 mb-4">
          <Key size={14} className="text-slate-400" />
          <div className="text-xs font-semibold text-slate-300 uppercase tracking-widest">AI Configuration</div>
        </div>

        <div className="space-y-3">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-sm text-slate-300 font-medium">Gemini API Key</div>
              <div className="text-xs text-slate-500 mt-0.5">
                Set GEMINI_API_KEY environment variable on the backend server.
              </div>
            </div>
            <div className={`px-2.5 py-1 rounded border text-[11px] font-medium ${
              aiAvailable
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                : 'bg-slate-700/40 border-slate-600/40 text-slate-500'
            }`}>
              {aiAvailable ? 'Configured' : 'Not set'}
            </div>
          </div>

          <div className="bg-slate-900/60 rounded p-3 font-mono text-xs text-slate-400 border border-slate-700/40">
            # .env file (backend root)<br />
            GEMINI_API_KEY=your_key_here
          </div>

          <div className="flex items-start gap-2 text-xs text-slate-500 bg-slate-900/30 border border-slate-700/30 rounded p-3">
            <Info size={12} className="mt-0.5 flex-shrink-0" />
            Without a Gemini API key, the Finance Copilot operates in data-only mode,
            providing structured answers from reconciliation data without LLM generation.
          </div>
        </div>
      </div>

      {/* Data Status */}
      <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-5">
        <div className="flex items-center gap-2 mb-4">
          <Database size={14} className="text-slate-400" />
          <div className="text-xs font-semibold text-slate-300 uppercase tracking-widest">Data Status</div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Invoices', count: dataStatus?.invoices ?? 0 },
            { label: 'Settlements', count: dataStatus?.settlements ?? 0 },
            { label: 'Bank Transactions', count: dataStatus?.bank_transactions ?? 0 },
          ].map(item => (
            <div key={item.label} className="bg-slate-900/60 rounded p-3 border border-slate-700/40">
              <div className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">{item.label}</div>
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${item.count > 0 ? 'bg-emerald-400' : 'bg-slate-600'}`} />
                <span className="text-sm font-mono font-semibold text-slate-200">{item.count}</span>
                {item.count > 0 && <span className="text-[10px] text-slate-600">records</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* About */}
      <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-5">
        <div className="flex items-center gap-2 mb-4">
          <Info size={14} className="text-slate-400" />
          <div className="text-xs font-semibold text-slate-300 uppercase tracking-widest">About</div>
        </div>
        <div className="text-xs text-slate-500 space-y-1.5 leading-relaxed">
          <div><span className="text-slate-400 font-medium">CashUP</span> — AI Finance Controller v1.0</div>
          <div>Built for Razorpay Buildathon 2026</div>
          <div className="pt-1 text-slate-600">
            Core principle: AI proposes. Deterministic financial logic verifies.
            Financial arithmetic is never delegated to an LLM.
          </div>
        </div>
      </div>
    </div>
  );
}
