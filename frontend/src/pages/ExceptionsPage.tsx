// Page 3 — Exceptions & Investigation Workbench

import React, { useState } from 'react';
import {
  AlertTriangle, Info, ChevronDown, ChevronUp, Download,
} from 'lucide-react';
import { useApp } from '../store/AppContext';
import { StatusBadge, ExceptionBadge } from '../components/ui/StatusBadge';
import { ConfidenceBar } from '../components/ui/ConfidenceBar';
import { EvidencePanel } from '../components/ui/EvidencePanel';
import { formatCurrency, formatDate } from '../utils/format';
import type { ReconciliationResult } from '../types';

const CATEGORY_TABS = [
  { key: 'all', label: 'All Exceptions' },
  { key: 'Missing Settlement', label: 'Missing Settlement' },
  { key: 'Amount Mismatch', label: 'Amount Mismatch' },
  { key: 'Duplicate', label: 'Duplicate' },
  { key: 'Partial Payment', label: 'Partial Payment' },
  { key: 'Refund Discrepancy', label: 'Refund Discrepancy' },
  { key: 'Ambiguous Match', label: 'Ambiguous Match' },
];

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  'Missing Settlement': 'Invoices with no corresponding settlement record in any source feed.',
  'Amount Mismatch': 'Settlement gross amount differs significantly from the invoice amount.',
  Duplicate: 'Multiple settlement records found referencing the identical invoice ID.',
  'Partial Payment': 'Settlement received accounts for only an installment of the full invoice amount.',
  'Refund Discrepancy': 'Settlement remarks indicate refund deduction or disputed chargeback.',
  'Ambiguous Match': 'Multiple candidate settlements exist without distinct invoice reference identifiers.',
};

