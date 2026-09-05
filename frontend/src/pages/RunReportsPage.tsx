import React, { useState, useEffect } from 'react';
import {
  FileBarChart2, CheckCircle, XCircle, Download, FileJson,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from 'recharts';
import { useApp } from '../store/AppContext';
import * as api from '../api/client';
import type { ReconciliationRun } from '../types';
import {
  formatCurrency,
  formatDateTime,
  formatPct,
  formatMs,
  scenarioLabel,
} from '../utils/format';

function StatRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | number;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-1 text-xs">
      <span className="text-slate-500">{label}</span>
      <span className={`${mono ? 'font-mono' : ''} text-slate-200 font-medium`}>{value}</span>
    </div>
  );
}

function AccuracyBar({ accuracy }: { accuracy: number }) {
  const pct = Math.round(accuracy * 100);
  const color = accuracy >= 0.9 ? 'bg-emerald-500' : accuracy >= 0.7 ? 'bg-amber-500' : 'bg-red-500';

  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 bg-slate-700/60 rounded-full h-1.5 overflow-hidden">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono font-medium text-slate-300 w-10 text-right">
        {pct}%
      </span>
    </div>
  );
}

export function RunReportsPage() {
  const { currentRun } = useApp();
  const [runs, setRuns] = useState<ReconciliationRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<ReconciliationRun | null>(null);

  useEffect(() => {
    api.fetchRuns().then(setRuns).catch(() => {});
  }, []);

  useEffect(() => {
    if (currentRun && !selectedRunId) {
      setSelectedRunId(currentRun.run_id);
      setActiveRun(currentRun);
    }
  }, [currentRun, selectedRunId]);

  useEffect(() => {
    if (selectedRunId) {
      api.fetchRun(selectedRunId).then(setActiveRun).catch(() => {});
    }
  }, [selectedRunId]);

  if (!activeRun && runs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <FileBarChart2 size={24} className="text-slate-600 mb-3" />
        <div className="text-slate-500 text-sm">No run reports yet. Run reconciliation first.</div>
      </div>
    );
  }

  const run = activeRun;
  const chartData =
    run?.scenario_performance?.map(sp => ({
      name: scenarioLabel(sp.scenario),
      shortName: scenarioLabel(sp.scenario).split(' ')[0],
      total: sp.total_cases,
      correct: sp.correctly_identified,
      accuracy: Math.round(sp.accuracy * 100),
    })) ?? [];

  const isBenchmark = Boolean(run?.dataset_source === 'benchmark' && run?.verified_accuracy !== null && run?.verified_accuracy !== undefined);
  const isImported = !isBenchmark;
  const matchedRecords = run
    ? Math.min(run.records_processed, Math.max(0, run.exact_matches + run.fee_matches + run.probable_matches))
    : 0;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-lg font-semibold text-slate-100">Run Report</h1>
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-medium border ${
                isBenchmark
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                  : 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
              }`}
            >
              {isBenchmark ? 'Benchmark Dataset' : 'Uploaded Dataset'}
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Comprehensive audit report and execution metrics for run {run?.run_id}.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Download buttons */}
          <a
            href={`/api/reports/export/results.csv${run?.run_id ? `?run_id=${run.run_id}` : ''}`}
            download
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded text-xs text-slate-300 font-medium transition-colors"
          >
            <Download size={13} className="text-cyan-400" />
            Results (CSV)
          </a>
          <a
            href={`/api/reports/export/exceptions.csv${run?.run_id ? `?run_id=${run.run_id}` : ''}`}
            download
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded text-xs text-slate-300 font-medium transition-colors"
          >
            <Download size={13} className="text-rose-400" />
            Exceptions (CSV)
          </a>
          <a
            href={`/api/reports/export/run_report.json${run?.run_id ? `?run_id=${run.run_id}` : ''}`}
            download
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded text-xs text-slate-300 font-medium transition-colors"
          >
            <FileJson size={13} className="text-indigo-400" />
            Report (JSON)
          </a>

          {runs.length > 1 && (
            <select
              value={selectedRunId ?? ''}
              onChange={e => setSelectedRunId(e.target.value)}
              className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-300 focus:outline-none"
            >
              {runs.map(r => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {run && (
        <>
          {/* Top Row: Run Stats & Performance Metrics */}
          <div className="grid grid-cols-3 gap-4">
            {/* Run Statistics */}
            <div className="col-span-2 bg-slate-800/40 border border-slate-700/50 rounded-lg p-5">
              <div className="text-[11px] text-slate-500 uppercase tracking-widest mb-4">
                Run Statistics
              </div>
              <div className="grid grid-cols-3 gap-6">
                <div>
                  <StatRow label="Run ID" value={run.run_id} mono />
                  <StatRow label="Timestamp" value={formatDateTime(run.timestamp)} />
                  <StatRow label="Processing Time" value={formatMs(run.processing_time_ms)} mono />
                  <StatRow label="Dataset Type" value={isImported ? 'User Uploaded' : 'Synthetic Benchmark'} />
                </div>
                <div>
                  <StatRow label="Records Processed" value={run.records_processed} />
                  <StatRow label="Matched Invoices" value={`${matchedRecords} / ${run.records_processed}`} />
                  <StatRow label="Invoices Ingested" value={run.invoices_count} />
                  <StatRow label="Settlements Ingested" value={run.settlements_count} />
                  <StatRow label="Bank Feeds" value={run.bank_transactions_count} />
                </div>
                <div>
                  <StatRow label="Exact Matches" value={run.exact_matches} />
                  <StatRow label="Fee Matches" value={run.fee_matches} />
                  <StatRow label="Probable Matches" value={run.probable_matches} />
                  <StatRow label="Human Review" value={run.human_review} />
                  <StatRow label="Unresolved" value={run.unresolved} />
                </div>
              </div>
            </div>

            {/* Performance Metrics */}
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-5">
              <div className="text-[11px] text-slate-500 uppercase tracking-widest mb-4">
                Performance Metrics
              </div>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs text-slate-500">Match Rate</span>
                    <span className="text-xs font-semibold text-emerald-400 font-mono">
                      {formatPct(run.match_rate)} ({matchedRecords}/{run.records_processed})
                    </span>
                  </div>
                  <AccuracyBar accuracy={run.match_rate} />
                </div>

                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs text-slate-500">Verified Accuracy</span>
                    {run.verified_accuracy != null ? (
                      <span className="text-xs font-semibold text-cyan-400 font-mono">
                        {formatPct(run.verified_accuracy)}
                      </span>
                    ) : (
                      <span
                        title="Ground-truth labels were not supplied for this dataset."
                        className="text-xs font-semibold text-slate-400 font-mono cursor-help"
                      >
                        N/A <span className="text-[10px] text-slate-500 font-sans">(No Ground Truth)</span>
                      </span>
                    )}
                  </div>
                  {run.verified_accuracy != null ? (
                    <AccuracyBar accuracy={run.verified_accuracy} />
                  ) : (
                    <div className="text-[10px] text-slate-500 italic">
                      Ground-truth labels were not supplied for this dataset.
                    </div>
                  )}
                </div>

                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs text-slate-500">Auto-Resolution Rate</span>
                    <span className="text-xs font-semibold text-blue-400 font-mono">
                      {formatPct(run.auto_resolution_rate)}
                    </span>
                  </div>
                  <AccuracyBar accuracy={run.auto_resolution_rate} />
                </div>

                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs text-slate-500">Precision</span>
                    {run.precision != null ? (
                      <span className="text-xs font-semibold text-emerald-300 font-mono">
                        {formatPct(run.precision)}
                      </span>
                    ) : (
                      <span
                        title="Ground-truth labels were not supplied for this dataset."
                        className="text-xs font-semibold text-slate-500 font-mono cursor-help"
                      >
                        N/A
                      </span>
                    )}
                  </div>
                  {run.precision != null && <AccuracyBar accuracy={run.precision} />}
                </div>

                <div>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs text-slate-500">Recall</span>
                    {run.recall != null ? (
                      <span className="text-xs font-semibold text-cyan-300 font-mono">
                        {formatPct(run.recall)}
                      </span>
                    ) : (
                      <span
                        title="Ground-truth labels were not supplied for this dataset."
                        className="text-xs font-semibold text-slate-500 font-mono cursor-help"
                      >
                        N/A
                      </span>
                    )}
                  </div>
                  {run.recall != null && <AccuracyBar accuracy={run.recall} />}
                </div>

                <div className="pt-3 border-t border-slate-700/50">
                  <StatRow label="Reconciled Amount" value={formatCurrency(run.reconciled_amount)} mono />
                  <StatRow label="Unresolved Amount" value={formatCurrency(run.unresolved_amount)} mono />
                </div>
              </div>
            </div>
          </div>

          {/* Middle Row: Agent Execution Trace */}
          {run.trace && run.trace.length > 0 && (
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-5">
              <div className="flex items-center justify-between mb-1">
                <div className="text-[11px] text-slate-500 uppercase tracking-widest">
                  Agent Execution Trace (LangGraph)
                </div>
                <span className="text-[10px] font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
                  Stateful Pipeline
                </span>
              </div>
              <div className="text-xs text-slate-500 mb-4">
                Real node timings and status recorded during workflow execution.
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5">
                {run.trace.map((step, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-slate-900/60 border border-slate-700/60 rounded-lg flex flex-col justify-between"
                  >
                    <div>
                      <div className="text-[10px] font-mono font-bold text-cyan-400 tracking-wider">
                        {step.node.replace(/_/g, ' ')}
                      </div>
                      <div
                        className="text-[11px] text-slate-300 font-medium mt-1 line-clamp-2"
                        title={step.message}
                      >
                        {step.message}
                      </div>
                    </div>
                    <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-500">
                      <span>DURATION</span>
                      <span className="text-emerald-400 font-semibold">
                        {formatMs(step.duration_ms)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Benchmark Evaluation Section */}
          {run.benchmark_evaluation ? (
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-5 space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <div className="text-[11px] text-slate-500 uppercase tracking-widest font-semibold">
                      Benchmark Evaluation
                    </div>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                      Isolated Ground Truth Answer Key
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">
                    Post-reconciliation verification of engine decisions against hidden benchmark ground-truth labels.
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[10px] uppercase text-slate-500 font-mono">Classification Accuracy</div>
                  <div className="text-lg font-bold font-mono text-cyan-400">
                    {formatPct(run.benchmark_evaluation.classification_accuracy)}
                  </div>
                </div>
              </div>

              {/* 8 Benchmark Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-slate-900/60 border border-slate-700/60 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                    Total Benchmark Records
                  </div>
                  <div className="text-base font-mono font-semibold text-slate-100 mt-1">
                    {run.benchmark_evaluation.total_records}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Evaluated invoices</div>
                </div>

                <div className="p-3 bg-slate-900/60 border border-slate-700/60 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                    Correct Classifications
                  </div>
                  <div className="text-base font-mono font-semibold text-emerald-400 mt-1 flex items-center gap-1.5">
                    <CheckCircle size={14} className="text-emerald-400" />
                    {run.benchmark_evaluation.correct_classifications}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Matched ground truth</div>
                </div>

                <div className="p-3 bg-slate-900/60 border border-slate-700/60 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                    Incorrect Classifications
                  </div>
                  <div className="text-base font-mono font-semibold text-rose-400 mt-1 flex items-center gap-1.5">
                    <XCircle size={14} className="text-rose-400" />
                    {run.benchmark_evaluation.incorrect_classifications}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Mismatched ground truth</div>
                </div>

                <div className="p-3 bg-slate-900/60 border border-slate-700/60 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                    Classification Accuracy
                  </div>
                  <div className="text-base font-mono font-semibold text-cyan-400 mt-1">
                    {formatPct(run.benchmark_evaluation.classification_accuracy)}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Overall decision accuracy</div>
                </div>

                <div className="p-3 bg-slate-900/60 border border-slate-700/60 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                    Precision
                  </div>
                  <div className="text-base font-mono font-semibold text-emerald-300 mt-1">
                    {formatPct(run.benchmark_evaluation.precision)}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">TP / (TP + FP)</div>
                </div>

                <div className="p-3 bg-slate-900/60 border border-slate-700/60 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                    Recall
                  </div>
                  <div className="text-base font-mono font-semibold text-cyan-300 mt-1">
                    {formatPct(run.benchmark_evaluation.recall)}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">TP / (TP + FN)</div>
                </div>

                <div className="p-3 bg-slate-900/60 border border-slate-700/60 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                    Auto-Verified Precision
                  </div>
                  <div className="text-base font-mono font-semibold text-indigo-400 mt-1">
                    {formatPct(run.benchmark_evaluation.auto_verified_precision)}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">True auto / Total auto</div>
                </div>

                <div className="p-3 bg-slate-900/60 border border-slate-700/60 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                    Incorrect Auto-Verifications
                  </div>
                  <div className="text-base font-mono font-semibold text-amber-400 mt-1">
                    {run.benchmark_evaluation.incorrect_auto_verifications}
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Exceptions marked verified</div>
                </div>
              </div>

              {/* Misclassification Table: Invoice ID | Expected | Predicted | Confidence | Status */}
              <div className="pt-2">
                <div className="flex items-center justify-between mb-2.5">
                  <div className="text-xs font-semibold text-slate-200">
                    Misclassification Audit ({run.benchmark_evaluation.misclassified_records.length})
                  </div>
                  <span className="text-[11px] text-slate-500">
                    Records where predicted classification diverged from hidden ground truth
                  </span>
                </div>

                {run.benchmark_evaluation.misclassified_records.length > 0 ? (
                  <div className="border border-slate-700/60 rounded-lg overflow-hidden">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-slate-900/80 border-b border-slate-700/60">
                          {['Invoice ID', 'Expected', 'Predicted', 'Confidence', 'Status'].map(h => (
                            <th
                              key={h}
                              className="text-left px-3.5 py-2.5 text-[10px] text-slate-400 uppercase tracking-wider font-medium"
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {run.benchmark_evaluation.misclassified_records.map(rec => (
                          <tr key={rec.invoice_id} className="hover:bg-slate-800/30 transition-colors">
                            <td className="px-3.5 py-2 font-mono text-cyan-400 font-medium">
                              {rec.invoice_id}
                            </td>
                            <td className="px-3.5 py-2 text-emerald-300 font-medium">
                              {scenarioLabel(rec.expected)}
                            </td>
                            <td className="px-3.5 py-2 text-rose-300 font-medium">
                              {scenarioLabel(rec.predicted)}
                            </td>
                            <td className="px-3.5 py-2 font-mono text-slate-300">
                              {formatPct(rec.confidence)}
                            </td>
                            <td className="px-3.5 py-2">
                              <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700">
                                {rec.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-300 text-xs flex items-center gap-2">
                    <CheckCircle size={15} className="text-emerald-400" />
                    Zero misclassifications detected. Perfect 100% benchmark classification accuracy.
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-5">
              <div className="text-[11px] text-slate-500 uppercase tracking-widest mb-1">
                Benchmark Evaluation
              </div>
              <div className="text-xs text-slate-400 mt-2 p-3 bg-slate-900/60 rounded-lg border border-slate-800">
                Ground-truth evaluation metrics (Precision, Recall, Scenario Accuracy, Misclassification Audit) are only available for pre-labeled benchmark datasets with known expected matches. For normal user-uploaded financial data, review Match Rate, Exceptions, and Evidence.
              </div>
            </div>
          )}

          {/* Scenario Breakdown / Ground Truth Performance */}
          {chartData.length > 0 && (
            <div className="bg-slate-800/40 border border-slate-700/50 rounded-lg p-5">
              <div className="text-[11px] text-slate-500 uppercase tracking-widest mb-1">
                Scenario Performance Breakdown
              </div>
              <div className="text-xs text-slate-600 mb-5">
                Accuracy measured per scenario category against benchmark labels.
              </div>

              <div className="mb-6">
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <XAxis dataKey="shortName" tick={{ fontSize: 10, fill: '#64748b' }} />
                    <YAxis tick={{ fontSize: 10, fill: '#64748b' }} domain={[0, 100]} unit="%" />
                    <Tooltip
                      contentStyle={{
                        background: '#1e293b',
                        border: '1px solid #334155',
                        borderRadius: 6,
                        fontSize: 11,
                      }}
                      formatter={(val: any) => [`${val}%`, 'Accuracy']}
                    />
                    <Bar dataKey="accuracy" radius={[2, 2, 0, 0]}>
                      {chartData.map((entry, index) => (
                        <Cell
                          key={index}
                          fill={
                            entry.accuracy >= 90
                              ? '#10b981'
                              : entry.accuracy >= 70
                              ? '#f59e0b'
                              : '#ef4444'
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-700/50">
                    {['Scenario', 'Total Cases', 'Correctly Identified', 'Accuracy'].map(h => (
                      <th
                        key={h}
                        className="text-left px-3 py-2 text-[10px] text-slate-500 uppercase tracking-widest font-medium"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {run.scenario_performance?.map(sp => (
                    <tr key={sp.scenario} className="border-b border-slate-700/30">
                      <td className="px-3 py-2.5 text-slate-300 font-medium">
                        {scenarioLabel(sp.scenario)}
                      </td>
                      <td className="px-3 py-2.5 text-slate-400 font-mono">{sp.total_cases}</td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-1.5">
                          {sp.correctly_identified === sp.total_cases ? (
                            <CheckCircle size={12} className="text-emerald-400" />
                          ) : (
                            <XCircle size={12} className="text-red-400" />
                          )}
                          <span className="font-mono text-slate-300">
                            {sp.correctly_identified}
                          </span>
                          <span className="text-slate-600">/ {sp.total_cases}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 w-48">
                        <AccuracyBar accuracy={sp.accuracy} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
