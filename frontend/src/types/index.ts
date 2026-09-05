
// CashUP — Frontend TypeScript Interfaces & Types

export type ReconciliationStatus =
  | 'Exact Match'
  | 'Fee Match'
  | 'Probable Match'
  | 'Human Review'
  | 'Unresolved';

export type ExceptionCategory =
  | 'Missing Settlement'
  | 'Amount Mismatch'
  | 'Duplicate'
  | 'Partial Payment'
  | 'Refund Discrepancy'
  | 'Ambiguous Match';

export type MatchType =
  | 'exact_match'
  | 'fee_adjusted'
  | 'delayed_settlement'
  | 'partial_payment'
  | 'refund'
  | 'duplicate'
  | 'ambiguous'
  | 'unresolved';

export interface EvidenceItem {
  label: string;
  matched: boolean;
  detail: string;
}

export interface ReconciliationResult {
  result_id: string;
  run_id: string;
  invoice_id: string;
  settlement_id: string | null;
  bank_txn_id: string | null;
  invoice_amount: number;
  settlement_amount: number | null;
  bank_amount: number | null;
  difference: number;
  invoice_date: string;
  payment_date: string | null;
  settlement_date: string | null;
  days_delayed: number | null;
  customer_name: string;
  customer_id: string;
  match_type: MatchType | string;
  status: ReconciliationStatus | string;
  confidence_score: number;
  exception_category: ExceptionCategory | string | null;
  evidence: EvidenceItem[];
  system_assessment: string;
  recommendation: string;
  ground_truth_scenario: string;
  is_correct_prediction?: boolean | null;
  processed_at: string;
}

export interface ScenarioPerformance {
  scenario: string;
  total_cases: number;
  correctly_identified: number;
  accuracy: number;
}

export interface TraceStep {
  node: string;
  timestamp: string;
  message: string;
  duration_ms: number;
  status: string;
}

export interface MisclassifiedRecord {
  invoice_id: string;
  expected: string;
  predicted: string;
  confidence: number;
  status: string;
}

export interface BenchmarkEvaluation {
  total_records: number;
  correct_classifications: number;
  incorrect_classifications: number;
  precision: number;
  recall: number;
  classification_accuracy: number;
  auto_verified_precision: number;
  incorrect_auto_verifications: number;
  misclassified_records: MisclassifiedRecord[];
}

export interface ReconciliationRun {
  run_id: string;
  timestamp: string;
  records_processed: number;
  invoices_count: number;
  settlements_count: number;
  bank_transactions_count: number;
  exact_matches: number;
  fee_matches: number;
  probable_matches: number;
  human_review: number;
  unresolved: number;
  auto_resolved: number;
  open_exception_count: number;
  reconciled_amount: number;
  unresolved_amount: number;
  match_rate: number;
  verified_accuracy?: number | null;
  auto_resolution_rate: number;
  precision?: number | null;
  recall?: number | null;
  processing_time_ms: number;
  scenario_performance: ScenarioPerformance[];
  trace?: TraceStep[];
  has_run?: boolean;
  dataset_source?: 'benchmark' | 'imported' | 'uploaded';
  dataset_id?: string;
  has_ground_truth?: boolean;
  source_metadata?: any;
  benchmark_evaluation?: BenchmarkEvaluation | null;
}

export interface DataStatusResponse {
  invoices: number;
  settlements: number;
  bank_transactions: number;
  refunds?: number;
  reconciliation_runs: number;
  ready: boolean;
  data_loaded?: boolean;
  dataset_source?: 'benchmark' | 'imported' | 'uploaded';
  dataset_id?: string;
  has_ground_truth?: boolean;
  active_run_id?: string | null;
  has_active_run?: boolean;
  source_metadata?: any;
}

export interface ColumnProfile {
  column_name: string;
  index: number;
  null_count: number;
  null_percentage: number;
  sample_values: string[];
  detected_type: string;
}

export interface ColumnMappingItem {
  source_column: string;
  target_field: string | null;
  confidence: number;
  confidence_band?: 'HIGH' | 'MEDIUM' | 'LOW';
  status: string;
  reason?: string;
}

