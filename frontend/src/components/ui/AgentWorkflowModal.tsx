// AgentWorkflowModal — visual modal for the LangGraph agent workflow execution
// Enhanced with Level 3 Spatial Flow:
// Shows records moving through INGEST → NORMALIZE → MATCH → VERIFY → CLASSIFY
// Uses actual trace steps from the deterministic engine
// Terminal verification pulse wave upon run completion

import React from 'react';
import { GitMerge, CheckCircle, X, ArrowRight, Clock, Zap, Check } from 'lucide-react';
import type { TraceStep } from '../../types';
import { formatMs } from '../../utils/format';

interface AgentWorkflowModalProps {
  isOpen: boolean;
  onClose: () => void;
  isRunning: boolean;
  trace: TraceStep[];
  runId?: string;
}

const WORKFLOW_NODES = [
  { node: 'INGEST', label: 'Ingest Sources', stage: 'STAGE 1', description: 'Validate and load multi-source records' },
  { node: 'NORMALIZE', label: 'Normalize Records', stage: 'STAGE 2', description: 'Standardize references, dates, and amounts' },
  { node: 'MATCH', label: 'Match Transactions', stage: 'STAGE 3', description: 'Identify candidates across ERP, gateway, and bank feeds' },
  { node: 'VERIFY', label: 'Verify Evidence', stage: 'STAGE 4', description: 'Deterministic arithmetic, SLA, & bank verification' },
  { node: 'CLASSIFY', label: 'Classify Scenarios', stage: 'STAGE 5', description: 'Categorize into exact, fee, delayed, and exceptions' },
  { node: 'EXCEPTION_ANALYSIS', label: 'Investigate Exceptions', stage: 'STAGE 6', description: 'Construct structured anomaly contexts' },
  { node: 'REPORT', label: 'Generate Report', stage: 'STAGE 7', description: 'Calculate final metrics and evaluate ground truth' },
];