function ExceptionCard({
  result,
  onSelect,
  isSelected,
}: {
  result: ReconciliationResult;
  onSelect: () => void;
  isSelected: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className={`border rounded-lg overflow-hidden transition-all ${
        isSelected
          ? 'border-cyan-500/40 bg-slate-800/60'
          : 'border-slate-700/50 bg-slate-800/30 hover:border-slate-600/60'
      }`}
    >
      <div
        className="flex items-start gap-4 p-4 cursor-pointer"
        onClick={() => {
          setExpanded(!expanded);
          onSelect();
        }}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <span className="font-mono text-sm font-semibold text-cyan-400">
              {result.invoice_id}
            </span>
            <StatusBadge status={result.status} />
            {result.exception_category && (
              <ExceptionBadge category={result.exception_category} />
            )}
          </div>
          <div className="text-xs text-slate-400 mb-3">{result.customer_name}</div>

          <div className="grid grid-cols-4 gap-3">
            <div className="bg-slate-900/60 rounded p-2.5">
              <div className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">
                Expected
              </div>
              <div className="text-sm font-mono font-semibold text-slate-200">
                {formatCurrency(result.invoice_amount)}
              </div>
            </div>
            <div className="bg-slate-900/60 rounded p-2.5">
              <div className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">
                Received
              </div>
              <div className="text-sm font-mono font-semibold text-slate-400">
                {result.settlement_amount == null ? '—' : formatCurrency(result.settlement_amount)}
              </div>
            </div>
            <div className="bg-slate-900/60 rounded p-2.5">
              <div className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">
                Difference
              </div>
              <div
                className={`text-sm font-mono font-semibold ${
                  result.difference === 0 ? 'text-emerald-400' : 'text-red-400'
                }`}
              >
                {result.difference === 0 ? '₹0' : formatCurrency(Math.abs(result.difference))}
              </div>
            </div>
            <div className="bg-slate-900/60 rounded p-2.5">
              <div className="text-[10px] text-slate-600 uppercase tracking-wider mb-1">
                Confidence
              </div>
              <div className="mt-1">
                <ConfidenceBar score={result.confidence_score} compact />
              </div>
            </div>
          </div>
        </div>

        <button className="text-slate-600 hover:text-slate-400 transition-colors mt-0.5">
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
      </div>

      {expanded && (
        <div className="border-t border-slate-700/50 px-4 py-4 bg-slate-900/30">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-2 font-semibold">
                System Assessment
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                {result.system_assessment}
              </p>
              <div className="text-[10px] text-cyan-400 uppercase tracking-wider mt-3 mb-2 font-semibold">
                Recommendation
              </div>
              <p className="text-xs text-cyan-300 leading-relaxed">
                {result.recommendation}
              </p>
            </div>
            <div>
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-2 font-semibold">
                Evidence
              </div>
              <div className="space-y-1.5">
                {result.evidence?.map((item, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <div
                      className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        item.matched ? 'bg-emerald-400' : 'bg-red-400'
                      }`}
                    />
                    <span
                      className={`text-xs ${item.matched ? 'text-slate-300' : 'text-slate-500'}`}
                    >
                      {item.label}
                    </span>
                  </div>
                ))}
              </div>
              {result.invoice_date && (
                <div className="mt-3 text-[10px] text-slate-600">
                  Invoice: {formatDate(result.invoice_date)}
                  {result.payment_date && ` · Payment: ${formatDate(result.payment_date)}`}
                </div>
              )}
            </div>
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={e => {
                e.stopPropagation();
                onSelect();
              }}
              className="px-4 py-1.5 text-xs bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-400 border border-cyan-500/30 rounded font-medium transition-colors"
            >
              Open Evidence Panel
            </button>
            <div className="text-[10px] text-slate-600">
              Low-confidence records must remain unresolved until manually verified.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function ExceptionsPage() {
  const { exceptions, currentRun, selectResult, selectedResult, handleReview } = useApp();
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  if (!currentRun) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <AlertTriangle size={24} className="text-slate-600 mb-3" />
        <div className="text-slate-500 text-sm">Run a reconciliation to see exceptions.</div>
      </div>
    );
  }

  const categoryCounts = CATEGORY_TABS.slice(1).reduce<Record<string, number>>((acc, tab) => {
    acc[tab.key] = exceptions.filter(e => e.exception_category === tab.key).length;
    return acc;
  }, {});

  const filteredExceptions =
    selectedCategory === 'all'
      ? exceptions
      : exceptions.filter(e => e.exception_category === selectedCategory);

  const unresolvedValue = exceptions
    .filter(e => e.status === 'Unresolved')
    .reduce((acc, r) => acc + r.invoice_amount, 0);

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-auto">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-start justify-between mb-6">
            <div>
              <h1 className="text-lg font-semibold text-slate-100 mb-1">
                Exceptions requiring attention
              </h1>
              <div className="flex items-center gap-6 text-sm">
                <div>
                  <span className="text-slate-500">Open Exceptions: </span>
                  <span className="text-red-400 font-semibold">
                    {currentRun.open_exception_count ?? exceptions.length}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">Unresolved: </span>
                  <span className="text-slate-300 font-semibold">{currentRun.unresolved}</span>
                </div>
                <div>
                  <span className="text-slate-500">Human Review: </span>
                  <span className="text-amber-400 font-semibold">{currentRun.human_review}</span>
                </div>
                <div>
                  <span className="text-slate-500">Unresolved Value: </span>
                  <span className="text-red-400 font-mono font-semibold">
                    {formatCurrency(unresolvedValue)}
                  </span>
                </div>
              </div>
            </div>

            <a
              href={`/api/reports/export/exceptions.csv${currentRun?.run_id ? `?run_id=${currentRun.run_id}` : ''}`}
              download
              title="Download exception items as CSV"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/80 hover:bg-slate-700 border border-slate-700 rounded text-xs text-slate-300 font-medium transition-colors"
            >
              <Download size={13} className="text-rose-400" />
              Export Exceptions (CSV)
            </a>
          </div>

          {/* Category Tabs */}
          <div className="flex items-center gap-2 flex-wrap mb-6">
            {CATEGORY_TABS.map(tab => {
              const count = tab.key === 'all' ? exceptions.length : categoryCounts[tab.key] ?? 0;
              const isActive = selectedCategory === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => setSelectedCategory(tab.key)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded border text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30'
                      : 'text-slate-500 border-slate-700 hover:border-slate-600 hover:text-slate-300'
                  }`}
                >
                  {tab.label}
                  <span className={`font-mono ${isActive ? 'text-cyan-300' : 'text-slate-600'}`}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Category Description */}
          {selectedCategory !== 'all' && CATEGORY_DESCRIPTIONS[selectedCategory] && (
            <div className="flex items-start gap-2 mb-4 px-4 py-3 bg-slate-800/30 border border-slate-700/40 rounded text-xs text-slate-400">
              <Info size={13} className="mt-0.5 flex-shrink-0 text-slate-500" />
              {CATEGORY_DESCRIPTIONS[selectedCategory]}
            </div>
          )}

          {/* Exception Cards */}
          <div className="space-y-3">
            {filteredExceptions.map(r => (
              <ExceptionCard
                key={r.result_id}
                result={r}
                isSelected={selectedResult?.result_id === r.result_id}
                onSelect={() =>
                  selectResult(selectedResult?.result_id === r.result_id ? null : r)
                }
              />
            ))}
            {filteredExceptions.length === 0 && (
              <div className="py-16 text-center text-slate-600">
                No exceptions in this category.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Drawer */}
      {selectedResult && (
        <EvidencePanel
          result={selectedResult}
          onClose={() => selectResult(null)}
          onApprove={id => handleReview(id, 'approve')}
          onReject={id => handleReview(id, 'reject')}
          onKeep={id => handleReview(id, 'keep_open')}
        />
      )}
    </div>
  );
}
