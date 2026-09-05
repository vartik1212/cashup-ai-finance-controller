// CashUP — Global Application Context

import React, { createContext, useContext, useState, useCallback } from 'react';
import type {
  DataStatusResponse,
  ReconciliationRun,
  ReconciliationResult,
  TraceStep,
  AIStatusResponse,
} from '../types';
import * as api from '../api/client';

interface AppContextType {
  dataStatus: DataStatusResponse | null;
  aiAvailable: boolean;
  aiStatus: AIStatusResponse | null;
  currentRun: ReconciliationRun | null;
  runStatus: 'idle' | 'loading' | 'running' | 'complete' | 'error';
  runError: string | null;
  results: ReconciliationResult[];
  exceptions: ReconciliationResult[];
  resultsLoaded: boolean;
  selectedResult: ReconciliationResult | null;
  currentTrace: TraceStep[];
  isWorkflowModalOpen: boolean;
  setWorkflowModalOpen: (open: boolean) => void;
  isUploadModalOpen: boolean;
  setUploadModalOpen: (open: boolean) => void;
  refreshDataStatus: () => Promise<void>;
  resetWorkspace: () => void;
  loadDemo: () => Promise<void>;
  runReconciliation: () => Promise<void>;
  loadLatestRun: () => Promise<void>;
  loadResults: (runId: string) => Promise<void>;
  loadExceptions: (runId: string) => Promise<void>;
  selectResult: (result: ReconciliationResult | null) => void;
  handleReview: (resultId: string, action: 'approve' | 'reject' | 'keep_open') => Promise<void>;
}