export function AgentWorkflowModal({
  isOpen,
  onClose,
  isRunning,
  trace,
  runId,
}: AgentWorkflowModalProps) {
  if (!isOpen) return null;

  const traceMap = new Map<string, TraceStep>();
  trace.forEach(t => traceMap.set(t.node, t));
  const totalDuration = trace.reduce((acc, t) => acc + t.duration_ms, 0);
  const isComplete = !isRunning && trace.length >= 5;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 backdrop-blur-md p-4 perspective-container">
      <div className="bg-slate-900/95 border border-cyan-500/40 rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200 depth-z3 preserve-3d">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-700/60 flex items-center justify-between bg-slate-850/60">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-9 h-9 rounded-xl bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center">
                <GitMerge size={18} className="text-cyan-400" />
              </div>
              {isRunning && (
                <span className="absolute -top-1 -right-1 flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500" />
                </span>
              )}
            </div>
            <div>
              <div className="text-[10px] font-bold text-cyan-400 uppercase tracking-widest leading-none">
                LangGraph Deterministic Orchestration
              </div>
              <div className="text-sm font-semibold text-slate-100 mt-1">
                {isRunning ? 'Reconciling Ledger Records...' : `Reconciliation Run ${runId ?? ''}`}
              </div>
            </div>
          </div>
          {!isRunning && (
            <button
              onClick={onClose}
              className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 transition-colors"
            >
              <X size={15} />
            </button>
          )}
        </div>

        {/* Spatial Stage Flow Track (Top Visualization) */}
        <div className="px-6 py-3.5 bg-slate-950/70 border-b border-slate-800/80">
          <div className="flex items-center justify-between text-[10px] font-mono mb-2">
            <span className="text-slate-400">FINANCIAL PIPELINE CONDUIT</span>
            <span className="text-cyan-400">
              {isRunning ? 'TRANSACTIONS IN TRANSIT' : isComplete ? 'PIPELINE VERIFIED ✓' : 'IDLE'}
            </span>
          </div>

          <div className="flex items-center justify-between gap-1.5 relative">
            {WORKFLOW_NODES.slice(0, 5).map((node, i) => {
              const done = !!traceMap.get(node.node);
              const active = isRunning && !done && (i === 0 || !!traceMap.get(WORKFLOW_NODES[i - 1]?.node));

              return (
                <React.Fragment key={node.node}>
                  <div
                    className={`flex-1 py-1.5 px-2 rounded-lg text-center border transition-all duration-200 ${
                      done
                        ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.15)]'
                        : active
                        ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200 animate-pulse shadow-[0_0_12px_rgba(6,182,212,0.3)]'
                        : 'bg-slate-900/40 border-slate-800 text-slate-600'
                    }`}
                  >
                    <div className="text-[8px] uppercase tracking-wider font-bold opacity-75">{node.stage}</div>
                    <div className="text-[10px] font-bold truncate mt-0.5">{node.node}</div>
                  </div>
                  {i < 4 && (
                    <ArrowRight
                      size={12}
                      className={done ? 'text-emerald-400' : active ? 'text-cyan-400 animate-pulse' : 'text-slate-700'}
                    />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Step-by-Step Execution Trace */}
        <div className="p-6 space-y-2.5 max-h-[50vh] overflow-y-auto">
          {WORKFLOW_NODES.map((item, idx) => {
            const step = traceMap.get(item.node);
            const isDone = !!step;
            const isCurrent =
              isRunning &&
              !isDone &&
              (idx === 0 || !!traceMap.get(WORKFLOW_NODES[idx - 1]?.node));

            return (
              <div
                key={item.node}
                className={`p-3 rounded-xl border transition-all duration-200 ${
                  isDone
                    ? 'bg-slate-850/80 border-slate-700/60 shadow-sm'
                    : isCurrent
                    ? 'bg-cyan-500/10 border-cyan-500/40 shadow-md shadow-cyan-950/40'
                    : 'bg-slate-900/30 border-slate-800/40 opacity-40'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    {isDone ? (
                      <CheckCircle size={15} className="text-emerald-400 flex-shrink-0" />
                    ) : isCurrent ? (
                      <div className="w-3.5 h-3.5 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin flex-shrink-0" />
                    ) : (
                      <div className="w-3.5 h-3.5 rounded-full border border-slate-600 flex-shrink-0" />
                    )}
                    <span
                      className={`text-xs font-semibold ${
                        isDone ? 'text-slate-200' : isCurrent ? 'text-cyan-300' : 'text-slate-500'
                      }`}
                    >
                      {item.label}
                    </span>
                  </div>
                  {step && (
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700 tabular-nums">
                      {formatMs(step.duration_ms)}
                    </span>
                  )}
                </div>
                {step ? (
                  <div className="text-[11px] text-emerald-400/90 mt-1 pl-6 font-mono">{step.message}</div>
                ) : (
                  <div className="text-[11px] text-slate-500 mt-1 pl-6">{item.description}</div>
                )}
              </div>
            );
          })}
        </div>

        {/* Completion Verification Wave Pulse */}
        {isComplete && (
          <div className="mx-6 mb-4 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-between shadow-[0_0_20px_rgba(16,185,129,0.15)] animate-in fade-in duration-300">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span className="text-xs font-bold text-emerald-300">
                Deterministic Financial Verification Wave Confirmed
              </span>
            </div>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/20 px-2 py-0.5 rounded border border-emerald-500/40">
              LEDGER VERIFIED
            </span>
          </div>
        )}

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-700/60 bg-slate-850/40 flex items-center justify-between">
          <div className="text-xs text-slate-400 flex items-center gap-2 font-mono">
            <Clock size={13} className="text-slate-500" />
            {isRunning ? (
              <span>Executing deterministic verification...</span>
            ) : (
              <span>
                Total execution: <strong className="text-slate-200">{formatMs(totalDuration)}</strong>
              </span>
            )}
          </div>
          {!isRunning && (
            <button
              onClick={onClose}
              className="px-5 py-2 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white rounded-lg text-xs font-bold transition-all shadow-md shadow-cyan-950/50 flex items-center gap-2"
            >
              <span>View Results</span>
              <ArrowRight size={13} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
