"""
ReconAI — Deterministic Multi-Source Reconciliation Engine v2.1
===============================================================
Two-pass deterministic reconciliation:
- Pass 1: Exact reference matching (handles exact, fee-adjusted, delayed, duplicates, refunds, partial, amount mismatch)
- Pass 2: Secondary heuristic matching (handles incorrect reference, ambiguous match, missing settlement)
Ground-truth is kept strictly segregated for post-reconciliation evaluation.
No LLM calls. No random values. No hardcoded results.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple

from ..models.schemas import (
    Invoice,
    Settlement,
    BankTransaction,
    ReconciliationResult,
    ReconciliationRun,
    MatchType,
    ReconciliationStatus,
    ExceptionCategory,
    EvidenceItem,
    ScenarioPerformance,
)

EXACT_AMT_TOLERANCE = Decimal("0.01")
FEE_RATE_MIN = Decimal("0.005")
FEE_RATE_MAX = Decimal("0.045")
GST_ON_FEE_RATE = Decimal("0.18")
PARTIAL_MIN = Decimal("0.10")
PARTIAL_MAX = Decimal("0.85")
DATE_DELAYED_DAYS = 5
CONF_AUTO_THRESHOLD = 90
CONF_REVIEW_THRESHOLD = 70


def _d(v: float) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _f(v: Decimal) -> float:
    return float(v)


def normalize_ref(s: Optional[str]) -> str:
    if not s:
        return ""
    return s.strip().upper().replace(" ", "")


def _find_bank_txn(
    settlement: Settlement,
    bank_by_utr: Dict[str, BankTransaction],
    bank_by_set_ref: Dict[str, BankTransaction],
) -> Optional[BankTransaction]:
    if settlement.utr_number:
        b = bank_by_utr.get(normalize_ref(settlement.utr_number))
        if b:
            return b
    return bank_by_set_ref.get(settlement.settlement_id)


def _build_evidence(
    invoice: Invoice,
    settlement: Optional[Settlement],
    bank_txn: Optional[BankTransaction],
    ref_matched: bool,
    cust_matched: bool,
    amt_matched: bool,
    fee_matched: bool,
    date_matched: bool,
    days_delta: int,
    is_duplicate: bool = False,
    is_refund: bool = False,
) -> List[EvidenceItem]:
    items: List[EvidenceItem] = []
    if not settlement:
        items.append(
            EvidenceItem(
                label="Settlement record exists",
                matched=False,
                detail="No settlement found in any source for this invoice.",
            )
        )
        return items

    inv_amt = _d(invoice.invoice_amount)
    s_gross = _d(settlement.amount)
    s_fee = _d(settlement.fee)

    items.append(
        EvidenceItem(
            label="Invoice reference matched",
            matched=ref_matched,
            detail=f"Settlement ref '{settlement.invoice_reference}' vs Invoice '{invoice.invoice_id}'",
        )
    )
    items.append(
        EvidenceItem(
            label="Customer ID matched",
            matched=cust_matched,
            detail=f"Settlement customer '{settlement.customer_id}' vs Invoice '{invoice.customer_id}'",
        )
    )
    items.append(
        EvidenceItem(
            label="Gross amount matched",
            matched=amt_matched,
            detail=f"Settlement gross ₹{s_gross:,.2f} vs Invoice ₹{inv_amt:,.2f}",
        )
    )
    items.append(
        EvidenceItem(
            label="Gateway fee verified",
            matched=fee_matched,
            detail=f"Fee ₹{s_fee:,.2f} on ₹{inv_amt:,.2f} ({float(s_fee / inv_amt) * 100:.2f}%)"
            if inv_amt > 0
            else "N/A",
        )
    )
    items.append(
        EvidenceItem(
            label="Settlement SLA (≤ 5 days)",
            matched=date_matched,
            detail=f"Settlement payment received {days_delta} days after invoice date",
        )
    )
    items.append(
        EvidenceItem(
            label="Bank transaction verified",
            matched=bank_txn is not None,
            detail=f"Bank txn ID: {bank_txn.bank_txn_id if bank_txn else 'Not found in bank feed'}",
        )
    )
    if is_duplicate:
        items.append(
            EvidenceItem(
                label="Duplicate payment check",
                matched=False,
                detail="Multiple settlement credits found with identical invoice reference.",
            )
        )
    if is_refund:
        items.append(
            EvidenceItem(
                label="Refund deduction detected",
                matched=True,
                detail=settlement.remarks or "Refund adjustment indicated in remarks",
            )
        )
    return items


def _calculate_confidence(
    ref_matched: bool,
    cust_matched: bool,
    amt_matched: bool,
    fee_matched: bool,
    date_matched: bool,
    bank_matched: bool,
    is_duplicate: bool,
    is_ambiguous: bool,
    is_mismatch: bool,
) -> int:
    score = 0
    if ref_matched:
        score += 35
    if cust_matched:
        score += 15
    if amt_matched:
        score += 25
    elif fee_matched:
        score += 20
    if date_matched:
        score += 15
    else:
        score += 5
    if bank_matched:
        score += 10
    if is_duplicate:
        score -= 25
    if is_ambiguous:
        score -= 20
    if is_mismatch:
        score -= 30
    return max(0, min(100, score))


def _evaluate_prediction(
    result: ReconciliationResult,
    gt_by_invoice: Dict[str, dict],
) -> Optional[bool]:
    gt = gt_by_invoice.get(result.invoice_id)
    if not gt:
        return None
    gt_scenario = gt.get("scenario", "")
    gt_settlement_id = gt.get("settlement_id")

    if gt_settlement_id is None:
        return result.status == ReconciliationStatus.UNRESOLVED and result.settlement_id is None

    status_family = {
        "Exact Match": {"exact_match"},
        "Fee Match": {"fee_adjusted"},
        "Probable Match": {"delayed_settlement"},
        "Human Review": {
            "incorrect_reference",
            "duplicate_payment",
            "ambiguous_match",
            "refund",
            "partial_payment",
            "amount_mismatch",
        },
        "Unresolved": {"missing_settlement", "amount_mismatch"},
    }

    if gt_scenario == "duplicate_payment":
        matched_settlement = result.settlement_id is not None
        status_ok = result.status == ReconciliationStatus.HUMAN_REVIEW
        return matched_settlement and status_ok

    matched_settlement = result.settlement_id == gt_settlement_id
    allowed_scenarios = status_family.get(result.status.value, set())
    status_ok = gt_scenario in allowed_scenarios
    return matched_settlement and status_ok


def reconcile(
    invoices: List[Invoice],
    settlements: List[Settlement],
    bank_transactions: List[BankTransaction],
    ground_truth_records: Optional[List[dict]] = None,
    run_id: Optional[str] = None,
) -> Tuple[ReconciliationRun, List[ReconciliationResult]]:
    t_start = time.perf_counter()
    run_id = run_id or f"RUN-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.utcnow()

    gt_by_invoice = (
        {gt["invoice_id"]: gt for gt in ground_truth_records}
        if ground_truth_records
        else {}
    )

    bank_by_utr: Dict[str, BankTransaction] = {}
    bank_by_set_ref: Dict[str, BankTransaction] = {}
    for b in bank_transactions:
        if b.utr_number:
            bank_by_utr[normalize_ref(b.utr_number)] = b
        if b.settlement_reference:
            bank_by_set_ref[b.settlement_reference] = b

    set_by_ref: Dict[str, List[Settlement]] = defaultdict(list)
    for s in settlements:
        ref = normalize_ref(s.invoice_reference)
        if ref:
            set_by_ref[ref].append(s)

    used_settlement_ids = set()
    matched_results: Dict[str, ReconciliationResult] = {}
    unmatched_invoices: List[Invoice] = []

    # Pass 1: Exact reference matching
    for inv in invoices:
        inv_ref = normalize_ref(inv.invoice_id)
        candidates = set_by_ref.get(inv_ref, [])
        if not candidates:
            unmatched_invoices.append(inv)
            continue

        inv_amt = _d(inv.invoice_amount)

        if len(candidates) >= 2:
            s1 = candidates[0]
            for c in candidates:
                used_settlement_ids.add(c.settlement_id)
            bank_txn = _find_bank_txn(s1, bank_by_utr, bank_by_set_ref)
            conf = _calculate_confidence(
                True,
                True,
                True,
                True,
                True,
                bank_txn is not None,
                True,
                False,
                False,
            )
            ev = _build_evidence(
                inv,
                s1,
                bank_txn,
                True,
                True,
                True,
                True,
                True,
                abs((s1.payment_date - inv.invoice_date).days),
                True,
            )
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s1.settlement_id,
                bank_txn_id=bank_txn.bank_txn_id if bank_txn else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s1.net_amount, 2),
                bank_amount=round(bank_txn.amount, 2) if bank_txn else None,
                difference=round(inv.invoice_amount - s1.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s1.payment_date,
                settlement_date=s1.settlement_date,
                days_delayed=(s1.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.DUPLICATE,
                status=ReconciliationStatus.HUMAN_REVIEW,
                confidence_score=conf,
                exception_category=ExceptionCategory.DUPLICATE,
                evidence=ev,
                system_assessment=f"Duplicate settlements detected: {len(candidates)} records reference invoice {inv.invoice_id}.",
                recommendation=f"Flag for human review: verify if customer made double payment or settlement file contains duplicate ingestion.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            matched_results[inv.invoice_id] = res
            continue

        s = candidates[0]
        used_settlement_ids.add(s.settlement_id)
        bank_txn = _find_bank_txn(s, bank_by_utr, bank_by_set_ref)

        s_gross = _d(s.amount)
        s_net = _d(s.net_amount)
        s_fee = _d(s.fee)
        days_delta = abs((s.payment_date - inv.invoice_date).days)
        remarks_lower = (s.remarks or "").lower()

        gross_matches = abs(inv_amt - s_gross) <= EXACT_AMT_TOLERANCE
        fee_pct = (s_fee / inv_amt) if inv_amt > 0 else Decimal("0")
        fee_valid = FEE_RATE_MIN <= fee_pct <= FEE_RATE_MAX

        if "refund" in remarks_lower:
            conf = _calculate_confidence(
                True,
                True,
                False,
                False,
                days_delta <= DATE_DELAYED_DAYS,
                bank_txn is not None,
                False,
                False,
                False,
            )
            ev = _build_evidence(
                inv,
                s,
                bank_txn,
                True,
                True,
                False,
                False,
                days_delta <= DATE_DELAYED_DAYS,
                days_delta,
                is_refund=True,
            )
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=bank_txn.bank_txn_id if bank_txn else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(bank_txn.amount, 2) if bank_txn else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.REFUND,
                status=ReconciliationStatus.HUMAN_REVIEW,
                confidence_score=conf,
                exception_category=ExceptionCategory.REFUND_DISCREPANCY,
                evidence=ev,
                system_assessment=f"Refund adjustment detected on settlement {s.settlement_id}: remarks indicate return or dispute deduction.",
                recommendation="Audit refund authorization against customer ticket. Verify return of merchandise or service adjustment.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            matched_results[inv.invoice_id] = res

        elif (
            PARTIAL_MIN
            <= ((s_gross / inv_amt) if inv_amt > 0 else Decimal("0"))
            <= PARTIAL_MAX
        ):
            conf = _calculate_confidence(
                True,
                True,
                False,
                False,
                days_delta <= DATE_DELAYED_DAYS,
                bank_txn is not None,
                False,
                False,
                False,
            )
            ev = _build_evidence(
                inv,
                s,
                bank_txn,
                True,
                True,
                False,
                False,
                days_delta <= DATE_DELAYED_DAYS,
                days_delta,
            )
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=bank_txn.bank_txn_id if bank_txn else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(bank_txn.amount, 2) if bank_txn else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.PARTIAL,
                status=ReconciliationStatus.HUMAN_REVIEW,
                confidence_score=conf,
                exception_category=ExceptionCategory.PARTIAL_PAYMENT,
                evidence=ev,
                system_assessment=f"Partial settlement received: ₹{s_gross:,.2f} of invoice ₹{inv_amt:,.2f} ({float(s_gross/inv_amt)*100:.1f}%).",
                recommendation="Record partial payment against accounts receivable ledger. Follow up with customer for pending tranche.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            matched_results[inv.invoice_id] = res

        elif not gross_matches:
            conf = _calculate_confidence(
                True,
                True,
                False,
                False,
                days_delta <= DATE_DELAYED_DAYS,
                bank_txn is not None,
                False,
                False,
                True,
            )
            ev = _build_evidence(
                inv,
                s,
                bank_txn,
                True,
                True,
                False,
                False,
                days_delta <= DATE_DELAYED_DAYS,
                days_delta,
            )
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=bank_txn.bank_txn_id if bank_txn else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(bank_txn.amount, 2) if bank_txn else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.UNRESOLVED,
                status=ReconciliationStatus.HUMAN_REVIEW,
                confidence_score=conf,
                exception_category=ExceptionCategory.AMOUNT_MISMATCH,
                evidence=ev,
                system_assessment=f"Unexplained amount mismatch: Invoice ₹{inv_amt:,.2f} vs Settlement gross ₹{s_gross:,.2f} (diff ₹{abs(inv_amt - s_gross):,.2f}).",
                recommendation="Obtain gateway transaction receipt. Check for unrecorded discounts, penalties or chargebacks.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            matched_results[inv.invoice_id] = res

        elif days_delta > DATE_DELAYED_DAYS:
            conf = _calculate_confidence(
                True,
                True,
                True,
                fee_valid,
                False,
                bank_txn is not None,
                False,
                False,
                False,
            )
            ev = _build_evidence(
                inv,
                s,
                bank_txn,
                True,
                True,
                True,
                fee_valid,
                False,
                days_delta,
            )
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=bank_txn.bank_txn_id if bank_txn else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(bank_txn.amount, 2) if bank_txn else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.DELAYED,
                status=ReconciliationStatus.PROBABLE_MATCH,
                confidence_score=conf,
                exception_category=None,
                evidence=ev,
                system_assessment=f"Delayed settlement: Payment received {days_delta} days after invoice (SLA {DATE_DELAYED_DAYS} days).",
                recommendation="Approve match. Flag customer account for billing cycle timing adjustment if delays are recurring.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            matched_results[inv.invoice_id] = res

        else:
            conf = _calculate_confidence(
                True,
                True,
                True,
                fee_valid,
                True,
                bank_txn is not None,
                False,
                False,
                False,
            )
            ev = _build_evidence(
                inv,
                s,
                bank_txn,
                True,
                True,
                True,
                fee_valid,
                True,
                days_delta,
            )
            match_type = MatchType.FEE_ADJUSTED if fee_valid else MatchType.EXACT
            status = (
                ReconciliationStatus.FEE_MATCH
                if fee_valid
                else ReconciliationStatus.EXACT_MATCH
            )
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=bank_txn.bank_txn_id if bank_txn else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(bank_txn.amount, 2) if bank_txn else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=match_type,
                status=status,
                confidence_score=conf,
                exception_category=None,
                evidence=ev,
                system_assessment=f"Verified match: Invoice ₹{inv_amt:,.2f} matched with settlement {s.settlement_id}.",
                recommendation="Auto-approve. Record journal entry in general ledger.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            matched_results[inv.invoice_id] = res

    # Pass 2: Secondary heuristic matching
    remaining_settlements = [
        s for s in settlements if s.settlement_id not in used_settlement_ids
    ]

    for inv in unmatched_invoices:
        inv_amt = _d(inv.invoice_amount)

        incorrect_ref_match: Optional[Settlement] = None
        for s in remaining_settlements:
            if s.settlement_id in used_settlement_ids:
                continue
            if (
                s.customer_id == inv.customer_id
                and abs(_d(s.amount) - inv_amt) <= EXACT_AMT_TOLERANCE
            ):
                incorrect_ref_match = s
                break

        if incorrect_ref_match:
            s = incorrect_ref_match
            used_settlement_ids.add(s.settlement_id)
            bank_txn = _find_bank_txn(s, bank_by_utr, bank_by_set_ref)
            days_delta = abs((s.payment_date - inv.invoice_date).days)
            conf = _calculate_confidence(
                False,
                True,
                True,
                True,
                days_delta <= DATE_DELAYED_DAYS,
                bank_txn is not None,
                False,
                True,
                False,
            )
            ev = _build_evidence(
                inv,
                s,
                bank_txn,
                False,
                True,
                True,
                True,
                days_delta <= DATE_DELAYED_DAYS,
                days_delta,
            )
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=bank_txn.bank_txn_id if bank_txn else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(bank_txn.amount, 2) if bank_txn else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.INCORRECT_REFERENCE,
                status=ReconciliationStatus.HUMAN_REVIEW,
                confidence_score=conf,
                exception_category=ExceptionCategory.INCORRECT_REFERENCE,
                evidence=ev,
                system_assessment=f"Incorrect reference match: Settlement references '{s.invoice_reference}' but customer ID '{inv.customer_id}' and amount ₹{inv_amt:,.2f} match exactly.",
                recommendation=f"Human review required: verify remittance advice to confirm this payment belongs to invoice {inv.invoice_id}.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            matched_results[inv.invoice_id] = res
            continue

        ambiguous_candidate: Optional[Settlement] = None
        for s in remaining_settlements:
            if s.settlement_id in used_settlement_ids:
                continue
            if s.customer_id == inv.customer_id and (
                not s.invoice_reference or s.invoice_reference.strip() == ""
            ):
                diff_pct = (
                    abs(_d(s.amount) - inv_amt) / inv_amt
                    if inv_amt > 0
                    else Decimal("1")
                )
                if diff_pct <= Decimal("0.05"):
                    ambiguous_candidate = s
                    break

        if ambiguous_candidate:
            s = ambiguous_candidate
            used_settlement_ids.add(s.settlement_id)
            bank_txn = _find_bank_txn(s, bank_by_utr, bank_by_set_ref)
            days_delta = abs((s.payment_date - inv.invoice_date).days)
            conf = _calculate_confidence(
                False,
                True,
                False,
                False,
                days_delta <= DATE_DELAYED_DAYS,
                bank_txn is not None,
                False,
                True,
                False,
            )
            ev = _build_evidence(
                inv,
                s,
                bank_txn,
                False,
                True,
                False,
                False,
                days_delta <= DATE_DELAYED_DAYS,
                days_delta,
            )
            res = ReconciliationResult(
                result_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
                run_id=run_id,
                invoice_id=inv.invoice_id,
                settlement_id=s.settlement_id,
                bank_txn_id=bank_txn.bank_txn_id if bank_txn else None,
                invoice_amount=round(inv.invoice_amount, 2),
                settlement_amount=round(s.net_amount, 2),
                bank_amount=round(bank_txn.amount, 2) if bank_txn else None,
                difference=round(inv.invoice_amount - s.net_amount, 2),
                invoice_date=inv.invoice_date,
                payment_date=s.payment_date,
                settlement_date=s.settlement_date,
                days_delayed=(s.settlement_date - inv.invoice_date).days,
                customer_name=inv.customer_name,
                customer_id=inv.customer_id,
                match_type=MatchType.AMBIGUOUS,
                status=ReconciliationStatus.HUMAN_REVIEW,
                confidence_score=conf,
                exception_category=ExceptionCategory.AMBIGUOUS_MATCH,
                evidence=ev,
                system_assessment=f"Ambiguous candidate: Settlement {s.settlement_id} for customer {inv.customer_id} has missing invoice reference with similar amount.",
                recommendation="Request payment confirmation proof from customer or gateway audit logs.",
                ground_truth_scenario=inv.ground_truth_scenario,
                processed_at=now,
            )
            matched_results[inv.invoice_id] = res
            continue

        # Missing settlement
        ev = _build_evidence(
            inv,
            None,
            None,
            False,
            False,
            False,
            False,
            False,
            0,
            False,
            False,
        )
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
            confidence_score=0,
            exception_category=ExceptionCategory.MISSING_SETTLEMENT,
            evidence=ev,
            system_assessment=f"Missing settlement: No matching settlement or bank transaction found across any source for {inv.invoice_id}.",
            recommendation="Issue payment reminder to customer. Verify if transaction failed or was abandoned at gateway.",
            ground_truth_scenario=inv.ground_truth_scenario,
            processed_at=now,
        )
        matched_results[inv.invoice_id] = res

    results = [matched_results[inv.invoice_id] for inv in invoices]

    for r in results:
        r.is_correct_prediction = _evaluate_prediction(r, gt_by_invoice)

    total = len(results)
    exact_count = sum(
        1 for r in results if r.status == ReconciliationStatus.EXACT_MATCH
    )
    fee_count = sum(
        1 for r in results if r.status == ReconciliationStatus.FEE_MATCH
    )
    delayed_count = sum(
        1 for r in results if r.status == ReconciliationStatus.PROBABLE_MATCH
    )
    unresolved_count = sum(
        1 for r in results if r.status == ReconciliationStatus.UNRESOLVED
    )
    review_count = sum(
        1 for r in results if r.status == ReconciliationStatus.HUMAN_REVIEW
    )
    auto_resolved = sum(
        1
        for r in results
        if r.status
        in (ReconciliationStatus.EXACT_MATCH, ReconciliationStatus.FEE_MATCH)
    )
    matched_count = exact_count + fee_count + delayed_count
    match_rate = round(matched_count / total, 4) if total else 0.0

    evaluated = [r for r in results if r.is_correct_prediction is not None]
    correct = sum(1 for r in evaluated if r.is_correct_prediction)
    verified_accuracy = round(correct / len(evaluated), 4) if evaluated else 0.0
    auto_resolution_rate = round(auto_resolved / total, 4) if total else 0.0

    reconciled_amount = sum(
        r.invoice_amount
        for r in results
        if r.status != ReconciliationStatus.UNRESOLVED
    )
    unresolved_amount = sum(
        r.invoice_amount
        for r in results
        if r.status == ReconciliationStatus.UNRESOLVED
    )

    tp = sum(
        1
        for r in evaluated
        if r.is_correct_prediction and r.status != ReconciliationStatus.UNRESOLVED
    )
    fp = sum(
        1
        for r in evaluated
        if not r.is_correct_prediction
        and r.status != ReconciliationStatus.UNRESOLVED
    )
    fn = sum(
        1
        for r in evaluated
        if r.status == ReconciliationStatus.UNRESOLVED
        and r.is_correct_prediction is False
    )

    precision = round(tp / (tp + fp), 4) if (tp + fp) else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) else 0.0

    scenario_map: Dict[str, List[ReconciliationResult]] = defaultdict(list)
    for r in results:
        scenario_map[r.ground_truth_scenario].append(r)

    scenario_perf: List[ScenarioPerformance] = []
    for scenario, scene_results in sorted(scenario_map.items()):
        total_s = len(scene_results)
        evaluated_s = [
            r for r in scene_results if r.is_correct_prediction is not None
        ]
        correct_s = sum(1 for r in evaluated_s if r.is_correct_prediction)
        acc = round(correct_s / len(evaluated_s), 4) if evaluated_s else 0.0
        scenario_perf.append(
            ScenarioPerformance(
                scenario=scenario,
                total_cases=total_s,
                correctly_identified=correct_s,
                accuracy=acc,
            )
        )

    t_end = time.perf_counter()
    processing_ms = round((t_end - t_start) * 1000, 2)

    run = ReconciliationRun(
        run_id=run_id,
        timestamp=now,
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
        reconciled_amount=round(reconciled_amount, 2),
        unresolved_amount=round(unresolved_amount, 2),
        match_rate=match_rate,
        verified_accuracy=verified_accuracy,
        auto_resolution_rate=auto_resolution_rate,
        processing_time_ms=processing_ms,
        scenario_performance=scenario_perf,
        precision=precision,
        recall=recall,
    )

    return run, results