const AppContext = createContext<AppContextType | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [dataStatus, setDataStatus] = useState<DataStatusResponse | null>(null);
  const [aiAvailable, setAiAvailable] = useState<boolean>(false);
  const [aiStatus, setAiStatus] = useState<AIStatusResponse | null>(null);
  const [currentRun, setCurrentRun] = useState<ReconciliationRun | null>(null);
  const [runStatus, setRunStatus] = useState<'idle' | 'loading' | 'running' | 'complete' | 'error'>('idle');
  const [runError, setRunError] = useState<string | null>(null);
  const [results, setResults] = useState<ReconciliationResult[]>([]);
  const [exceptions, setExceptions] = useState<ReconciliationResult[]>([]);
  const [resultsLoaded, setResultsLoaded] = useState<boolean>(false);
  const [selectedResult, setSelectedResult] = useState<ReconciliationResult | null>(null);
  const [currentTrace, setCurrentTrace] = useState<TraceStep[]>([]);
  const [isWorkflowModalOpen, setWorkflowModalOpen] = useState<boolean>(false);
  const [isUploadModalOpen, setUploadModalOpen] = useState<boolean>(false);

  const refreshDataStatus = useCallback(async () => {
    try {
      const [status, health, ai] = await Promise.all([
        api.fetchDataStatus(),
        api.checkHealth(),
        api.fetchAiStatus().catch(() => null),
      ]);
      setDataStatus(status);
      const isAvailable = ai?.available ?? health.ai_available ?? false;
      setAiAvailable(isAvailable);
      setAiStatus(ai);
    } catch {
      // Ignored if server offline
    }
  }, []);

  const resetWorkspace = useCallback(() => {
    setCurrentRun(null);
    setCurrentTrace([]);
    setResults([]);
    setExceptions([]);
    setSelectedResult(null);
    setResultsLoaded(false);
    setRunStatus('idle');
    setRunError(null);
  }, []);

  const loadDemo = useCallback(async () => {
    resetWorkspace();
    setRunStatus('loading');
    setRunError(null);
    try {
      await api.loadDemoDataset();
      await refreshDataStatus();
      await loadLatestRun();
      setRunStatus('idle');
    } catch (e: any) {
      setRunError(e.response?.data?.detail ?? 'Failed to load demo dataset');
      setRunStatus('error');
    }
  }, [refreshDataStatus]);

  const loadResults = useCallback(async (runId: string) => {
    try {
      const data = await api.fetchRunResults(runId, { limit: 200 });
      setResults(data);
      setResultsLoaded(true);
    } catch {
      setResults([]);
    }
  }, []);

  const loadExceptions = useCallback(async (runId: string) => {
    try {
      const data = await api.fetchRunExceptions(runId);
      setExceptions(data);
    } catch {
      setExceptions([]);
    }
  }, []);

  const runReconciliation = useCallback(async () => {
    setRunStatus('running');
    setRunError(null);
    setResultsLoaded(false);
    setCurrentTrace([]);
    setWorkflowModalOpen(true);
    try {
      localStorage.removeItem('cashup_active_run_id');
      localStorage.removeItem('reconai_active_run_id');
      const res = await api.runReconciliation();
      const run = res.summary ?? res;
      setCurrentRun(run);
      if (res.trace) {
        setCurrentTrace(res.trace);
      } else if (run.trace) {
        setCurrentTrace(run.trace);
      }
      setRunStatus('complete');
      if (run.run_id) {
        await Promise.all([
          loadResults(run.run_id),
          loadExceptions(run.run_id),
          refreshDataStatus(),
        ]);
      }
    } catch (e: any) {
      setRunError(e.response?.data?.detail ?? 'Reconciliation failed');
      setRunStatus('error');
    }
  }, [loadResults, loadExceptions, refreshDataStatus]);

  const loadLatestRun = useCallback(async () => {
    try {
      localStorage.removeItem('cashup_active_run_id');
      localStorage.removeItem('reconai_active_run_id');
      const run = await api.fetchLatestRun();

      if (run && run.has_run !== false && run.run_id) {
        setCurrentRun(run);
        if (run.trace) setCurrentTrace(run.trace);
        setRunStatus('complete');
        await Promise.all([
          loadResults(run.run_id),
          loadExceptions(run.run_id),
        ]);
      } else {
        setCurrentRun(null);
        setCurrentTrace([]);
        setResults([]);
        setExceptions([]);
        setSelectedResult(null);
        setRunStatus('idle');
      }
    } catch {
      setCurrentRun(null);
      setCurrentTrace([]);
      setResults([]);
      setExceptions([]);
      setSelectedResult(null);
      setRunStatus('idle');
    }
  }, [loadResults, loadExceptions]);

  const selectResult = useCallback((result: ReconciliationResult | null) => {
    setSelectedResult(result);
  }, []);

  const handleReview = useCallback(
    async (resultId: string, action: 'approve' | 'reject' | 'keep_open') => {
      if (!currentRun) return;
      try {
        const audit = await api.submitReviewDecision(currentRun.run_id, resultId, { action });
        const newStatus = audit.new_status ?? (action === 'approve' ? 'Exact Match' : 'Human Review');
        setResults(prev =>
          prev.map(r => (r.result_id === resultId ? { ...r, status: newStatus } : r))
        );
        setExceptions(prev =>
          action === 'approve'
            ? prev.filter(r => r.result_id !== resultId)
            : prev.map(r => (r.result_id === resultId ? { ...r, status: newStatus } : r))
        );
        setSelectedResult(prev =>
          prev?.result_id === resultId ? { ...prev, status: newStatus } : prev
        );
      } catch (e) {
        console.error('Failed to submit review action', e);
      }
    },
    [currentRun]
  );

  return (
    <AppContext.Provider
      value={{
        dataStatus,
        aiAvailable,
        aiStatus,
        currentRun,
        runStatus,
        runError,
        results,
        exceptions,
        resultsLoaded,
        selectedResult,
        currentTrace,
        isWorkflowModalOpen,
        setWorkflowModalOpen,
        isUploadModalOpen,
        setUploadModalOpen,
        refreshDataStatus,
        resetWorkspace,
        loadDemo,
        runReconciliation,
        loadLatestRun,
        loadResults,
        loadExceptions,
        selectResult,
        handleReview,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}

export function useApp(): AppContextType {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
}
