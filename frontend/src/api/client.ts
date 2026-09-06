// CashUP - API Client for FastAPI backend

import axios from 'axios';
import type {
  DataStatusResponse,
  ReconciliationRun,
  ReconciliationResult,
  CopilotRequest,
  CopilotResponse,
  ReviewDecision,
  AuditEntry,
  LoadDemoResponse,
  HealthResponse,
  AIStatusResponse,
  AIExceptionAnalysis,
} from '../types';

const rawBase = (import.meta as any).env?.VITE_API_URL || (import.meta as any).env?.VITE_API_BASE_URL || '/api';
const API_BASE = rawBase.replace(/\/+$/, '');

export const apiClient = axios.create({
  baseURL: API_BASE.endsWith('/api') ? API_BASE : (API_BASE === '' ? '/api' : `${API_BASE}/api`),
  timeout: 90000,
});

export async function checkHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get('/health');
  return {
    ...data,
    ai_available: data.ai_ready ?? data.ai_available ?? false,
  };
}

export async function fetchDataStatus(): Promise<DataStatusResponse> {
  const { data } = await apiClient.get('/data/status');
  return {
    ...data,
    data_loaded: (data.invoices ?? 0) > 0,
  };
}

export async function loadDemoDataset(): Promise<LoadDemoResponse> {
  const { data } = await apiClient.post('/data/load-demo', { confirm: true });
  return data;
}

export async function runReconciliation(req?: { run_id?: string }): Promise<any> {
  const { data } = await apiClient.post('/reconcile', req ?? {});
  return data;
}

export async function fetchLatestRun(): Promise<ReconciliationRun> {
  const { data } = await apiClient.get('/reconcile/latest');
  return data;
}

export async function fetchRuns(): Promise<ReconciliationRun[]> {
  const { data } = await apiClient.get('/reconcile/runs');
  return data;
}

export async function fetchRun(runId: string): Promise<ReconciliationRun> {
  const { data } = await apiClient.get(`/reconcile/runs/${runId}`);
  return data;
}

export async function fetchRunResults(
  runId: string,
  params?: Record<string, any>
): Promise<ReconciliationResult[]> {
  const { data } = await apiClient.get(`/reconcile/runs/${runId}/results`, { params });
  return data;
}

export async function fetchRunExceptions(runId: string): Promise<ReconciliationResult[]> {
  const { data } = await apiClient.get(`/reconcile/runs/${runId}/exceptions`);
  return data;
}

export async function sendCopilotMessage(req: CopilotRequest): Promise<CopilotResponse> {
  const { data } = await apiClient.post('/copilot/chat', {
    message: req.message,
    run_id: req.run_id,
    conversation_history: req.conversation_history ?? [],
  });
  return data;
}

export async function submitReviewDecision(
  runId: string,
  resultId: string,
  decision: ReviewDecision
): Promise<AuditEntry> {
  const { data } = await apiClient.post(`/reconcile/runs/${runId}/results/${resultId}/review`, {
    result_id: resultId,
    action: decision.action,
    notes: decision.notes,
    actor: decision.actor ?? 'human',
  });
  return data;
}

export async function uploadAndProfile(files: File[]): Promise<any> {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));
  const { data } = await apiClient.post('/upload/profile', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function confirmUpload(payload: any): Promise<any> {
  const { data } = await apiClient.post('/upload/confirm', payload);
  return data;
}

export function getExportResultsUrl(runId?: string): string {
  const base = apiClient.defaults.baseURL || '/api';
  return runId ? `${base}/reports/export/results.csv?run_id=${runId}` : `${base}/reports/export/results.csv`;
}

export function getExportExceptionsUrl(runId?: string): string {
  const base = apiClient.defaults.baseURL || '/api';
  return runId ? `${base}/reports/export/exceptions.csv?run_id=${runId}` : `${base}/reports/export/exceptions.csv`;
}

export function getExportRunReportUrl(runId?: string): string {
  const base = apiClient.defaults.baseURL || '/api';
  return runId ? `${base}/reports/export/run_report.json?run_id=${runId}` : `${base}/reports/export/run_report.json`;
}

export async function fetchResultByInvoice(
  invoiceId: string,
  runId?: string
): Promise<ReconciliationResult> {
  const url = runId
    ? `/reconcile/runs/${encodeURIComponent(runId)}/result/${encodeURIComponent(invoiceId)}`
    : `/reconciliation/result/${encodeURIComponent(invoiceId)}`;
  const { data } = await apiClient.get(url);
  return data;
}

export async function fetchAiStatus(): Promise<AIStatusResponse> {
  const { data } = await apiClient.get('/ai/status');
  return data;
}

export async function analyzeException(
  invoiceId: string,
  runId?: string,
  force = false
): Promise<AIExceptionAnalysis> {
  const params: Record<string, any> = {};
  if (runId) params.run_id = runId;
  if (force) params.force = force;
  const { data } = await apiClient.post(`/ai/exceptions/${encodeURIComponent(invoiceId)}/analyze`, null, { params });
  return data;
}

