"""
ReconAI — Pydantic Data Models
All financial records and reconciliation entities.
"""

from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MatchType(str, Enum):
    EXACT = "exact_match"
    FEE_ADJUSTED = "fee_adjusted"
    DELAYED = "delayed_settlement"
    PARTIAL = "partial_payment"
    REFUND = "refund"
    DUPLICATE = "duplicate"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class ReconciliationStatus(str, Enum):
    EXACT_MATCH = "Exact Match"
    FEE_MATCH = "Fee Match"
    PROBABLE_MATCH = "Probable Match"
    HUMAN_REVIEW = "Human Review"
    UNRESOLVED = "Unresolved"


class ExceptionCategory(str, Enum):
    MISSING_SETTLEMENT = "Missing Settlement"
    AMOUNT_MISMATCH = "Amount Mismatch"
    DUPLICATE = "Duplicate"
    PARTIAL_PAYMENT = "Partial Payment"
    REFUND_DISCREPANCY = "Refund Discrepancy"
    AMBIGUOUS_MATCH = "Ambiguous Match"


class Invoice(BaseModel):
    invoice_id: str
    customer_name: str
    customer_id: str
    invoice_amount: float
    invoice_date: date
    due_date: date
    currency: str = "INR"
    description: str = ""
    gstin: Optional[str] = None
    ground_truth_scenario: str
    expected_match_id: Optional[str] = None


class Settlement(BaseModel):
    settlement_id: str
    payment_id: str
    invoice_reference: Optional[str] = None
    customer_id: Optional[str] = None
    amount: float
    fee: float
    net_amount: float
    payment_date: date
    settlement_date: date
    payment_gateway: str
    utr_number: Optional[str] = None
    remarks: Optional[str] = None
    ground_truth_invoice_id: Optional[str] = None
    ground_truth_scenario: str


class BankTransaction(BaseModel):
    bank_txn_id: str
    utr_number: Optional[str] = None
    amount: float
    transaction_date: date
    value_date: date
    description: str
    bank_reference: Optional[str] = None
    settlement_reference: Optional[str] = None
    transaction_type: str
    balance: Optional[float] = None
    ground_truth_settlement_id: Optional[str] = None
    ground_truth_scenario: str


class EvidenceItem(BaseModel):
    label: str
    matched: bool
    detail: Optional[str] = None


class ReconciliationResult(BaseModel):
    result_id: str
    run_id: str
    invoice_id: str
    settlement_id: Optional[str] = None
    bank_txn_id: Optional[str] = None
    invoice_amount: float
    settlement_amount: Optional[float] = None
    bank_amount: Optional[float] = None
    difference: float
    invoice_date: date
    payment_date: Optional[date] = None
    settlement_date: Optional[date] = None
    days_delayed: Optional[int] = None
    customer_name: str
    customer_id: str
    match_type: MatchType
    status: ReconciliationStatus
    confidence_score: float
    exception_category: Optional[ExceptionCategory] = None
    evidence: List[EvidenceItem] = []
    system_assessment: str
    recommendation: str
    ground_truth_scenario: str
    is_correct_prediction: Optional[bool] = None
    processed_at: datetime


class TraceStep(BaseModel):
    node: str
    timestamp: str
    message: str
    duration_ms: float
    status: str = "completed"


class ScenarioPerformance(BaseModel):
    scenario: str
    total_cases: int
    correctly_identified: int
    accuracy: float


class MisclassifiedRecord(BaseModel):
    invoice_id: str
    expected: str
    predicted: str
    confidence: float
    status: str


class BenchmarkEvaluation(BaseModel):
    total_records: int
    correct_classifications: int
    incorrect_classifications: int
    precision: float
    recall: float
    classification_accuracy: float
    auto_verified_precision: float
    incorrect_auto_verifications: int
    misclassified_records: List[MisclassifiedRecord] = []


class ReconciliationRun(BaseModel):
    run_id: str
    timestamp: datetime
    records_processed: int
    invoices_count: int
    settlements_count: int
    bank_transactions_count: int
    exact_matches: int
    fee_matches: int
    probable_matches: int
    human_review: int
    unresolved: int
    auto_resolved: int
    open_exception_count: int = 0
    reconciled_amount: float
    unresolved_amount: float
    match_rate: float
    verified_accuracy: Optional[float] = None
    auto_resolution_rate: float
    precision: Optional[float] = None
    recall: Optional[float] = None
    processing_time_ms: float
    scenario_performance: List[ScenarioPerformance] = []
    trace: List[TraceStep] = []
    dataset_source: str = "benchmark"
    dataset_id: Optional[str] = "DATASET-BENCHMARK"
    source_metadata: Optional[Dict[str, Any]] = None
    benchmark_evaluation: Optional[BenchmarkEvaluation] = None


class ReviewAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    KEEP = "keep_open"


class ReviewDecision(BaseModel):
    action: ReviewAction
    result_id: Optional[str] = None
    actor: str = "human"
    notes: Optional[str] = None


class AuditEntry(BaseModel):
    audit_id: str
    result_id: str
    invoice_id: str
    action: ReviewAction
    previous_status: str
    new_status: str
    actor: str
    notes: Optional[str] = None
    timestamp: datetime


class LoadDemoResponse(BaseModel):
    invoices_loaded: int
    settlements_loaded: int
    bank_transactions_loaded: int
    message: str


class RunReconciliationRequest(BaseModel):
    run_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    referenced_ids: List[str] = []


class CopilotRequest(BaseModel):
    message: str
    run_id: Optional[str] = None
    conversation_history: List[ChatMessage] = []


class CopilotResponse(BaseModel):
    message: str
    ai_available: bool
    mode: str = "connected"
    model: Optional[str] = None
    referenced_ids: List[str] = []
    error: Optional[str] = None


class AIStatusResponse(BaseModel):
    available: bool
    provider: str = "Gemini"
    mode: str = "connected"
    model: Optional[str] = None


class LikelyReason(str, Enum):
    PROCESSING_FEE = "PROCESSING_FEE"
    PARTIAL_PAYMENT = "PARTIAL_PAYMENT"
    REFUND_ACTIVITY = "REFUND_ACTIVITY"
    DELAYED_SETTLEMENT = "DELAYED_SETTLEMENT"
    DUPLICATE_ACTIVITY = "DUPLICATE_ACTIVITY"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AIExceptionAnalysis(BaseModel):
    summary: str
    likely_reason: LikelyReason
    risk_level: RiskLevel
    recommended_action: str
    explanation: str
    invoice_id: Optional[str] = None
    cached: bool = False
    model: Optional[str] = None

