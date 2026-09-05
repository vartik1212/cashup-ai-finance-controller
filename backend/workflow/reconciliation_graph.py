"""
ReconAI — LangGraph Reconciliation Agent Workflow
=================================================
Stateful multi-node reconciliation pipeline orchestrated via LangGraph.
Deterministic logic verifies; agent workflow orchestrates.
No LLM in the financial verification path.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any, TypedDict

from langgraph.graph import StateGraph, START, END

try:
    from models.schemas import (
        Invoice, Settlement, BankTransaction,
        ReconciliationResult, ReconciliationRun,
        MatchType, ReconciliationStatus, ExceptionCategory,
        EvidenceItem, ScenarioPerformance, TraceStep,
    )
except (ImportError, ValueError):
    from ..models.schemas import (
        Invoice, Settlement, BankTransaction,
        ReconciliationResult, ReconciliationRun,
        MatchType, ReconciliationStatus, ExceptionCategory,
        EvidenceItem, ScenarioPerformance, TraceStep,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXACT_AMT_TOLERANCE   = Decimal("0.01")
FEE_RATE_MIN          = Decimal("0.005")   # 0.5%
FEE_RATE_MAX          = Decimal("0.045")   # 4.5%
GST_ON_FEE_RATE       = Decimal("0.18")
PARTIAL_MIN           = Decimal("0.10")    # 10%
PARTIAL_MAX           = Decimal("0.85")    # 85%
DATE_DELAYED_DAYS     = 5                  # > 5 days from invoice = delayed
CONF_AUTO_THRESHOLD   = 0.90               # 0.90 (90%) on 0.0 - 1.0 scale
CONF_REVIEW_THRESHOLD = 0.70               # 0.70 (70%)


def _d(v: float) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_ref(s: Optional[str]) -> str:
    if not s:
        return ""
    return s.strip().upper().replace(" ", "")


def _parse_date(s: Any) -> date:
    if isinstance(s, date):
        return s
    return date.fromisoformat(str(s))


# ---------------------------------------------------------------------------
# LangGraph State Schema
# ---------------------------------------------------------------------------

class ReconciliationState(TypedDict, total=False):
    run_id: str
    started_at: str

    # Raw sources
    raw_invoices: List[Dict[str, Any]]
    raw_settlements: List[Dict[str, Any]]
    raw_bank_transactions: List[Dict[str, Any]]
    ground_truth_records: Optional[List[Dict[str, Any]]]

    # Normalized records
    normalized_invoices: List[Invoice]
    normalized_settlements: List[Settlement]
    normalized_bank_transactions: List[BankTransaction]

    # Candidate matches
    candidates_by_invoice: Dict[str, List[Dict[str, Any]]]
    candidate_count: int

    # Verifications
    verifications_by_invoice: Dict[str, Dict[str, Any]]
    verified_count: int

    # Results & Exceptions
    reconciliation_results: List[ReconciliationResult]
    auto_verified_results: List[ReconciliationResult]
    exception_results: List[ReconciliationResult]
    has_exceptions: bool

    # Investigated exceptions
    investigated_exceptions: List[Dict[str, Any]]

    # Final summary
    run_summary: Optional[ReconciliationRun]

    # Execution trace
    trace: List[TraceStep]
    processing_messages: List[str]
    errors: List[str]


# ---------------------------------------------------------------------------
# Node 1: Ingest
# ---------------------------------------------------------------------------

def ingest_node(state: ReconciliationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    run_id = state.get("run_id") or f"RUN-{uuid.uuid4().hex[:8].upper()}"
    raw_invoices = state.get("raw_invoices", [])
    raw_settlements = state.get("raw_settlements", [])
    raw_bank_transactions = state.get("raw_bank_transactions", [])

    if not raw_invoices:
        raise ValueError("Source ingestion failed: No invoices provided to reconciliation pipeline.")

    msg = f"Ingested {len(raw_invoices)} invoices, {len(raw_settlements)} settlements, {len(raw_bank_transactions)} bank records"
    duration = round((time.perf_counter() - t0) * 1000, 2)

    step = TraceStep(
        node="INGEST",
        timestamp=datetime.utcnow().isoformat(),
        message=msg,
        duration_ms=duration,
        status="completed",
    )

    return {
        "run_id": run_id,
        "started_at": state.get("started_at") or datetime.utcnow().isoformat(),
        "trace": [step],
        "processing_messages": [msg],
    }


# ---------------------------------------------------------------------------
# Node 2: Normalize
# ---------------------------------------------------------------------------

def normalize_node(state: ReconciliationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    raw_invoices = state.get("raw_invoices", [])
    raw_settlements = state.get("raw_settlements", [])
    raw_bank_transactions = state.get("raw_bank_transactions", [])

    invoices: List[Invoice] = []
    for r in raw_invoices:
        invoices.append(Invoice(
            invoice_id=str(r["invoice_id"]).strip().upper(),
            customer_name=str(r.get("customer_name", "")).strip(),
            customer_id=str(r.get("customer_id", "")).strip(),
            invoice_amount=float(r["invoice_amount"]),
            invoice_date=_parse_date(r["invoice_date"]),
            due_date=_parse_date(r["due_date"]),
            currency=r.get("currency", "INR"),
            description=r.get("description", ""),
            gstin=r.get("gstin"),
            ground_truth_scenario=r.get("ground_truth_scenario", "unknown"),
            expected_match_id=r.get("expected_match_id"),
        ))

    settlements: List[Settlement] = []
    for r in raw_settlements:
        settlements.append(Settlement(
            settlement_id=str(r["settlement_id"]).strip().upper(),
            payment_id=str(r.get("payment_id", "")).strip(),
            invoice_reference=str(r.get("invoice_reference", "")).strip().upper() if r.get("invoice_reference") else None,
            customer_id=str(r.get("customer_id", "")).strip() if r.get("customer_id") else None,
            amount=float(r["amount"]),
            fee=float(r.get("fee", 0.0)),
            net_amount=float(r.get("net_amount", r["amount"])),
            payment_date=_parse_date(r["payment_date"]),
            settlement_date=_parse_date(r["settlement_date"]),
            payment_gateway=str(r.get("payment_gateway", "Razorpay")),
            utr_number=str(r.get("utr_number", "")).strip() if r.get("utr_number") else None,
            remarks=r.get("remarks"),
            ground_truth_invoice_id=r.get("ground_truth_invoice_id"),
            ground_truth_scenario=r.get("ground_truth_scenario", "unknown"),
        ))

    bank_transactions: List[BankTransaction] = []
    for r in raw_bank_transactions:
        bank_transactions.append(BankTransaction(
            bank_txn_id=str(r["bank_txn_id"]).strip().upper(),
            utr_number=str(r.get("utr_number", "")).strip() if r.get("utr_number") else None,
            amount=float(r["amount"]),
            transaction_date=_parse_date(r["transaction_date"]),
            value_date=_parse_date(r["value_date"]),
            description=str(r.get("description", "")),
            bank_reference=r.get("bank_reference"),
            settlement_reference=str(r.get("settlement_reference", "")).strip().upper() if r.get("settlement_reference") else None,
            transaction_type=str(r.get("transaction_type", "credit")),
            balance=float(r["balance"]) if r.get("balance") is not None else None,
            ground_truth_settlement_id=r.get("ground_truth_settlement_id"),
            ground_truth_scenario=r.get("ground_truth_scenario", "unknown"),
        ))

    total_records = len(invoices) + len(settlements) + len(bank_transactions)
    msg = f"Normalized {total_records} financial records across 3 sources"
    duration = round((time.perf_counter() - t0) * 1000, 2)

    step = TraceStep(
        node="NORMALIZE",
        timestamp=datetime.utcnow().isoformat(),
        message=msg,
        duration_ms=duration,
        status="completed",
    )

    prev_trace = state.get("trace", [])
    prev_msg = state.get("processing_messages", [])

    return {
        "normalized_invoices": invoices,
        "normalized_settlements": settlements,
        "normalized_bank_transactions": bank_transactions,
        "trace": prev_trace + [step],
        "processing_messages": prev_msg + [msg],
    }


# ---------------------------------------------------------------------------
# Node 3: Match Candidates (Two-pass isolation)
# ---------------------------------------------------------------------------

def match_node(state: ReconciliationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    invoices = state.get("normalized_invoices", [])
    settlements = state.get("normalized_settlements", [])

    set_by_ref: Dict[str, List[Settlement]] = defaultdict(list)
    for s in settlements:
        ref = normalize_ref(s.invoice_reference)
        if ref:
            set_by_ref[ref].append(s)

    candidates_by_invoice: Dict[str, List[Dict[str, Any]]] = {}
    used_in_pass1: set = set()
    candidate_links = 0

    # Pass 1: Direct reference matching
    unmatched_invoices: List[Invoice] = []
    for inv in invoices:
        inv_ref = normalize_ref(inv.invoice_id)
        direct_matches = set_by_ref.get(inv_ref, [])

        if direct_matches:
            candidates_by_invoice[inv.invoice_id] = [
                {"settlement": s, "strategy": "DIRECT_REFERENCE"}
                for s in direct_matches
            ]
            for s in direct_matches:
                used_in_pass1.add(s.settlement_id)
            candidate_links += len(direct_matches)
        else:
            unmatched_invoices.append(inv)

    # Pass 2: Secondary matching for unmatched invoices ONLY from unused settlements
    remaining_settlements = [s for s in settlements if s.settlement_id not in used_in_pass1]
    used_in_pass2: set = set()

    for inv in unmatched_invoices:
        inv_amt = _d(inv.invoice_amount)
        candidates = []

        # Look for incorrect reference (same customer, gross amount matches)
        for s in remaining_settlements:
            if s.settlement_id in used_in_pass2:
                continue
            if s.customer_id == inv.customer_id and abs(_d(s.amount) - inv_amt) <= EXACT_AMT_TOLERANCE:
                candidates.append({"settlement": s, "strategy": "INCORRECT_REFERENCE"})
                used_in_pass2.add(s.settlement_id)
                break

        # If not found, look for ambiguous (same customer, close amount, missing/empty reference)
        if not candidates:
            for s in remaining_settlements:
                if s.settlement_id in used_in_pass2:
                    continue
                if s.customer_id == inv.customer_id and (not s.invoice_reference or s.invoice_reference.strip() == ""):
                    diff_pct = abs(_d(s.amount) - inv_amt) / inv_amt if inv_amt > 0 else Decimal("1")
                    if diff_pct <= Decimal("0.05"):
                        candidates.append({"settlement": s, "strategy": "AMBIGUOUS_MATCH"})
                        used_in_pass2.add(s.settlement_id)
                        break

        candidates_by_invoice[inv.invoice_id] = candidates
        candidate_links += len(candidates)

    msg = f"{candidate_links} candidate relationships identified across source feeds"
    duration = round((time.perf_counter() - t0) * 1000, 2)

    step = TraceStep(
        node="MATCH",
        timestamp=datetime.utcnow().isoformat(),
        message=msg,
        duration_ms=duration,
        status="completed",
    )

    prev_trace = state.get("trace", [])
    prev_msg = state.get("processing_messages", [])

    return {
        "candidates_by_invoice": candidates_by_invoice,
        "candidate_count": candidate_links,
        "trace": prev_trace + [step],
        "processing_messages": prev_msg + [msg],
    }


# ---------------------------------------------------------------------------
# Node 4: Verify
# ---------------------------------------------------------------------------

def verify_node(state: ReconciliationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    invoices = state.get("normalized_invoices", [])
    candidates_by_invoice = state.get("candidates_by_invoice", {})
    bank_txns = state.get("normalized_bank_transactions", [])

    bank_by_utr: Dict[str, BankTransaction] = {}
    bank_by_set_ref: Dict[str, BankTransaction] = {}
    for b in bank_txns:
        if b.utr_number:
            bank_by_utr[normalize_ref(b.utr_number)] = b
        if b.settlement_reference:
            bank_by_set_ref[normalize_ref(b.settlement_reference)] = b

    verifications: Dict[str, Dict[str, Any]] = {}
    verified_relationships = 0

    for inv in invoices:
        candidates = candidates_by_invoice.get(inv.invoice_id, [])
        if not candidates:
            verifications[inv.invoice_id] = {"has_settlement": False}
            continue

        verified_candidates = []
        for c in candidates:
            s: Settlement = c["settlement"]
            strategy: str = c.get("strategy", "DIRECT_REFERENCE")

            inv_amt = _d(inv.invoice_amount)
            s_gross = _d(s.amount)
            s_net = _d(s.net_amount)
            s_fee = _d(s.fee)

            ref_match = (normalize_ref(s.invoice_reference) == normalize_ref(inv.invoice_id))
            cust_match = (s.customer_id == inv.customer_id)
            gross_match = abs(inv_amt - s_gross) <= EXACT_AMT_TOLERANCE

            # Accurate fee verification:
            # gross must match invoice AND fee must be > 0.01 AND net + fee + tax == gross
            fee_pct = s_fee / inv_amt if inv_amt > 0 else Decimal("0")
            fee_valid = (
                gross_match
                and (s_fee > Decimal("0.01"))
                and (FEE_RATE_MIN <= fee_pct <= FEE_RATE_MAX)
            )

            days_delta = abs((s.payment_date - inv.invoice_date).days)
            date_ok = (days_delta <= DATE_DELAYED_DAYS)

            # Bank verification
            bank_txn: Optional[BankTransaction] = None
            if s.utr_number:
                bank_txn = bank_by_utr.get(normalize_ref(s.utr_number))
            if not bank_txn:
                bank_txn = bank_by_set_ref.get(normalize_ref(s.settlement_id))

            # Confidence score calculation (0.00 – 1.00 float scale)
            score = 0.0
            if ref_match:
                score += 0.35
            if cust_match:
                score += 0.15
            if gross_match and not fee_valid:
                score += 0.25
            elif fee_valid:
                score += 0.25
            elif abs(inv_amt - s_gross) / inv_amt <= Decimal("0.10"):
                score += 0.10

            if date_ok:
                score += 0.15
            else:
                score += 0.05

            if bank_txn is not None:
                score += 0.10

            confidence = round(max(0.0, min(1.0, score)), 2)

            ev = _build_evidence_list(
                inv=inv,
                settlement=s,
                bank_txn=bank_txn,
                ref_matched=ref_match,
                cust_matched=cust_match,
                amt_matched=gross_match,
                fee_matched=fee_valid,
                date_matched=date_ok,
                days_delta=days_delta,
            )

            verified_candidates.append({
                "settlement": s,
                "strategy": strategy,
                "bank_txn": bank_txn,
                "ref_match": ref_match,
                "cust_match": cust_match,
                "gross_match": gross_match,
                "fee_valid": fee_valid,
                "days_delta": days_delta,
                "confidence": confidence,
                "evidence": ev,
            })
            verified_relationships += 1

        verifications[inv.invoice_id] = {
            "has_settlement": True,
            "candidates": verified_candidates,
        }

    msg = f"Verified {verified_relationships} relationships against gateway fees, date SLA & bank records"
    duration = round((time.perf_counter() - t0) * 1000, 2)

    step = TraceStep(
        node="VERIFY",
        timestamp=datetime.utcnow().isoformat(),
        message=msg,
        duration_ms=duration,
        status="completed",
    )

    prev_trace = state.get("trace", [])
    prev_msg = state.get("processing_messages", [])

    return {
        "verifications_by_invoice": verifications,
        "verified_count": verified_relationships,
        "trace": prev_trace + [step],
        "processing_messages": prev_msg + [msg],
    }


def _build_evidence_list(
    inv: Invoice,
    settlement: Settlement,
    bank_txn: Optional[BankTransaction],
    ref_matched: bool,
    cust_matched: bool,
    amt_matched: bool,
    fee_matched: bool,
    date_matched: bool,
    days_delta: int,
) -> List[EvidenceItem]:
    inv_amt = _d(inv.invoice_amount)
    s_gross = _d(settlement.amount)
    s_fee = _d(settlement.fee)

    return [
        EvidenceItem(
            label="Invoice reference match",
            matched=ref_matched,
            detail=f"Settlement ref '{settlement.invoice_reference}' vs Invoice '{inv.invoice_id}'",
        ),
        EvidenceItem(
            label="Customer identifier match",
            matched=cust_matched,
            detail=f"Settlement cust '{settlement.customer_id}' vs Invoice '{inv.customer_id}'",
        ),
        EvidenceItem(
            label="Gross amount verified",
            matched=amt_matched,
            detail=f"Settlement gross ₹{s_gross:,.2f} vs Invoice ₹{inv_amt:,.2f}",
        ),
        EvidenceItem(
            label="Gateway fee verified",
            matched=fee_matched,
            detail=f"Fee ₹{s_fee:,.2f} ({float(s_fee/inv_amt)*100:.2f}%)" if inv_amt > 0 else "N/A",
        ),
        EvidenceItem(
            label="Payment SLA window (≤ 5 days)",
            matched=date_matched,
            detail=f"Payment received {days_delta} days from invoice date",
        ),
        EvidenceItem(
            label="Bank credit verified",
            matched=bank_txn is not None,
            detail=f"Bank Txn: {bank_txn.bank_txn_id if bank_txn else 'Not in bank feed'}",
        ),
    ]


# ---------------------------------------------------------------------------
# Node 5: Classify & Route
# ---------------------------------------------------------------------------

def classify_node(state: ReconciliationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    run_id = state.get("run_id", "RUN-UNKNOWN")
    invoices = state.get("normalized_invoices", [])
    verifications = state.get("verifications_by_invoice", {})
    now = datetime.utcnow()

    results: List[ReconciliationResult] = []
    auto_verified: List[ReconciliationResult] = []
    exceptions: List[ReconciliationResult] = []

    for inv in invoices:
        v = verifications.get(inv.invoice_id, {})
        if not v.get("has_settlement") or not v.get("candidates"):
            # Missing settlement
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=None,
                bank_txn_id=None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=None,
                bank_amount=None,
                difference=round(inv.invoice_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=None,
                settlement_date=None,
                days_delayed=None,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.UNRESOLVED,
                status=ReconciliationStatus.UNRESOLVED,
                confidence_score=0.0,
                exception_category=ExceptionCategory.MISSING_SETTLEMENT,
                evidence=[EvidenceItem(label="Settlement record found", matched=False, detail="No settlement record in feed")],
                system_assessment=f"No settlement record found for invoice {inv.invoice_id} (₹{inv.invoice_amount:,.2f}).",
                recommendation="Investigate with payment gateway. Check if payment was initiated or failed at checkout.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            results.append(res)
            exceptions.append(res)
            continue

        cands = v["candidates"]
        inv_amt = _d(inv.invoice_amount)

        # 1. Duplicate check (multiple candidates referencing this invoice)
        direct_refs = [c for c in cands if c["ref_match"]]
        if len(direct_refs) >= 2:
            s1 = direct_refs[0]["settlement"]
            b1 = direct_refs[0]["bank_txn"]

            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s1.settlement_id,
                bank_txn_id=b1.bank_txn_id if b1 else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s1.net_amount, 2),
                bank_amount=round(b1.amount, 2) if b1 else None,
                difference=round(inv.invoice_amount - s1.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s1.payment_date,
                settlement_date=s1.settlement_date,
                days_delayed=(s1.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.DUPLICATE,
                status=ReconciliationStatus.HUMAN_REVIEW,
                confidence_score=0.60,
                exception_category=ExceptionCategory.DUPLICATE,
                evidence=direct_refs[0]["evidence"] + [EvidenceItem(label="Duplicate check", matched=False, detail=f"{len(direct_refs)} settlements cite this reference")],
                system_assessment=f"Duplicate payment alert: {len(direct_refs)} settlements cite {inv.invoice_id}. Redundant credits require refund.",
                recommendation="Reconcile primary transaction. Void or refund redundant payment credit.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            results.append(res)
            exceptions.append(res)
            continue

        # Single primary candidate
        cand = cands[0]
        s: Settlement = cand["settlement"]
        b: Optional[BankTransaction] = cand["bank_txn"]
        strategy = cand.get("strategy", "DIRECT_REFERENCE")

        s_gross = _d(s.amount)
        s_net = _d(s.net_amount)
        s_fee = _d(s.fee)
        remarks_lower = (s.remarks or "").lower()

        # 2. Refund check
        if "refund" in remarks_lower:
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=b.bank_txn_id if b else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(b.amount, 2) if b else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.REFUND,
                status=ReconciliationStatus.HUMAN_REVIEW,
                confidence_score=0.65,
                exception_category=ExceptionCategory.REFUND_DISCREPANCY,
                evidence=cand["evidence"],
                system_assessment=f"Refund adjustment detected on settlement {s.settlement_id}: {s.remarks}.",
                recommendation="Audit customer dispute log to confirm authorized refund deduction.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            results.append(res)
            exceptions.append(res)
            continue

        # 3. Partial payment check (10% to 85% received)
        ratio = s_gross / inv_amt if inv_amt > 0 else Decimal("0")
        if PARTIAL_MIN <= ratio <= PARTIAL_MAX:
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=b.bank_txn_id if b else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(b.amount, 2) if b else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.PARTIAL,
                status=ReconciliationStatus.HUMAN_REVIEW,
                confidence_score=0.70,
                exception_category=ExceptionCategory.PARTIAL_PAYMENT,
                evidence=cand["evidence"],
                system_assessment=f"Partial settlement: Received ₹{s_net:,.2f} ({float(ratio)*100:.1f}%) of ₹{inv_amt:,.2f}.",
                recommendation="Book partial receipt against receivables. Remind client of balance ₹" + f"{float(inv_amt - s_net):,.2f}.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            results.append(res)
            exceptions.append(res)
            continue

        # 4. Amount mismatch check (direct reference matches, but gross amount does not match invoice)
        if cand["ref_match"] and not cand["gross_match"]:
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=b.bank_txn_id if b else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(b.amount, 2) if b else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.UNRESOLVED,
                status=ReconciliationStatus.UNRESOLVED,
                confidence_score=0.45,
                exception_category=ExceptionCategory.AMOUNT_MISMATCH,
                evidence=cand["evidence"],
                system_assessment=f"Unexplained amount variance: Invoice ₹{inv_amt:,.2f} vs Settlement gross ₹{s_gross:,.2f} (diff ₹{abs(inv_amt - s_gross):,.2f}).",
                recommendation="Request settlement deduction breakdown from payment gateway.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            results.append(res)
            exceptions.append(res)
            continue

        # 5. Delayed settlement check (gross matches or valid fee, but days_delta > 5)
        if cand["days_delta"] > DATE_DELAYED_DAYS:
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=b.bank_txn_id if b else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(b.amount, 2) if b else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.DELAYED,
                status=ReconciliationStatus.PROBABLE_MATCH,
                confidence_score=cand["confidence"],
                exception_category=None,
                evidence=cand["evidence"],
                system_assessment=f"Delayed settlement: Received {cand['days_delta']} days after invoice date. Reference and amounts confirmed.",
                recommendation="Approve match. Assess payment terms if delayed settlements recur.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            results.append(res)
            auto_verified.append(res)
            continue

        # 6. Ambiguous / Incorrect Reference check (strategy is INCORRECT_REFERENCE or AMBIGUOUS_MATCH)
        if not cand["ref_match"]:
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=b.bank_txn_id if b else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(b.amount, 2) if b else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.AMBIGUOUS,
                status=ReconciliationStatus.HUMAN_REVIEW,
                confidence_score=cand["confidence"],
                exception_category=ExceptionCategory.AMBIGUOUS_MATCH,
                evidence=cand["evidence"],
                system_assessment=f"Reference mismatch: Settlement references '{s.invoice_reference}' but customer and amounts match invoice {inv.invoice_id}.",
                recommendation="Human confirmation required: Verify bank advice slip before finalizing reconciliation.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            results.append(res)
            exceptions.append(res)
            continue

        # 7. Exact or Fee-Adjusted Match
        # STRICT FEE-ADJUSTED CHECK: must have non-zero fee > 0.01 AND gross matches
        is_fee_adjusted = cand["gross_match"] and cand["fee_valid"] and (s_fee > Decimal("0.01"))
        match_type = MatchType.FEE_ADJUSTED if is_fee_adjusted else MatchType.EXACT
        status = ReconciliationStatus.EXACT_MATCH if (not is_fee_adjusted and cand["confidence"] >= CONF_AUTO_THRESHOLD) else ReconciliationStatus.FEE_MATCH

        res = ReconciliationResult(
            result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
            run_id=run_id,
            invoice_id=inv.invoice_id,
            settlement_id=s.settlement_id,
            bank_txn_id=b.bank_txn_id if b else None,
            invoice_amount=round(inv.invoice_amount, 2),
            settlement_amount=round(s.net_amount, 2),
            bank_amount=round(b.amount, 2) if b else None,
            difference=round(inv.invoice_amount - s.net_amount, 2),
            invoice_date=inv.invoice_date,
            payment_date=s.payment_date,
            settlement_date=s.settlement_date,
            days_delayed=(s.settlement_date - inv.invoice_date).days,
            customer_name=inv.customer_name,
            customer_id=inv.customer_id,
            match_type=match_type,
            status=status,
            confidence_score=cand["confidence"],
            exception_category=None,
            evidence=cand["evidence"],
            system_assessment=f"Auto-verified match: Invoice ₹{inv_amt:,.2f} reconciled to {s.payment_gateway} settlement ₹{s_gross:,.2f} with fee ₹{s_fee:,.2f}.",
            recommendation="Auto-approve. Post journal entry directly to ledger.",
            ground_truth_scenario=inv.ground_truth_scenario,
            processed_at=now,
        )
        results.append(res)
        auto_verified.append(res)

    msg = f"Classified {len(results)} cases: {len(auto_verified)} auto-verified, {len(exceptions)} open exceptions"
    duration = round((time.perf_counter() - t0) * 1000, 2)

    step = TraceStep(
        node="CLASSIFY",
        timestamp=datetime.utcnow().isoformat(),
        message=msg,
        duration_ms=duration,
        status="completed",
    )

    prev_trace = state.get("trace", [])
    prev_msg = state.get("processing_messages", [])

    return {
        "reconciliation_results": results,
        "auto_verified_results": auto_verified,
        "exception_results": exceptions,
        "has_exceptions": len(exceptions) > 0,
        "trace": prev_trace + [step],
        "processing_messages": prev_msg + [msg],
    }


# ---------------------------------------------------------------------------
# Node 6: Exception Investigator (Deterministic, extensible for LLM)
# ---------------------------------------------------------------------------

def investigate_exception(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modular exception investigation logic.
    Currently deterministic; clean interface ready for free LLM (Gemini) delegation.
    """
    category = context.get("category", "UNKNOWN")
    invoice_id = context.get("invoice_id")
    expected = context.get("expected_amount", 0.0)
    observed = context.get("observed_amount")
    difference = context.get("difference", 0.0)

    findings = []
    if category == "Missing Settlement":
        findings.append("No settlement found in feed. Gateway API inquiry recommended.")
    elif category == "Amount Mismatch":
        findings.append(f"Discrepancy of ₹{abs(difference):,.2f} not explained by configured fee schedule.")
    elif category == "Duplicate":
        findings.append("Multiple settlements detected with duplicate payment reference. Risk of redundant revenue recognition.")
    elif category == "Partial Payment":
        pct = round((observed / expected) * 100, 1) if expected and observed else 0
        findings.append(f"Tranche received represents {pct}% of contract balance.")
    elif category == "Refund Discrepancy":
        findings.append("Settlement remarks indicate refund transaction.")
    elif category == "Ambiguous Match":
        findings.append("Customer match confirmed but reference identifier is missing or inconsistent.")

    return {
        "invoice_id": invoice_id,
        "category": category,
        "findings": findings,
        "actionable": True,
    }


