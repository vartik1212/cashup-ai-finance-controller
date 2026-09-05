// EvidencePanel — full transaction evidence drawer with audit trail and action buttons
// Clearly separates SYSTEM VERIFICATION (deterministic engine) and AI INVESTIGATION (Gemini)

import React, { useState, useEffect } from 'react';
import {
  X, CheckCircle, AlertTriangle, XCircle, Clock,
  Check, Slash, HelpCircle, Sparkles, RefreshCw,
  ShieldAlert, ShieldCheck, FileText, ArrowRight
} from 'lucide-react';
import type { ReconciliationResult, AIExceptionAnalysis } from '../../types';
import { StatusBadge, ExceptionBadge } from './StatusBadge';
import { ConfidenceBar } from './ConfidenceBar';
import { formatCurrency, formatDiff } from '../../utils/format';
import * as api from '../../api/client';

interface EvidencePanelProps {
  result: ReconciliationResult | null;
  onClose: () => void;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onKeep: (id: string) => void;
}

export function EvidencePanel({
  result,
  onClose,
  onApprove,
  onReject,
  onKeep,
}: EvidencePanelProps) {
  const [aiAnalysis, setAiAnalysis] = useState<AIExceptionAnalysis | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Reset or load cached analysis when selected result changes
  useEffect(() => {
    setAiAnalysis(null);
    setAnalysisError(null);
    setIsAnalyzing(false);
  }, [result?.invoice_id, result?.run_id]);

  if (!result) return null;

  const handleAnalyze = async (force = false) => {
    if (!result.invoice_id || isAnalyzing) return;
    setIsAnalyzing(true);
    setAnalysisError(null);
    try {
      const data = await api.analyzeException(result.invoice_id, result.run_id, force);
      setAiAnalysis(data);
    } catch (err: any) {
      setAnalysisError(err?.response?.data?.detail || err.message || 'Failed to analyze exception');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const hasDiff = result.difference !== 0;
  const diffColor =
    result.difference === 0
      ? 'text-emerald-400'
      : result.difference > 0
      ? 'text-amber-400'
      : 'text-red-400';

  const hasSettlement = !!result.settlement_amount;
  const invAmt = result.invoice_amount;
  const setAmt = result.settlement_amount ?? 0;
  const feeEstimate = hasSettlement && invAmt > setAmt ? (invAmt - setAmt) / 1.18 : 0;
  const gstEstimate = feeEstimate * 0.18;

  const evidenceMap = new Map(
    result.evidence?.map(e => [e.label.toLowerCase(), e]) ?? []
  );

  const getEvidenceStatus = (key: string, requireSettlement = false) => {
    if (!hasSettlement && requireSettlement) {
      return { status: 'NOT_AVAILABLE', detail: 'No settlement record available' };
    }
    for (const [k, v] of evidenceMap.entries()) {
      if (k.includes(key)) {
        return { status: v.matched ? 'PASS' : 'FAIL', detail: v.detail };
      }
    }
    return { status: hasSettlement ? 'PASS' : 'NOT_AVAILABLE', detail: 'N/A' };
  };

  const refCheck = getEvidenceStatus('reference', true);
  const custCheck = getEvidenceStatus('customer', true);
  const amtCheck = getEvidenceStatus('amount', true);
  const feeCheck = getEvidenceStatus('fee', true);
  const dateCheck = hasSettlement
    ? result.days_delayed != null && result.days_delayed > 5
      ? { status: 'WARNING', detail: `Received ${result.days_delayed} days post-invoice (SLA warning)` }
      : { status: 'PASS', detail: 'Within normal SLA (≤ 5 days)' }
    : { status: 'NOT_AVAILABLE', detail: 'No settlement record' };

  const bankCheck = hasSettlement
    ? result.bank_txn_id
      ? { status: 'PASS', detail: `Verified bank txn: ${result.bank_txn_id}` }
      : { status: 'WARNING', detail: 'Pending bank statement confirmation' }
    : { status: 'NOT_AVAILABLE', detail: 'No settlement record' };

  const checks = [
    { label: 'Reference Code Matching', ...refCheck },
    { label: 'Customer ID Alignment', ...custCheck },
    { label: 'Gross Amount Parity', ...amtCheck },
    { label: 'Gateway Fee Schedule Verification', ...feeCheck },
    { label: 'Settlement Delivery SLA (≤ 5 days)', ...dateCheck },
    { label: 'Bank Statement Settlement Verification', ...bankCheck },
  ];

  const getRiskBadge = (risk: string) => {
    switch (risk.toUpperCase()) {
      case 'LOW':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <ShieldCheck size={11} /> Low Risk
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
            <AlertTriangle size={11} /> Medium Risk
          </span>
        );
      case 'HIGH':
      default:
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/30">
            <ShieldAlert size={11} /> High Risk
          </span>
        );
    }
  };

  return (
    <div className="w-[460px] flex-shrink-0 bg-slate-900 border-l border-slate-700/60 flex flex-col h-full shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700/60 bg-slate-800/40">
        <div>
          <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1 font-semibold">
            Transaction Details & Investigation
          </div>
          <div className="text-sm font-semibold text-slate-100 font-mono">
            {result.invoice_id}
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 flex items-center justify-center rounded text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 transition-colors"
          title="Close details"
        >
          <X size={15} />
        </button>
      </div>

      {/* Scrollable Body with Two Clearly Separated Sections */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6">

        {/* ======================================================= */}
        {/* SECTION 1: SYSTEM VERIFICATION (Deterministic Source of Truth) */}
        {/* ======================================================= */}
        <section className="space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-slate-700/60">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400" />
              <span className="text-[11px] font-bold tracking-wider uppercase text-slate-200">
                System Verification
              </span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">Deterministic Engine</span>
          </div>

          {/* 3-Way Visual Reconciliation Chain: Invoice ↓ Settlement ↓ Bank */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-2.5 shadow-inner">
            <div className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold flex items-center justify-between pb-1 border-b border-slate-800/80">
              <span className="flex items-center gap-1.5 text-cyan-400">
                <FileText size={11} /> 3-Way Evidence Document Chain
              </span>
              <span className="font-mono text-[9px] text-slate-500">Inspection Mode</span>
            </div>

            {/* Document 1: Invoice Record Surface */}
            <div className="relative p-3 rounded-lg bg-slate-900/90 border border-cyan-500/30 shadow-md transition-all hover:border-cyan-500/50">
              <div className="absolute top-0 right-0 w-8 h-8 overflow-hidden pointer-events-none">
                <div className="w-12 h-12 bg-cyan-500/10 rotate-45 transform origin-bottom-left" />
              </div>
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-[10px] font-mono font-bold text-cyan-300">
                  1
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-slate-100 truncate">{result.invoice_id}</span>
                    <span className="text-xs font-mono font-bold text-cyan-400 tabular-nums">{formatCurrency(result.invoice_amount)}</span>
                  </div>
                  <div className="text-[10px] text-slate-400 flex items-center justify-between mt-0.5">
                    <span className="truncate">ERP AR Ledger · {result.customer_name}</span>
                    <span className="text-[9px] font-mono text-cyan-500/80 uppercase font-semibold">ORIGINAL CLAIM</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Dimensional Conduit Pipe 1 -> 2 */}
            <div className="flex flex-col items-center -my-1 relative z-10">
              <div className="w-0.5 h-3 bg-gradient-to-b from-cyan-500/50 to-indigo-500/50" />
              <div className={`w-2 h-2 rounded-full border ${hasSettlement ? 'bg-indigo-400 border-indigo-300 shadow-[0_0_6px_#818cf8]' : 'bg-red-500 border-red-400 shadow-[0_0_6px_#ef4444]'}`} />
              <div className="w-0.5 h-3 bg-gradient-to-b from-indigo-500/50 to-emerald-500/50" />
            </div>

            {/* Document 2: Settlement Record Surface */}
            <div className={`relative p-3 rounded-lg border transition-all ${
              hasSettlement
                ? 'bg-slate-900/90 border-indigo-500/30 shadow-md hover:border-indigo-500/50'
                : 'bg-red-950/20 border-dashed border-red-500/50 shadow-inner'
            }`}>
              <div className="flex items-center gap-3">
                <div className={`w-6 h-6 rounded flex items-center justify-center text-[10px] font-mono font-bold ${
                  hasSettlement
                    ? 'bg-indigo-500/20 border border-indigo-500/40 text-indigo-300'
                    : 'bg-red-500/20 border border-red-500/40 text-red-400'
                }`}>
                  2
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-slate-100 truncate">
                      {result.settlement_id || 'Missing Settlement Record'}
                    </span>
                    <span className={`text-xs font-mono font-bold tabular-nums ${hasSettlement ? 'text-indigo-300' : 'text-red-400'}`}>
                      {hasSettlement ? formatCurrency(result.settlement_amount!) : '₹0.00 (VOID)'}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 flex items-center justify-between mt-0.5">
                    <span className="truncate">
                      {hasSettlement
                        ? `Gateway Feed · Match: ${result.match_type.replace(/_/g, ' ')}`
                        : 'Fractured Chain: No payment gateway settlement detected'}
                    </span>
                    <span className={`text-[9px] font-mono uppercase font-semibold ${hasSettlement ? 'text-indigo-400' : 'text-red-400'}`}>
                      {hasSettlement ? 'NET SETTLED' : 'DISCREPANCY'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Dimensional Conduit Pipe 2 -> 3 */}
            <div className="flex flex-col items-center -my-1 relative z-10">
              <div className="w-0.5 h-3 bg-gradient-to-b from-indigo-500/50 to-emerald-500/50" />
              <div className={`w-2 h-2 rounded-full border ${result.bank_txn_id ? 'bg-emerald-400 border-emerald-300 shadow-[0_0_6px_#34d399]' : 'bg-slate-600 border-slate-500'}`} />
              <div className="w-0.5 h-3 bg-gradient-to-b from-emerald-500/50 to-slate-700/50" />
            </div>

            {/* Document 3: Bank Statement Record Surface */}
            <div className={`relative p-3 rounded-lg border transition-all ${
              result.bank_txn_id
                ? 'bg-slate-900/90 border-emerald-500/30 shadow-md hover:border-emerald-500/50'
                : 'bg-slate-950/40 border-dashed border-slate-800'
            }`}>
              <div className="flex items-center gap-3">
                <div className={`w-6 h-6 rounded flex items-center justify-center text-[10px] font-mono font-bold ${
                  result.bank_txn_id
                    ? 'bg-emerald-500/20 border border-emerald-500/40 text-emerald-300'
                    : 'bg-slate-800 border border-slate-700 text-slate-500'
                }`}>
                  3
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-slate-100 truncate">
                      {result.bank_txn_id || 'Pending Bank Statement Entry'}
                    </span>
                    <span className={`text-xs font-mono font-bold tabular-nums ${result.bank_txn_id ? 'text-emerald-400' : 'text-slate-600'}`}>
                      {result.bank_txn_id ? formatCurrency(result.settlement_amount ?? result.invoice_amount) : '—'}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 flex items-center justify-between mt-0.5">
                    <span className="truncate">
                      {result.bank_txn_id
                        ? 'Core Statement Feed · Direct Account Settlement Confirmed'
                        : 'Pending bank settlement reconciliation or statement delay'}
                    </span>
                    <span className={`text-[9px] font-mono uppercase font-semibold ${result.bank_txn_id ? 'text-emerald-400' : 'text-slate-600'}`}>
                      {result.bank_txn_id ? 'BANK AUDITED' : 'UNCONFIRMED'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* System Verification Key Metrics */}
          <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-[10px] text-slate-500 uppercase block mb-0.5">Invoice</span>
                <span className="font-mono text-slate-200 font-semibold">{result.invoice_id}</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 uppercase block mb-0.5">Current Status</span>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <StatusBadge status={result.status} />
                  {result.exception_category && (
                    <ExceptionBadge category={result.exception_category} />
                  )}
                </div>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 uppercase block mb-0.5">Expected Amount</span>
                <span className="font-mono text-slate-200 font-medium">{formatCurrency(result.invoice_amount)}</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 uppercase block mb-0.5">Received Amount</span>
                <span className="font-mono text-slate-200 font-medium">
                  {result.settlement_amount != null ? formatCurrency(result.settlement_amount) : '—'}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 uppercase block mb-0.5">Difference</span>
                <span className={`font-mono font-semibold ${diffColor}`}>{formatDiff(result.difference)}</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 uppercase block mb-0.5">Settlement Reference</span>
                <span className="font-mono text-slate-300 text-[11px] truncate block" title={result.settlement_id || 'None'}>
                  {result.settlement_id || 'None'}
                </span>
              </div>
              <div className="col-span-2">
                <span className="text-[10px] text-slate-500 uppercase block mb-0.5">Bank Verification</span>
                <span className="text-[11px] text-slate-300 font-mono">
                  {result.bank_txn_id ? `Verified (${result.bank_txn_id})` : (hasSettlement ? 'Pending bank statement match' : 'No settlement to verify')}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 uppercase block mb-0.5">Classification</span>
                <span className="text-xs font-semibold text-cyan-400 capitalize">
                  {result.match_type.replace(/_/g, ' ')}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 uppercase block mb-0.5">Confidence</span>
                <ConfidenceBar score={result.confidence_score} />
              </div>
            </div>
          </div>

          {/* Evidence Signals Checklist */}
          <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-4">
            <div className="text-[10px] text-slate-400 uppercase tracking-widest mb-3 font-semibold">
              Evidence Signals
            </div>
            <div className="space-y-2.5">
              {checks.map(check => {
                const icon =
                  check.status === 'PASS' ? (
                    <CheckCircle size={14} className="text-emerald-400 flex-shrink-0 mt-0.5" />
                  ) : check.status === 'WARNING' ? (
                    <AlertTriangle size={14} className="text-amber-400 flex-shrink-0 mt-0.5" />
                  ) : check.status === 'FAIL' ? (
                    <XCircle size={14} className="text-red-400 flex-shrink-0 mt-0.5" />
                  ) : (
                    <Clock size={14} className="text-slate-600 flex-shrink-0 mt-0.5" />
                  );

                return (
                  <div key={check.label} className="flex items-start gap-2.5 text-xs">
                    {icon}
                    <div>
                      <div className="font-medium text-slate-300">{check.label}</div>
                      <div className="text-[11px] text-slate-500 mt-0.5 leading-tight">
                        {check.detail}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Deterministic System Assessment & Recommendation */}
          <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-4 space-y-3">
            <div>
              <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1 font-semibold">
                System Assessment
              </div>
              <div className="text-xs text-slate-300 leading-relaxed">
                {result.system_assessment}
              </div>
            </div>
            <div className="pt-2 border-t border-slate-700/40">
              <div className="text-[10px] text-cyan-400 uppercase tracking-widest mb-1 font-semibold">
                System Recommendation
              </div>
              <div className="text-xs text-slate-400 leading-relaxed">
                {result.recommendation}
              </div>
            </div>
          </div>
        </section>

        {/* ======================================================= */}
        {/* SECTION 2: AI INVESTIGATION (Gemini Intelligence Layer) */}
        {/* ======================================================= */}
        <section className="space-y-4 pt-2">
          <div className="flex items-center justify-between pb-2 border-b border-cyan-500/30">
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-cyan-400" />
              <span className="text-[11px] font-bold tracking-wider uppercase text-cyan-300">
                AI Investigation
              </span>
            </div>
            <span className="text-[9px] bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 px-2 py-0.5 rounded font-medium">
              AI-GENERATED
            </span>
          </div>

          {!aiAnalysis && !isAnalyzing && (
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-4 text-center space-y-3">
              <p className="text-xs text-slate-400 leading-relaxed">
                Run deep AI root-cause investigation grounded strictly in system evidence.
              </p>
              <button
                onClick={() => handleAnalyze(false)}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white rounded-lg text-xs font-semibold shadow-lg shadow-cyan-900/30 transition-all"
              >
                <Sparkles size={14} />
                Analyze with AI
              </button>
            </div>
          )}

          {isAnalyzing && (
            <div className="bg-slate-800/40 border border-cyan-500/30 rounded-lg p-6 text-center space-y-3">
              <div className="flex justify-center">
                <RefreshCw size={22} className="text-cyan-400 animate-spin" />
              </div>
              <div className="text-xs font-medium text-slate-200">Investigating transaction signals…</div>
              <p className="text-[11px] text-slate-500">
                Synthesizing settlement timing, fee structures, and bank verification.
              </p>
            </div>
          )}

          {analysisError && !isAnalyzing && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-xs text-red-400 space-y-2">
              <div className="font-semibold flex items-center gap-1.5">
                <AlertTriangle size={13} />
                AI Analysis Unavailable
              </div>
              <p className="text-[11px] text-red-300/80">{analysisError}</p>
              <button
                onClick={() => handleAnalyze(true)}
                className="text-[11px] underline hover:text-red-200 text-red-400"
              >
                Try Again
              </button>
            </div>
          )}

          {aiAnalysis && !isAnalyzing && (
            <div className="bg-slate-800/40 border border-cyan-500/40 rounded-lg p-4 space-y-4">
              {/* Header badges: Likely Reason & Risk Level */}
              <div className="flex items-center justify-between gap-2 flex-wrap pb-2 border-b border-slate-700/40">
                <div>
                  <span className="text-[9px] text-slate-500 uppercase block mb-1">Likely Reason</span>
                  <span className="inline-block text-[11px] font-mono font-semibold px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                    {aiAnalysis.likely_reason}
                  </span>
                </div>
                <div>
                  <span className="text-[9px] text-slate-500 uppercase block mb-1">Risk Level</span>
                  {getRiskBadge(aiAnalysis.risk_level)}
                </div>
              </div>

              {/* Summary */}
              <div>
                <span className="text-[10px] text-slate-500 uppercase tracking-widest mb-1 block font-semibold">
                  Summary
                </span>
                <div className="text-xs text-slate-200 font-medium leading-relaxed bg-slate-900/60 p-2.5 rounded border border-slate-700/40">
                  {aiAnalysis.summary}
                </div>
              </div>

              {/* Explanation */}
              <div>
                <span className="text-[10px] text-slate-500 uppercase tracking-widest mb-1 block font-semibold">
                  Explanation
                </span>
                <div className="text-xs text-slate-300 leading-relaxed bg-slate-900/40 p-2.5 rounded border border-slate-700/30 whitespace-pre-line">
                  {aiAnalysis.explanation}
                </div>
              </div>

              {/* Recommended Action */}
              <div>
                <span className="text-[10px] text-cyan-400 uppercase tracking-widest mb-1 block font-semibold flex items-center gap-1">
                  <ArrowRight size={11} /> Recommended Action
                </span>
                <div className="text-xs text-cyan-300 bg-cyan-950/30 p-2.5 rounded border border-cyan-800/40 leading-relaxed">
                  {aiAnalysis.recommended_action}
                </div>
              </div>

              {/* Safety notice & re-analyze option */}
              <div className="pt-2 border-t border-slate-700/40 flex items-center justify-between text-[10px] text-slate-500">
                <span>Advisory only · deterministic status unchanged</span>
                <button
                  onClick={() => handleAnalyze(true)}
                  className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-medium"
                >
                  <RefreshCw size={10} /> Re-analyze
                </button>
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Footer / Review Actions */}
      <div className="p-4 border-t border-slate-700/60 bg-slate-800/40 space-y-2">
        <div className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-2">
          Controller Review Action
        </div>
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => onApprove(result.result_id)}
            className="flex items-center justify-center gap-1.5 py-2 px-3 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/30 rounded text-xs font-semibold transition-colors"
          >
            <Check size={13} />
            Approve
          </button>
          <button
            onClick={() => onReject(result.result_id)}
            className="flex items-center justify-center gap-1.5 py-2 px-3 bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 rounded text-xs font-semibold transition-colors"
          >
            <Slash size={13} />
            Reject
          </button>
          <button
            onClick={() => onKeep(result.result_id)}
            className="flex items-center justify-center gap-1.5 py-2 px-3 bg-slate-700/40 hover:bg-slate-700/60 text-slate-300 border border-slate-600/40 rounded text-xs font-semibold transition-colors"
          >
            <HelpCircle size={13} />
            Keep Open
          </button>
        </div>
      </div>
    </div>
  );
}