export interface CanonicalFieldDef {
  field: string;
  label: string;
  required: boolean;
}

export interface FileProfile {
  filename: string;
  error?: string;
  row_count: number;
  column_count: number;
  columns: ColumnProfile[];
  duplicate_rows: number;
  preview_rows: Record<string, any>[];
  delimiter: string;
  detected_file_type: 'INVOICES' | 'SETTLEMENTS' | 'BANK_TRANSACTIONS' | 'REFUNDS' | 'UNKNOWN';
  detection_confidence: number;
  detection_confidence_band?: 'HIGH' | 'MEDIUM' | 'LOW';
  detection_reason: string;
  detection_source: string;
  column_mappings: ColumnMappingItem[];
  canonical_schema: CanonicalFieldDef[];
  file_content_b64?: string;
}

export interface UploadProfileResponse {
  status: string;
  file_count: number;
  profiles: FileProfile[];
  available_schemas: Record<string, CanonicalFieldDef[]>;
}

export interface ConfirmUploadFileSpec {
  filename: string;
  file_type: string;
  column_mapping: Record<string, string>;
  file_content_b64: string;
}

export interface ConfirmUploadRequest {
  files: ConfirmUploadFileSpec[];
}

export interface ValidationSummary {
  filename: string;
  file_type: string;
  stats: {
    total_rows: number;
    valid_count: number;
    rejected_count: number;
    warning_count: number;
    duplicate_ids: number;
  };
  errors: string[];
  warnings: string[];
}

export interface ConfirmUploadResponse {
  status: string;
  message: string;
  summaries: ValidationSummary[];
  metadata: {
    dataset_name: string;
    imported_at: string;
    files: Array<{
      filename: string;
      file_type: string;
      rows_imported: number;
      rows_rejected: number;
      warnings_count: number;
    }>;
    total_invoices: number;
    total_settlements: number;
    total_bank_transactions: number;
  };
}

export interface HealthResponse {
  status: string;
  version: string;
  engine: string;
  ai_ready: boolean;
  ai_available?: boolean;
  timestamp: string;
}

export interface LoadDemoResponse {
  invoices_loaded: number;
  settlements_loaded: number;
  bank_transactions_loaded: number;
  message: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  referenced_ids?: string[];
  mode?: 'connected' | 'data_only' | string;
}

export interface CopilotRequest {
  message: string;
  run_id?: string;
  conversation_history?: ChatMessage[];
}

export interface CopilotResponse {
  message: string;
  ai_available: boolean;
  mode?: 'connected' | 'data_only' | string;
  referenced_ids: string[];
  error?: string | null;
}

export type ReviewAction = 'approve' | 'reject' | 'keep_open';

export interface ReviewDecision {
  action: ReviewAction;
  result_id?: string;
  actor?: string;
  notes?: string;
}

export interface AuditEntry {
  audit_id: string;
  result_id: string;
  invoice_id: string;
  action: string;
  actor: string;
  previous_status?: string;
  new_status?: string;
  notes?: string;
  timestamp: string;
}

export interface AIStatusResponse {
  available: boolean;
  provider: string;
  mode: 'connected' | 'data_only' | string;
  model?: string | null;
}

export type LikelyReason =
  | 'PROCESSING_FEE'
  | 'PARTIAL_PAYMENT'
  | 'REFUND_ACTIVITY'
  | 'DELAYED_SETTLEMENT'
  | 'DUPLICATE_ACTIVITY'
  | 'REFERENCE_MISMATCH'
  | 'AMOUNT_MISMATCH'
  | 'MISSING_SETTLEMENT'
  | 'AMBIGUOUS'
  | 'UNKNOWN';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH';

export interface AIExceptionAnalysis {
  summary: string;
  likely_reason: LikelyReason;
  risk_level: RiskLevel;
  recommended_action: string;
  explanation: string;
  invoice_id?: string;
  cached?: boolean;
  model?: string | null;
}
