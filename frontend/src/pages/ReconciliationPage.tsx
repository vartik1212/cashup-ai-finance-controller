// Page 2 — Detailed Multi-Source Reconciliation Grid & Auditor Table

import React, { useState, useMemo } from 'react';
import { Search, X, Download, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { useApp } from '../store/AppContext';
import { StatusBadge } from '../components/ui/StatusBadge';
import { TableConfidenceBar } from '../components/ui/ConfidenceBar';
import { EvidencePanel } from '../components/ui/EvidencePanel';
import { formatCurrency, formatDate } from '../utils/format';

const STATUS_FILTERS = [
  'Exact Match',
  'Fee Match',
  'Probable Match',
  'Human Review',
  'Unresolved',
];

const CONFIDENCE_FILTERS = [
  { label: 'All', min: 0, max: 100 },
  { label: 'High (≥85%)', min: 85, max: 100 },
  { label: 'Medium (60–84%)', min: 60, max: 84 },
  { label: 'Low (<60%)', min: 0, max: 59 },
];

function FilterButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 text-xs rounded border font-medium transition-colors ${
        active
          ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30'
          : 'text-slate-500 border-slate-700 hover:border-slate-600 hover:text-slate-300'
      }`}
    >
      {label}
    </button>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <div className="text-slate-600 text-sm">No reconciliation data available.</div>
      <div className="text-slate-600 text-xs mt-1">
        Load demo dataset and run reconciliation.
      </div>
    </div>
  );
}

type SortField = 'invoice_id' | 'customer_name' | 'invoice_amount' | 'settlement_amount' | 'difference' | 'confidence_score' | 'status';

export function ReconciliationPage() {
  const { results, selectedResult, selectResult, currentRun, handleReview } = useApp();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [confFilter, setConfFilter] = useState({ min: 0, max: 100 });
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      if (sortDirection === 'asc') {
        setSortDirection('desc');
      } else {
        setSortField(null);
        setSortDirection('asc');
      }
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const filtered = useMemo(() => {
    const list = results.filter(r => {
      if (statusFilter && r.status !== statusFilter) return false;
      if (r.confidence_score < confFilter.min || r.confidence_score > confFilter.max) return false;
      if (search) {
        const q = search.toLowerCase();
        return (
          r.invoice_id.toLowerCase().includes(q) ||
          r.customer_name.toLowerCase().includes(q) ||
          (r.settlement_id ?? '').toLowerCase().includes(q)
        );
      }
      return true;
    });

    if (!sortField) return list;

    return [...list].sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];

      if (aVal == null) aVal = '';
      if (bVal == null) bVal = '';

      if (typeof aVal === 'string') {
        const cmp = (aVal as string).localeCompare(bVal as string);
        return sortDirection === 'asc' ? cmp : -cmp;
      }
      const cmp = (aVal as number) - (bVal as number);
      return sortDirection === 'asc' ? cmp : -cmp;
    });
  }, [results, search, statusFilter, confFilter, sortField, sortDirection]);

  if (!currentRun) {
    return <EmptyState />;
  }

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown size={11} className="text-slate-600 group-hover:text-slate-400 ml-1 inline" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp size={11} className="text-cyan-400 ml-1 inline" />
    ) : (
      <ArrowDown size={11} className="text-cyan-400 ml-1 inline" />
    );
  };

  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col min-w-0">
        {/* Filter bar */}
        <div className="px-5 py-3 border-b border-slate-700/60 flex items-center gap-3 flex-shrink-0">
          <div className="relative flex-1 max-w-sm">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search invoice, customer…"
              className="w-full pl-8 pr-3 py-1.5 bg-slate-800/60 border border-slate-700 rounded text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-slate-500 transition-colors"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2"
              >
                <X size={12} className="text-slate-500" />
              </button>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">Status:</span>
            <FilterButton
              label="All"
              active={!statusFilter}
              onClick={() => setStatusFilter('')}
            />
            {STATUS_FILTERS.map(st => (
              <FilterButton
                key={st}
                label={st}
                active={statusFilter === st}
                onClick={() => setStatusFilter(st === statusFilter ? '' : st)}
              />
            ))}
          </div>

          <div className="ml-auto flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">Confidence:</span>
              {CONFIDENCE_FILTERS.map(cf => (
                <FilterButton
                  key={cf.label}
                  label={cf.label}
                  active={confFilter.min === cf.min && confFilter.max === cf.max}
                  onClick={() => setConfFilter({ min: cf.min, max: cf.max })}
                />
              ))}
            </div>

            <a
              href={`/api/reports/export/results.csv${currentRun?.run_id ? `?run_id=${currentRun.run_id}` : ''}`}
              download
              title="Download reconciliation results as CSV"
              className="flex items-center gap-1.5 px-3 py-1 bg-slate-800/80 hover:bg-slate-700 border border-slate-700 rounded text-xs text-slate-300 font-medium transition-colors"
            >
              <Download size={13} className="text-cyan-400" />
              Export Results (CSV)
            </a>
          </div>

          <div className="text-xs text-slate-500 flex-shrink-0">
            {filtered.length} / {results.length}
          </div>
        </div>

        {/* Results table */}
        <div className="flex-1 overflow-auto">
          <table className="w-full text-xs min-w-[900px]">
            <thead className="sticky top-0 z-10">
              <tr className="bg-slate-900/95 border-b border-slate-700/60">
                <th
                  onClick={() => handleSort('invoice_id')}
                  className="text-left px-4 py-3 text-[10px] text-slate-500 uppercase tracking-widest font-medium whitespace-nowrap cursor-pointer hover:text-slate-300 group"
                >
                  Invoice ID {renderSortIcon('invoice_id')}
                </th>
                <th
                  onClick={() => handleSort('customer_name')}
                  className="text-left px-4 py-3 text-[10px] text-slate-500 uppercase tracking-widest font-medium whitespace-nowrap cursor-pointer hover:text-slate-300 group"
                >
                  Customer {renderSortIcon('customer_name')}
                </th>
                <th
                  onClick={() => handleSort('invoice_amount')}
                  className="text-left px-4 py-3 text-[10px] text-slate-500 uppercase tracking-widest font-medium whitespace-nowrap cursor-pointer hover:text-slate-300 group"
                >
                  Invoice Amt {renderSortIcon('invoice_amount')}
                </th>
                <th
                  onClick={() => handleSort('settlement_amount')}
                  className="text-left px-4 py-3 text-[10px] text-slate-500 uppercase tracking-widest font-medium whitespace-nowrap cursor-pointer hover:text-slate-300 group"
                >
                  Settlement Amt {renderSortIcon('settlement_amount')}
                </th>
                <th
                  onClick={() => handleSort('difference')}
                  className="text-left px-4 py-3 text-[10px] text-slate-500 uppercase tracking-widest font-medium whitespace-nowrap cursor-pointer hover:text-slate-300 group"
                >
                  Difference {renderSortIcon('difference')}
                </th>
                <th className="text-left px-4 py-3 text-[10px] text-slate-500 uppercase tracking-widest font-medium whitespace-nowrap">
                  Payment Date
                </th>
                <th className="text-left px-4 py-3 text-[10px] text-slate-500 uppercase tracking-widest font-medium whitespace-nowrap">
                  Settlement Date
                </th>
                <th
                  onClick={() => handleSort('confidence_score')}
                  className="text-left px-4 py-3 text-[10px] text-slate-500 uppercase tracking-widest font-medium whitespace-nowrap cursor-pointer hover:text-slate-300 group"
                >
                  Confidence {renderSortIcon('confidence_score')}
                </th>
                <th className="text-left px-4 py-3 text-[10px] text-slate-500 uppercase tracking-widest font-medium whitespace-nowrap">
                  Match Type
                </th>
                <th
                  onClick={() => handleSort('status')}
                  className="text-left px-4 py-3 text-[10px] text-slate-500 uppercase tracking-widest font-medium whitespace-nowrap cursor-pointer hover:text-slate-300 group"
                >
                  Status {renderSortIcon('status')}
                </th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => {
                const isSelected = selectedResult?.result_id === r.result_id;
                const diffColor =
                  r.difference === 0
                    ? 'text-emerald-400'
                    : Math.abs(r.difference) > 0
                    ? 'text-amber-400'
                    : 'text-slate-400';

                return (
                  <tr
                    key={r.result_id}
                    onClick={() => selectResult(isSelected ? null : r)}
                    className={`border-b border-slate-700/30 cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-cyan-500/8 border-l-2 border-l-cyan-500'
                        : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <td className="px-4 py-3 font-mono text-cyan-400 font-medium">
                      {r.invoice_id}
                    </td>
                    <td className="px-4 py-3 text-slate-300 max-w-[140px]">
                      <div className="truncate">{r.customer_name}</div>
                      <div className="text-[10px] text-slate-600">{r.customer_id}</div>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-200">
                      {formatCurrency(r.invoice_amount)}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-400">
                      {r.settlement_amount == null ? (
                        <span className="text-slate-700">—</span>
                      ) : (
                        formatCurrency(r.settlement_amount)
                      )}
                    </td>
                    <td className={`px-4 py-3 font-mono ${diffColor}`}>
                      {r.difference === 0 ? '₹0' : formatCurrency(Math.abs(r.difference))}
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {r.payment_date ? (
                        formatDate(r.payment_date)
                      ) : (
                        <span className="text-slate-700">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {r.settlement_date ? (
                        formatDate(r.settlement_date)
                      ) : (
                        <span className="text-slate-700">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <TableConfidenceBar score={r.confidence_score} />
                    </td>
                    <td className="px-4 py-3 text-slate-500 capitalize">
                      {r.match_type.replace(/_/g, ' ')}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={r.status} />
                    </td>
                  </tr>
                );
              })}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-4 py-12 text-center text-slate-600 text-sm">
                    No records match the current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
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
