// CashUP — Overview & Analytics Dashboard
// Professional Financial Operations Console
// Clean, dense, calm, and precise

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Layers, CheckCircle, AlertTriangle, ArrowRight,
  Activity, Database, Zap, UploadCloud, Check,
} from 'lucide-react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import { useApp } from '../store/AppContext';
import { MetricCard } from '../components/ui/MetricCard';
import { StatusBadge, ExceptionBadge } from '../components/ui/StatusBadge';
import { TableConfidenceBar } from '../components/ui/ConfidenceBar';
import { EvidencePanel } from '../components/ui/EvidencePanel';
import {
  formatCurrency,
  formatCompactCurrency,
  formatPct,
} from '../utils/format';

const STATUS_COLORS: Record<string, string> = {
  'Exact Match': '#10b981',
  'Fee Adjusted': '#06b6d4',
  'Delayed': '#3b82f6',
  'Human Review': '#f59e0b',
  'Unresolved': '#ef4444',
};

// =============================================================================
// PRE-RUN EXECUTIVE ARCHITECTURE COCKPIT (Clean & Restrained)
// =============================================================================
function EmptyState({
  onLoad,
  onRun,
  onUpload,
  isLoading,
  hasData,
  dataStatus,
}: {
  onLoad: () => void;
  onRun: () => void;
  onUpload: () => void;
  isLoading: boolean;
  hasData: boolean;
  dataStatus?: any;
}) {
  const invoiceCount = dataStatus?.invoices ?? 0;
  const settlementCount = dataStatus?.settlements ?? 0;
  const bankCount = dataStatus?.bank_transactions ?? 0;

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 sm:p-10 min-h-[calc(100vh-100px)]">
      <div className="w-full max-w-4xl p-6 sm:p-8 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-xl relative overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 mb-6 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <span className={`w-2 h-2 rounded-full ${hasData ? 'bg-emerald-400' : 'bg-cyan-400'}`} />
            <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
              Reconciliation Operations Console
            </span>
          </div>

          <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded border font-medium ${
            hasData
              ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/25'
              : 'text-cyan-400 bg-cyan-500/10 border-cyan-500/25'
          }`}>
            {hasData ? 'Dataset Ready' : 'Engine Ready'}
          </span>
        </div>

        {/* 3-Stream Flow Pipeline */}
        <div className="grid grid-cols-1 md:grid-cols-11 gap-3 items-center my-4">
          {/* Feed Streams (Left - 4 cols) */}
          <div className="md:col-span-4 space-y-2.5">
            {/* ERP Invoices */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-left">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-mono text-cyan-400 font-medium">ERP Invoices</span>
                <span className="text-[10px] font-mono text-slate-400">
                  {hasData ? `${invoiceCount} rows` : 'Source A'}
                </span>
              </div>
              <div className="text-[11px] text-slate-200">
                {hasData ? `${invoiceCount} Invoices Loaded` : 'INV-2026045 · ₹29,700'}
              </div>
              <div className="text-[9px] text-slate-500 mt-0.5">Billing Ledgers & Customer AR</div>
            </div>

            {/* Settlement Slips */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-left">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-mono text-indigo-400 font-medium">Settlement Slips</span>
                <span className="text-[10px] font-mono text-slate-400">
                  {hasData ? `${settlementCount} rows` : 'Source B'}
                </span>
              </div>
              <div className="text-[11px] text-slate-200">
                {hasData ? `${settlementCount} Settlements Loaded` : 'SET-8821 · ₹17,820 (Net)'}
              </div>
              <div className="text-[9px] text-slate-500 mt-0.5">Gateway Fee Deductions</div>
            </div>

            {/* Bank Statements */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-left">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-mono text-emerald-400 font-medium">Bank Statements</span>
                <span className="text-[10px] font-mono text-slate-400">
                  {hasData ? `${bankCount} rows` : 'Source C'}
                </span>
              </div>
              <div className="text-[11px] text-slate-200">
                {hasData ? `${bankCount} Bank Transactions Loaded` : 'TXN-48392 · ₹2,91,600'}
              </div>
              <div className="text-[9px] text-slate-500 mt-0.5">Direct Clearing & Escrow Credits</div>
            </div>
          </div>

          {/* Flow Arrow */}
          <div className="md:col-span-1 hidden md:flex items-center justify-center">
            <ArrowRight size={16} className="text-slate-600" />
          </div>

          {/* Central CashUP Core */}
          <div className="md:col-span-2 py-5 px-3 rounded-xl bg-slate-950/70 border border-slate-800 text-center">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 mx-auto mb-2">
              <Zap size={16} />
            </div>
            <div className="text-xs font-semibold text-slate-100">CashUP Core</div>
            <div className="text-[9px] text-cyan-400 font-mono mt-0.5">Deterministic Parity</div>
            <div className="text-[9px] text-slate-400 mt-1.5 leading-tight px-1">
              Gross matching, MDR variances, & SLA verification
            </div>
          </div>

          {/* Flow Arrow */}
          <div className="md:col-span-1 hidden md:flex items-center justify-center">
            <ArrowRight size={16} className="text-slate-600" />
          </div>

          {/* Outcomes */}
          <div className="md:col-span-3 space-y-2.5">
            <div className="p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20 text-left">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-emerald-400 flex items-center gap-1.5">
                  <Check size={12} /> Auto-Verified
                </span>
                <span className="text-[9px] text-emerald-300 font-mono">GL Ready</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-1">Zero human touch · Cleared</div>
            </div>

            <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20 text-left">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-amber-400 flex items-center gap-1.5">
                  <AlertTriangle size={12} /> Review Required
                </span>
                <span className="text-[9px] text-amber-300 font-mono">Exceptions</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-1">Partial, delayed, fee variances</div>
            </div>

            <div className="p-3 rounded-xl bg-red-500/5 border border-red-500/20 text-left">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-red-400 flex items-center gap-1.5">
                  <AlertTriangle size={12} /> Unresolved
                </span>
                <span className="text-[9px] text-red-300 font-mono">Alert</span>
              </div>
              <div className="text-[10px] text-slate-400 mt-1">Missing feed or discrepancy</div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-left">
            <div className="text-xs font-medium text-slate-200">
              {hasData ? 'Dataset ready for reconciliation' : 'Upload financial data or load demo benchmark'}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              {hasData
                ? `${invoiceCount} Invoices, ${settlementCount} Settlements, ${bankCount} Bank Transactions in workspace.`
                : '100% deterministic matching rules with auditable ground truth.'}
            </div>
          </div>

          <div className="flex items-center gap-2.5 flex-shrink-0">
            <button
              onClick={onUpload}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700/80 border border-slate-700 rounded-lg text-xs font-medium text-slate-200 transition-colors cursor-pointer"
            >
              <UploadCloud size={12} className="text-indigo-400" />
              <span>Upload CSVs</span>
            </button>

            {!hasData && (
              <button
                onClick={onLoad}
                disabled={isLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700/80 border border-slate-700 rounded-lg text-xs font-medium text-slate-200 transition-colors cursor-pointer"
              >
                <Database size={12} className="text-cyan-400" />
                <span>{isLoading ? 'Loading…' : 'Load Demo Benchmark'}</span>
              </button>
            )}

            <button
              onClick={onRun}
              disabled={isLoading || !hasData}
              className="flex items-center gap-2 px-4 py-1.5 bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 disabled:opacity-40 rounded-lg text-xs text-white font-semibold transition-all shadow-sm cursor-pointer"
            >
              <Zap size={12} />
              <span>Run Reconciliation</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN OVERVIEW PAGE
// =============================================================================
export function OverviewPage() {
  const {
    currentRun,
    exceptions,
    runStatus,
    loadDemo,
    runReconciliation,
    dataStatus,
    selectedResult,
    selectResult,
    handleReview,
    setUploadModalOpen,
  } = useApp();

  const [hoveredStatus, setHoveredStatus] = useState<string | null>(null);

  const hasData = Boolean(dataStatus?.ready || (dataStatus?.invoices ?? 0) > 0);
  const isLoading = runStatus === 'loading';
  const isRunning = runStatus === 'running';

  if (!currentRun) {
    return (
      <div className="h-full flex flex-col">
        <EmptyState
          onLoad={loadDemo}
          onRun={runReconciliation}
          onUpload={() => setUploadModalOpen(true)}
          isLoading={isLoading || isRunning}
          hasData={hasData}
          dataStatus={dataStatus}
        />
      </div>
    );
  }

  const run = currentRun;
  const isBenchmark = Boolean(dataStatus?.has_ground_truth && dataStatus?.dataset_source === 'benchmark');

  const pieData = [
    { name: 'Exact Match', value: run.exact_matches },
    { name: 'Fee Adjusted', value: run.fee_matches },
    { name: 'Delayed', value: run.probable_matches },
    { name: 'Human Review', value: run.human_review },
    { name: 'Unresolved', value: run.unresolved },
  ].filter(d => d.value > 0);

  // Terminal Decisions (Invariant: autoVerified + reviewRequired + unresolved === records_processed)
  const autoVerified = run.auto_resolved;
  const unresolved = run.unresolved;
  const reviewRequired = Math.max(0, run.records_processed - autoVerified - unresolved);

  // Canonical matched records: exact + fee + probable/delayed
  // (match_rate = matchedRecords / records_processed)
  const matchedRecords = Math.min(
    run.records_processed,
    Math.max(0, run.exact_matches + run.fee_matches + run.probable_matches)
  );

  const openExceptionsCount = run.open_exception_count ?? (run.human_review + run.unresolved);
  const autoVerifiedPct = run.records_processed > 0 ? (autoVerified / run.records_processed) * 100 : 0;

  return (
    <div className="flex h-full w-full min-w-0 max-w-full justify-center">
      {/* Main Operational Canvas */}
      <div
        className={`flex-1 overflow-x-hidden w-full min-w-0 max-w-full p-4 sm:p-6 space-y-6 sm:space-y-7 ${
          selectedResult ? 'dashboard-recede' : 'dashboard-normal'
        }`}
      >
        {/* ================================================================= */}
        {/* 1. COMPACT RUN SUMMARY STRIP (Quiet horizontal information band)  */}
        {/* ================================================================= */}
        <div className="flex flex-wrap items-center justify-between gap-3 sm:gap-6 px-4 sm:px-5 py-2.5 sm:py-3 bg-slate-900/80 border border-slate-800 rounded-xl text-xs shadow-sm">
          {/* Left: Run ID & Dataset scope */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                Run Summary
              </span>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-800/80 text-cyan-300 border border-slate-700/60 font-medium">
                {run.run_id}
              </span>
            </div>
            <span className="text-slate-700 hidden sm:inline">|</span>
            <span className="text-slate-400 text-xs hidden sm:inline">
              {run.records_processed} invoices · {isBenchmark ? 'Benchmark dataset' : 'Uploaded dataset'}
            </span>
          </div>

          {/* Right: Metrics & System Status */}
          <div className="flex flex-wrap items-center gap-4 sm:gap-6 font-mono text-xs ml-auto">
            <div className="flex items-baseline gap-1.5">
              <span className="text-emerald-400 font-semibold tabular-nums">
                {autoVerifiedPct.toFixed(1)}%
              </span>
              <span className="text-slate-400 text-[11px] font-sans">
                Auto-cleared ({run.auto_resolved}/{run.records_processed})
              </span>
            </div>

            <div className="w-px h-3.5 bg-slate-800 hidden sm:block" />

            <div className="flex items-baseline gap-1.5">
              <span className="text-slate-100 font-semibold tabular-nums">
                {formatCurrency(run.reconciled_amount)}
              </span>
              <span className="text-slate-400 text-[11px] font-sans">
                Reconciled net
              </span>
            </div>

            <div className="w-px h-3.5 bg-slate-800 hidden md:block" />

            <div className="hidden md:flex items-center gap-1.5 text-[11px] font-sans text-slate-400">
              <span>Deterministic verification active</span>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
            </div>
          </div>
        </div>

        {/* ================================================================= */}
        {/* 2. PRIMARY KPI ROW (Four wide, unbloated cards)                  */}
        {/* ================================================================= */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 w-full min-w-0">
          <MetricCard
            label="Reconciled Value"
            value={formatCompactCurrency(run.reconciled_amount)}
            description="Successfully cleared net value"
            tooltip="Total financial invoice value successfully reconciled and confirmed against settlement/bank feeds."
            accent="cyan"
          />
          <MetricCard
            label="Match Rate"
            value={formatPct(run.match_rate)}
            description={`${matchedRecords} of ${run.records_processed} matched`}
            tooltip="Percentage of invoice records successfully linked to corresponding settlement/bank transactions."
            accent={run.match_rate >= 0.8 ? 'green' : 'amber'}
          />
          <MetricCard
            label="Verified Accuracy"
            value={
              run.verified_accuracy !== null && run.verified_accuracy !== undefined
                ? formatPct(run.verified_accuracy)
                : 'N/A'
            }
            secondaryLine={
              run.verified_accuracy === null || run.verified_accuracy === undefined
                ? 'No benchmark ground truth'
                : undefined
            }
            description={
              run.verified_accuracy !== null && run.verified_accuracy !== undefined
                ? 'Validated against hidden benchmark key'
                : 'Ordinary uploaded dataset'
            }
            tooltip={
              run.verified_accuracy !== null && run.verified_accuracy !== undefined
                ? 'Measured objectively against hidden benchmark ground truth. Isolated from decision engine.'
                : 'Ground-truth labels were not supplied for this uploaded dataset.'
            }
            accent={
              run.verified_accuracy !== null && run.verified_accuracy !== undefined
                ? run.verified_accuracy >= 0.8
                  ? 'green'
                  : 'amber'
                : 'default'
            }
          />
          <MetricCard
            label="Open Exceptions"
            value={openExceptionsCount}
            description={openExceptionsCount > 0 ? 'Requires controller review' : 'Clean ledger balance'}
            tooltip="Records requiring controller investigation (partial payments, delayed settlements, or missing feeds)."
            accent={openExceptionsCount > 0 ? 'red' : 'green'}
          />
        </div>

        {/* ================================================================= */}
        {/* 3. RECONCILIATION HEALTH (Flow ~68% + Status Distribution ~32%)    */}
        {/* ================================================================= */}
        <div className="space-y-3">
          <div>
            <h2 className="text-base sm:text-lg font-semibold text-slate-100 tracking-tight">
              Reconciliation health
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Decision pipeline efficiency and portfolio status breakdown
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6 w-full min-w-0 items-stretch">
            
            {/* LEFT 68% (8 cols): Horizontal Decision Rail */}
            <div className="lg:col-span-8 bg-slate-900/80 border border-slate-800 rounded-xl p-5 flex flex-col justify-between min-w-0 shadow-sm relative overflow-hidden">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-xs font-semibold text-slate-200 tracking-wide">
                    Reconciliation flow
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    How records move from ingestion to verified outcomes
                  </p>
                </div>
                <span className="text-[10px] font-mono text-cyan-400/90 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/25">
                  Rule Engine
                </span>
              </div>

              {/* Horizontal Decision Rail Layout */}
              <div className="my-auto py-3">
                <div className="flex flex-col sm:flex-row items-center gap-3 sm:gap-4 w-full">
                  
                  {/* Step 1: Ingested */}
                  <div className="w-full sm:w-28 p-3.5 bg-slate-800/60 border border-slate-700/70 rounded-xl text-center flex-shrink-0">
                    <div className="text-2xl font-bold font-mono text-slate-100 tabular-nums leading-none">
                      {run.records_processed}
                    </div>
                    <div className="text-[11px] font-medium text-slate-300 mt-1.5">
                      Ingested
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                      100% Invoices
                    </div>
                  </div>

                  {/* Connecting Arrow */}
                  <div className="hidden sm:flex items-center justify-center flex-shrink-0 text-slate-600">
                    <ArrowRight size={16} />
                  </div>

                  {/* Step 2: Matched */}
                  <div className="w-full sm:w-28 p-3.5 bg-slate-800/80 border border-cyan-500/30 rounded-xl text-center flex-shrink-0">
                    <div className="text-2xl font-bold font-mono text-cyan-400 tabular-nums leading-none">
                      {matchedRecords}
                    </div>
                    <div className="text-[11px] font-medium text-slate-300 mt-1.5">
                      Matched
                    </div>
                    <div className="text-[10px] text-cyan-400/80 font-mono mt-0.5">
                      {run.records_processed > 0 ? ((matchedRecords / run.records_processed) * 100).toFixed(1) : 0}% Linked
                    </div>
                  </div>

                  {/* Connecting Arrow */}
                  <div className="hidden sm:flex items-center justify-center flex-shrink-0 text-slate-600">
                    <ArrowRight size={16} />
                  </div>

                  {/* Step 3: Outcomes Branch (Stacked vertically on right) */}
                  <div className="flex-1 w-full space-y-2 min-w-0">
                    {/* Auto-verified */}
                    <div className="p-2.5 rounded-lg bg-emerald-500/5 border border-emerald-500/25 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                        <span className="text-xs font-semibold text-emerald-300 truncate">Auto-verified</span>
                        <span className="text-[10px] text-slate-400 font-mono hidden xl:inline">
                          Exact ({run.exact_matches}) + Fee ({run.fee_matches})
                        </span>
                      </div>
                      <span className="text-base font-bold font-mono text-emerald-400 tabular-nums flex-shrink-0">
                        {autoVerified}
                      </span>
                    </div>

                    {/* Review required */}
                    <div className="p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/25 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                        <span className="text-xs font-semibold text-amber-300 truncate">Review required</span>
                        <span className="text-[10px] text-slate-400 font-mono hidden xl:inline">
                          Delayed ({run.probable_matches}) + Flagged ({run.human_review})
                        </span>
                      </div>
                      <span className="text-base font-bold font-mono text-amber-400 tabular-nums flex-shrink-0">
                        {reviewRequired}
                      </span>
                    </div>

                    {/* Unresolved */}
                    <div className="p-2.5 rounded-lg bg-red-500/5 border border-red-500/25 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                        <span className="text-xs font-semibold text-red-300 truncate">Unresolved</span>
                        <span className="text-[10px] text-slate-400 font-mono hidden xl:inline">
                          Missing gateway feed
                        </span>
                      </div>
                      <span className="text-base font-bold font-mono text-red-400 tabular-nums flex-shrink-0">
                        {unresolved}
                      </span>
                    </div>
                  </div>

                </div>
              </div>

              {/* Progress pulse only when running */}
              {isRunning && (
                <div className="mt-3 pt-2 border-t border-slate-800 flex items-center gap-2 text-[11px] font-mono text-cyan-400 animate-pulse">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  <span>Processing transactions in engine pipeline…</span>
                </div>
              )}
            </div>

            {/* RIGHT 32% (4 cols): Status Distribution with Aligned Legend */}
            <div className="lg:col-span-4 bg-slate-900/80 border border-slate-800 rounded-xl p-5 flex flex-col justify-between min-w-0 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold text-slate-200 tracking-wide">
                  Status distribution
                </h3>
                <span className="text-[11px] text-slate-500 font-mono">
                  {run.records_processed} Total
                </span>
              </div>

              {/* Donut Chart */}
              <div className="relative my-auto w-full min-w-0 overflow-hidden py-1">
                <ResponsiveContainer width="100%" height={140}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={42}
                      outerRadius={58}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {pieData.map(entry => {
                        const isHovered = hoveredStatus === entry.name;
                        return (
                          <Cell
                            key={entry.name}
                            fill={STATUS_COLORS[entry.name] ?? '#64748b'}
                            opacity={hoveredStatus ? (isHovered ? 1 : 0.4) : 0.9}
                            stroke={isHovered ? '#ffffff' : 'none'}
                            strokeWidth={isHovered ? 2 : 0}
                          />
                        );
                      })}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: '#0f172a',
                        border: '1px solid #334155',
                        borderRadius: 8,
                        fontSize: 11,
                        color: '#f8fafc',
                      }}
                      formatter={(val: any) => [val, 'Count']}
                    />
                  </PieChart>
                </ResponsiveContainer>
                
                {/* Center Stat */}
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                  <span className="text-lg font-bold font-mono text-slate-100 tabular-nums leading-none">
                    {run.match_rate >= 0.8 ? formatPct(run.match_rate) : run.records_processed}
                  </span>
                  <span className="text-[9px] text-slate-400 font-semibold tracking-wider mt-0.5 uppercase">
                    {run.match_rate >= 0.8 ? 'Match Rate' : 'Total'}
                  </span>
                </div>
              </div>

              {/* Aligned Legend */}
              <div className="space-y-1 pt-3 border-t border-slate-800/80">
                {[
                  { name: 'Exact Match', count: run.exact_matches, color: '#10b981' },
                  { name: 'Fee Adjusted', count: run.fee_matches, color: '#06b6d4' },
                  { name: 'Delayed', count: run.probable_matches, color: '#3b82f6' },
                  { name: 'Human Review', count: run.human_review, color: '#f59e0b' },
                  { name: 'Unresolved', count: run.unresolved, color: '#ef4444' },
                ].map(item => (
                  <div
                    key={item.name}
                    onMouseEnter={() => setHoveredStatus(item.name)}
                    onMouseLeave={() => setHoveredStatus(null)}
                    className={`flex items-center justify-between text-xs py-1 px-1.5 rounded transition-colors cursor-default ${
                      hoveredStatus === item.name ? 'bg-slate-800/80' : ''
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ background: item.color }}
                      />
                      <span className="text-slate-400 text-[11px] truncate">
                        {item.name}
                      </span>
                    </div>
                    <span className="text-slate-200 font-mono font-medium tabular-nums text-xs ml-2 flex-shrink-0">
                      {item.count}
                    </span>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>

        {/* ================================================================= */}
        {/* 4. NEEDS ATTENTION (Compact, Actionable Operational Section)       */}
        {/* ================================================================= */}
        {exceptions.length > 0 && (
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
            <div className="px-4 sm:px-5 py-3 border-b border-slate-800/80 flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-shrink-0" />
                <h3 className="text-sm font-semibold text-slate-100">
                  Needs attention
                </h3>
                <span className="text-xs text-slate-500 font-mono hidden sm:inline">
                  ({exceptions.length} exceptions total)
                </span>
              </div>
              <Link
                to="/app/exceptions"
                className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors font-medium flex items-center gap-1 group"
              >
                <span>View all</span>
                <ArrowRight size={13} className="group-hover:translate-x-0.5 transition-transform" />
              </Link>
            </div>

            <div className="divide-y divide-slate-800/50">
              {exceptions.slice(0, 3).map(r => {
                const diffAbs = Math.abs(r.difference);
                return (
                  <div
                    key={r.result_id}
                    onClick={() => selectResult(r)}
                    className="px-4 sm:px-5 py-2.5 flex items-center justify-between gap-3 hover:bg-slate-800/40 transition-colors cursor-pointer text-xs"
                  >
                    <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                      <span className="font-mono text-cyan-300 font-medium text-xs whitespace-nowrap">
                        {r.invoice_id}
                      </span>
                      <span className="text-slate-300 truncate max-w-[130px] sm:max-w-[200px]">
                        {r.customer_name}
                      </span>
                      {r.exception_category && (
                        <span className="hidden md:inline-block px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-slate-800 text-slate-300 border border-slate-700/60">
                          {r.exception_category}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3 sm:gap-5 flex-shrink-0">
                      <div className="text-right font-mono tabular-nums">
                        {diffAbs > 0 ? (
                          <span className="text-red-400 font-medium">-{formatCurrency(diffAbs)}</span>
                        ) : (
                          <span className="text-slate-400">{formatCurrency(r.invoice_amount)}</span>
                        )}
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${
                        r.status === 'Unresolved'
                          ? 'bg-red-500/10 text-red-300 border-red-500/25'
                          : 'bg-amber-500/10 text-amber-300 border-amber-500/25'
                      }`}>
                        {r.status}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          selectResult(r);
                        }}
                        className="text-[11px] text-cyan-400 hover:text-cyan-300 font-medium hidden sm:inline-flex items-center gap-0.5"
                      >
                        <span>Review</span>
                        <ArrowRight size={11} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

      </div>

      {/* EVIDENCE DRAWER */}
      {selectedResult && (
        <div className="depth-drawer relative z-40">
          <EvidencePanel
            result={selectedResult}
            onClose={() => selectResult(null)}
            onApprove={id => handleReview(id, 'approve')}
            onReject={id => handleReview(id, 'reject')}
            onKeep={id => handleReview(id, 'keep_open')}
          />
        </div>
      )}
    </div>
  );
}