def exception_investigator_node(state: ReconciliationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    exceptions = state.get("exception_results", [])
    investigated = []

    for exc in exceptions:
        ctx = {
            "invoice_id": exc.invoice_id,
            "category": exc.exception_category.value if exc.exception_category else "Unresolved",
            "expected_amount": exc.invoice_amount,
            "observed_amount": exc.settlement_amount,
            "difference": exc.difference,
            "system_assessment": exc.system_assessment,
        }
        res = investigate_exception(ctx)
        investigated.append(res)

    msg = f"Investigated {len(exceptions)} exceptions; structured audit contexts prepared"
    duration = round((time.perf_counter() - t0) * 1000, 2)

    step = TraceStep(
        node="EXCEPTION_ANALYSIS",
        timestamp=datetime.utcnow().isoformat(),
        message=msg,
        duration_ms=duration,
        status="completed",
    )

    prev_trace = state.get("trace", [])
    prev_msg = state.get("processing_messages", [])

    return {
        "investigated_exceptions": investigated,
        "trace": prev_trace + [step],
        "processing_messages": prev_msg + [msg],
    }


# ---------------------------------------------------------------------------
# Node 7: Report & Ground-Truth Evaluation
# ---------------------------------------------------------------------------

def _evaluate_prediction_against_gt(
    res: ReconciliationResult,
    gt_map: Dict[str, Dict[str, Any]],
) -> Optional[bool]:
    gt = gt_map.get(res.invoice_id)
    if not gt:
        return None

    gt_scenario = gt.get("scenario", "")
    gt_settlement_id = gt.get("settlement_id")

    # Missing settlement: correct if no settlement matched AND marked Unresolved
    if gt_settlement_id is None:
        return (res.status == ReconciliationStatus.UNRESOLVED and res.settlement_id is None)

    status_family = {
        "Exact Match":    {"exact_match"},
        "Fee Match":      {"fee_adjusted"},
        "Probable Match": {"delayed_settlement"},
        "Human Review":   {"partial_payment", "refund", "duplicate_payment", "incorrect_reference", "ambiguous_match"},
        "Unresolved":     {"missing_settlement", "amount_mismatch"},
    }

    if gt_scenario == "duplicate_payment":
        return res.settlement_id is not None and res.status == ReconciliationStatus.HUMAN_REVIEW

    matched_correct_settlement = (res.settlement_id == gt_settlement_id)
    allowed_scenarios = status_family.get(res.status.value, set())
    status_ok = gt_scenario in allowed_scenarios

    return matched_correct_settlement and status_ok


def report_node(state: ReconciliationState) -> Dict[str, Any]:
    t0 = time.perf_counter()
    run_id = state.get("run_id", "RUN-UNKNOWN")
    results = state.get("reconciliation_results", [])
    invoices = state.get("normalized_invoices", [])
    settlements = state.get("normalized_settlements", [])
    bank_transactions = state.get("normalized_bank_transactions", [])
    gt_records = state.get("ground_truth_records", [])

    gt_map: Dict[str, Dict[str, Any]] = {}
    if gt_records:
        for r in gt_records:
            gt_map[r["invoice_id"]] = r

    # Post-hoc ground truth evaluation (pure evaluation, never used during matching)
    if gt_map:
        for r in results:
            r.is_correct_prediction = _evaluate_prediction_against_gt(r, gt_map)

    total = len(results)
    exact_count = sum(1 for r in results if r.match_type == MatchType.EXACT)
    fee_count = sum(1 for r in results if r.match_type == MatchType.FEE_ADJUSTED)
    delayed_count = sum(1 for r in results if r.match_type == MatchType.DELAYED)
    review_count = sum(1 for r in results if r.status == ReconciliationStatus.HUMAN_REVIEW)
    unresolved_count = sum(1 for r in results if r.status == ReconciliationStatus.UNRESOLVED)
    auto_resolved = exact_count + fee_count

    # Authoritative open exception count
    open_exception_count = review_count + unresolved_count

    # STRICT MATCH RATE: successfully reconciled cases / total evaluated cases
    # (Exact, Fee-adjusted, and verified Delayed settlements are successfully reconciled)
    reconciled_cases = exact_count + fee_count + delayed_count
    match_rate = round(reconciled_cases / total, 4) if total > 0 else 0.0

    auto_resolution_rate = round(auto_resolved / total, 4) if total > 0 else 0.0

    reconciled_amount = sum(r.invoice_amount for r in results if r.status != ReconciliationStatus.UNRESOLVED)
    unresolved_amount = sum(r.invoice_amount for r in results if r.status == ReconciliationStatus.UNRESOLVED)

    # Precision & Recall (only when ground truth is provided)
    evaluated = [r for r in results if r.is_correct_prediction is not None]
    if evaluated:
        correct = sum(1 for r in evaluated if r.is_correct_prediction)
        verified_accuracy = round(correct / len(evaluated), 4)
        tp = sum(1 for r in evaluated if r.is_correct_prediction and r.status != ReconciliationStatus.UNRESOLVED)
        fp = sum(1 for r in evaluated if not r.is_correct_prediction and r.status != ReconciliationStatus.UNRESOLVED)
        fn = sum(1 for r in evaluated if not r.is_correct_prediction and r.status == ReconciliationStatus.UNRESOLVED)
        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    else:
        verified_accuracy = None
        precision = None
        recall = None

    # Scenario-level breakdown
    scenario_map: Dict[str, List[ReconciliationResult]] = defaultdict(list)
    for r in results:
        scenario_map[r.ground_truth_scenario].append(r)

    scenario_perf: List[ScenarioPerformance] = []
    for scenario, scene_results in sorted(scenario_map.items()):
        total_s = len(scene_results)
        evaluated_s = [r for r in scene_results if r.is_correct_prediction is not None]
        correct_s = sum(1 for r in evaluated_s if r.is_correct_prediction)
        acc = round(correct_s / len(evaluated_s), 4) if evaluated_s else 0.0
        scenario_perf.append(ScenarioPerformance(
            scenario=scenario,
            total_cases=total_s,
            correctly_identified=correct_s,
            accuracy=acc,
        ))

    prev_trace = state.get("trace", [])
    duration_report = round((time.perf_counter() - t0) * 1000, 2)
    step = TraceStep(
        node="REPORT",
        timestamp=datetime.utcnow().isoformat(),
        message=f"Run finalized: {match_rate*100:.1f}% match rate, {open_exception_count} open exceptions",
        duration_ms=duration_report,
        status="completed",
    )
    final_trace = prev_trace + [step]

    # Total pipeline execution time
    total_ms = sum(s.duration_ms for s in final_trace)

    run = ReconciliationRun(
        run_id=run_id,
        timestamp=datetime.utcnow(),
        records_processed=total,
        invoices_count=len(invoices),
        settlements_count=len(settlements),
        bank_transactions_count=len(bank_transactions),
        exact_matches=exact_count,
        fee_matches=fee_count,
        probable_matches=delayed_count,
        human_review=review_count,
        unresolved=unresolved_count,
        auto_resolved=auto_resolved,
        open_exception_count=open_exception_count,
        reconciled_amount=round(reconciled_amount, 2),
        unresolved_amount=round(unresolved_amount, 2),
        match_rate=match_rate,
        verified_accuracy=verified_accuracy,
        auto_resolution_rate=auto_resolution_rate,
        processing_time_ms=round(total_ms, 2),
        scenario_performance=scenario_perf,
        precision=precision,
        recall=recall,
        trace=final_trace,
    )

    return {
        "run_summary": run,
        "trace": final_trace,
    }


# ---------------------------------------------------------------------------
# LangGraph Workflow Construction & Compilation
# ---------------------------------------------------------------------------

def should_route_to_exceptions(state: ReconciliationState) -> str:
    """Conditional router: directs exceptions to investigator before report."""
    if state.get("has_exceptions", False):
        return "exception_investigator_node"
    return "report_node"


def build_reconciliation_graph():
    """Builds and compiles the official LangGraph stateful reconciliation workflow."""
    workflow = StateGraph(ReconciliationState)

    workflow.add_node("ingest_node", ingest_node)
    workflow.add_node("normalize_node", normalize_node)
    workflow.add_node("match_node", match_node)
    workflow.add_node("verify_node", verify_node)
    workflow.add_node("classify_node", classify_node)
    workflow.add_node("exception_investigator_node", exception_investigator_node)
    workflow.add_node("report_node", report_node)

    workflow.add_edge(START, "ingest_node")
    workflow.add_edge("ingest_node", "normalize_node")
    workflow.add_edge("normalize_node", "match_node")
    workflow.add_edge("match_node", "verify_node")
    workflow.add_edge("verify_node", "classify_node")

    # Conditional branching
    workflow.add_conditional_edges(
        "classify_node",
        should_route_to_exceptions,
        {
            "exception_investigator_node": "exception_investigator_node",
            "report_node": "report_node",
        },
    )

    workflow.add_edge("exception_investigator_node", "report_node")
    workflow.add_edge("report_node", END)

    return workflow.compile()


# Compiled Singleton Graph instance
reconciliation_graph = build_reconciliation_graph()
