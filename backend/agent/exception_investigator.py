"""
ReconAI — AI Exception Investigator
===================================
Provides deep-dive root-cause analysis for Human Review and Unresolved exceptions.
Uses ONLY verified evidence already gathered by ReconAI:
- invoice
- matched settlement(s)
- relevant bank transaction(s)
- expected amount
- received amount
- difference
- dates
- deterministic classification
- confidence
- verification signals

Strict Rules:
- NEVER invent transaction IDs or amounts
- Explicitly acknowledge uncertainty
- Returns UNKNOWN when evidence is insufficient
- AI analysis CANNOT alter deterministic status
- Caches analysis in SQLite to preserve API quota
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..database.db import get_db
from ..models.schemas import (
    AIExceptionAnalysis,
    LikelyReason,
    RiskLevel,
    ReconciliationResult,
)
from .gemini_client import (
    is_gemini_configured,
    generate_content_with_fallback,
    PRIMARY_MODEL,
)

logger = logging.getLogger("reconai.investigator")

ALLOWED_REASONS = {r.value for r in LikelyReason}


def collect_exception_evidence(invoice_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Collects strictly verified evidence for an invoice from SQLite."""
    clean_id = invoice_id.strip().upper()
    with get_db() as conn:
        if run_id:
            rid = run_id
        else:
            row = conn.execute(
                "SELECT run_id FROM reconciliation_runs ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            rid = row["run_id"] if row else None

        res_row = conn.execute(
            "SELECT * FROM reconciliation_results WHERE UPPER(invoice_id) = ? AND run_id = ?",
            (clean_id, rid),
        ).fetchone() if rid else None

        if not res_row:
            # Fallback: check any run
            res_row = conn.execute(
                "SELECT * FROM reconciliation_results WHERE UPPER(invoice_id) = ? ORDER BY processed_at DESC LIMIT 1",
                (clean_id,),
            ).fetchone()

        if not res_row:
            # Check raw invoices
            inv_row = conn.execute(
                "SELECT * FROM invoices WHERE UPPER(invoice_id) = ?", (clean_id,)
            ).fetchone()
            if not inv_row:
                raise ValueError(f"Invoice '{clean_id}' was not found in the reconciliation dataset.")

            return {
                "invoice": dict(inv_row),
                "matched_settlements": [],
                "relevant_bank_transactions": [],
                "expected_amount": float(inv_row["invoice_amount"]),
                "received_amount": None,
                "difference": float(inv_row["invoice_amount"]),
                "dates": {"invoice_date": inv_row["invoice_date"]},
                "deterministic_classification": {"status": "Unreconciled", "match_type": "none"},
                "confidence": 0.0,
                "verification_signals": [],
                "run_id": rid or "RUN-CURRENT",
            }

        res = dict(res_row)
        active_rid = res["run_id"]

        # Collect matched settlements
        settlements = []
        if res.get("settlement_id"):
            s_rows = conn.execute(
                "SELECT * FROM settlements WHERE settlement_id = ?", (res["settlement_id"],)
            ).fetchall()
            settlements = [dict(s) for s in s_rows]
        if not settlements:
            s_rows = conn.execute(
                "SELECT * FROM settlements WHERE invoice_reference = ?", (clean_id,)
            ).fetchall()
            settlements = [dict(s) for s in s_rows]

        # Collect relevant bank transactions
        bank_txns = []
        if res.get("bank_txn_id"):
            b_rows = conn.execute(
                "SELECT * FROM bank_transactions WHERE bank_txn_id = ?", (res["bank_txn_id"],)
            ).fetchall()
            bank_txns = [dict(b) for b in b_rows]
        elif settlements:
            for s in settlements:
                utr = s.get("utr_number")
                if utr:
                    b_rows = conn.execute(
                        "SELECT * FROM bank_transactions WHERE utr_number = ?", (utr,)
                    ).fetchall()
                    bank_txns.extend([dict(b) for b in b_rows])

        evidence_items = []
        if res.get("evidence_json"):
            try:
                evidence_items = json.loads(res["evidence_json"])
            except Exception:
                pass

        return {
            "invoice": {
                "invoice_id": res["invoice_id"],
                "customer_name": res["customer_name"],
                "customer_id": res["customer_id"],
                "amount": res["invoice_amount"],
                "date": res["invoice_date"],
            },
            "matched_settlements": [
                {
                    "settlement_id": s["settlement_id"],
                    "amount": s.get("amount"),
                    "fee": s.get("fee"),
                    "net_amount": s.get("net_amount"),
                    "payment_date": s.get("payment_date"),
                    "settlement_date": s.get("settlement_date"),
                    "utr_number": s.get("utr_number"),
                    "remarks": s.get("remarks"),
                }
                for s in settlements
            ],
            "relevant_bank_transactions": [
                {
                    "bank_txn_id": b["bank_txn_id"],
                    "amount": b.get("amount"),
                    "transaction_date": b.get("transaction_date"),
                    "utr_number": b.get("utr_number"),
                    "description": b.get("description"),
                }
                for b in bank_txns
            ],
            "expected_amount": res["invoice_amount"],
            "received_amount": res["settlement_amount"],
            "difference": res["difference"],
            "dates": {
                "invoice_date": res["invoice_date"],
                "payment_date": res.get("payment_date"),
                "settlement_date": res.get("settlement_date"),
                "days_delayed": res.get("days_delayed"),
            },
            "deterministic_classification": {
                "status": res["status"],
                "match_type": res["match_type"],
                "exception_category": res.get("exception_category"),
                "system_assessment": res.get("system_assessment"),
                "recommendation": res.get("recommendation"),
            },
            "confidence": res["confidence_score"],
            "verification_signals": evidence_items,
            "run_id": active_rid,
        }


def _deterministic_fallback_analysis(evidence: Dict[str, Any]) -> AIExceptionAnalysis:
    """Fallback generator producing grounded structured analysis when Gemini is offline."""
    inv = evidence["invoice"]
    det = evidence["deterministic_classification"]
    cat = (det.get("exception_category") or "").upper()
    diff = evidence.get("difference", 0.0)
    exp_amt = evidence.get("expected_amount", 0.0)
    rec_amt = evidence.get("received_amount")

    if "PARTIAL" in cat:
        reason = LikelyReason.PARTIAL_PAYMENT
        risk = RiskLevel.MEDIUM
        summary = f"Partial payment received for invoice {inv['invoice_id']}. Outstanding balance is ₹{abs(diff):,.2f}."
        explanation = (
            f"Settlement reflects an installment of ₹{rec_amt:,.2f} against the total invoiced amount of ₹{exp_amt:,.2f}. "
            "Customer reference code and identity matched, but settlement does not cover the complete obligation."
        )
        action = "Obtain confirmation of second tranche payment or initiate balance dunning schedule."
    elif "DUPLICATE" in cat:
        reason = LikelyReason.DUPLICATE_ACTIVITY
        risk = RiskLevel.HIGH
        summary = f"Multiple conflicting settlement records detected referencing invoice {inv['invoice_id']}."
        explanation = (
            f"Two or more gateway settlement entries reference identical invoice {inv['invoice_id']}. "
            "Ledger reflects potential duplicate credit or overlapping batch submissions."
        )
        action = "Freeze duplicate settlement allocation and initiate gateway transaction ID deduplication audit."
    elif "REFUND" in cat:
        reason = LikelyReason.REFUND_ACTIVITY
        risk = RiskLevel.MEDIUM
        summary = f"Refund or chargeback adjustment detected on invoice {inv['invoice_id']}."
        explanation = (
            f"Settlement net proceeds show negative variance (-₹{abs(diff):,.2f}) matching gateway refund or dispute deductions."
        )
        action = "Verify customer support ticket or RMA authorization to confirm credit note issuance."
    elif "AMOUNT" in cat:
        reason = LikelyReason.AMOUNT_MISMATCH
        risk = RiskLevel.HIGH
        summary = f"Unexplained amount variance of ₹{abs(diff):,.2f} on invoice {inv['invoice_id']}."
        explanation = (
            f"Expected invoice amount is ₹{exp_amt:,.2f}, whereas settlement gross/net received is ₹{rec_amt or 0:,.2f}. "
            "Discrepancy exceeds permissible gateway fee schedule."
        )
        action = "Request settlement fee breakdown from gateway provider to reconcile unaccounted fee/deduction."
    elif "MISSING" in cat or det.get("status") == "Unresolved":
        reason = LikelyReason.MISSING_SETTLEMENT
        risk = RiskLevel.HIGH
        summary = f"No corresponding settlement or bank deposit found for invoice {inv['invoice_id']}."
        explanation = (
            f"Invoice for ₹{exp_amt:,.2f} issued to {inv['customer_name']} has no matching payment confirmation "
            "across payment gateway feeds or bank statements."
        )
        action = "Send automated payment reminder to customer and verify whether transaction was abandoned at checkout."
    elif "AMBIGUOUS" in cat:
        reason = LikelyReason.AMBIGUOUS
        risk = RiskLevel.MEDIUM
        summary = f"Ambiguous match candidates detected for invoice {inv['invoice_id']}."
        explanation = (
            "Multiple candidate settlements share similar transaction values and customer accounts without distinct invoice references."
        )
        action = "Manual auditor confirmation required to link settlement reference code to this specific billing record."
    elif "DELAYED" in cat or (evidence.get("dates", {}).get("days_delayed") or 0) > 5:
        reason = LikelyReason.DELAYED_SETTLEMENT
        risk = RiskLevel.LOW
        days = evidence.get("dates", {}).get("days_delayed") or 0
        summary = f"Settlement delivery breached 5-day SLA by {days} days for invoice {inv['invoice_id']}."
        explanation = f"Payment was successfully settled but exceeded standard gateway settlement SLA window by {days} days."
        action = "Record processor SLA delay in vendor scorecard; no funds recovery required."
    else:
        reason = LikelyReason.UNKNOWN
        risk = RiskLevel.MEDIUM
        summary = f"Exception analysis for invoice {inv['invoice_id']} requires additional documentation."
        explanation = "Deterministic evidence indicates an unresolved ledger state with insufficient transaction signals."
        action = "Escalate to Level 2 finance operations controller for audit log inspection."

    return AIExceptionAnalysis(
        summary=summary,
        likely_reason=reason,
        risk_level=risk,
        recommended_action=action,
        explanation=explanation,
        invoice_id=inv["invoice_id"],
        cached=False,
        model="data-only-engine",
    )


async def analyze_exception_with_ai(
    invoice_id: str,
    run_id: Optional[str] = None,
    force_refresh: bool = False,
) -> AIExceptionAnalysis:
    """
    Main entry point for AI exception investigation.
    Checks SQLite cache -> Calls Gemini if configured -> Falls back to deterministic rule analysis.
    """
    clean_id = invoice_id.strip().upper()
    evidence = collect_exception_evidence(clean_id, run_id)
    active_run_id = evidence["run_id"]

    # 1. Check Cache
    if not force_refresh:
        with get_db() as conn:
            cached_row = conn.execute(
                "SELECT analysis_json FROM ai_exception_analyses WHERE invoice_id = ? AND run_id = ?",
                (clean_id, active_run_id),
            ).fetchone()
            if cached_row and cached_row["analysis_json"]:
                try:
                    data = json.loads(cached_row["analysis_json"])
                    data["cached"] = True
                    return AIExceptionAnalysis(**data)
                except Exception:
                    pass

    # 2. If Gemini is configured, invoke with strict evidence
    if is_gemini_configured():
        system_instruction = (
            "You are ReconAI Exception Investigator, an expert AI financial auditor.\n"
            "Analyze the supplied financial reconciliation exception using ONLY the provided verified evidence.\n"
            "STRICT RULES:\n"
            "1. Never invent transaction IDs, UTRs, or amounts.\n"
            "2. Never alter the deterministic reconciliation status.\n"
            "3. Explicitly acknowledge uncertainty.\n"
            "4. Output strictly valid JSON matching this exact structure:\n"
            "{\n"
            '  "summary": "<1-2 sentence executive summary>",\n'
            '  "likely_reason": "<one of: PROCESSING_FEE | PARTIAL_PAYMENT | REFUND_ACTIVITY | DELAYED_SETTLEMENT | DUPLICATE_ACTIVITY | REFERENCE_MISMATCH | AMOUNT_MISMATCH | MISSING_SETTLEMENT | AMBIGUOUS | UNKNOWN>",\n'
            '  "risk_level": "<one of: LOW | MEDIUM | HIGH>",\n'
            '  "recommended_action": "<concrete next step for finance controller>",\n'
            '  "explanation": "<detailed root cause deduction citing verified numbers from evidence>"\n'
            "}"
        )

        prompt = (
            f"INVESTIGATION EVIDENCE FOR INVOICE {clean_id}:\n"
            f"{json.dumps(evidence, indent=2)}\n\n"
            "Provide root-cause diagnosis in requested JSON format based strictly on this evidence."
        )

        content, model_used, latency, error = generate_content_with_fallback(
            prompt=prompt,
            system_instruction=system_instruction,
            timeout_seconds=15.0,
        )

        if content:
            try:
                # Clean code fences if present
                clean_json = content.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json[7:]
                if clean_json.startswith("```"):
                    clean_json = clean_json[3:]
                if clean_json.endswith("```"):
                    clean_json = clean_json[:-3]
                clean_json = clean_json.strip()

                parsed = json.loads(clean_json)

                # Validate likely_reason
                reason_str = str(parsed.get("likely_reason", "UNKNOWN")).upper().strip()
                if reason_str not in ALLOWED_REASONS:
                    reason_str = "UNKNOWN"

                # Validate risk_level
                risk_str = str(parsed.get("risk_level", "MEDIUM")).upper().strip()
                if risk_str not in ("LOW", "MEDIUM", "HIGH"):
                    risk_str = "MEDIUM"

                analysis = AIExceptionAnalysis(
                    summary=parsed.get("summary", f"Exception investigation for {clean_id}"),
                    likely_reason=LikelyReason(reason_str),
                    risk_level=RiskLevel(risk_str),
                    recommended_action=parsed.get("recommended_action", "Review transaction evidence in audit workbench."),
                    explanation=parsed.get("explanation", "Root cause evaluated against supplied reconciliation signals."),
                    invoice_id=clean_id,
                    cached=False,
                    model=model_used or PRIMARY_MODEL,
                )

                # Save to Cache
                with get_db() as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO ai_exception_analyses
                        (invoice_id, run_id, analysis_json, created_at)
                        VALUES (?, ?, ?, datetime('now'))
                        """,
                        (clean_id, active_run_id, json.dumps(analysis.dict())),
                    )

                return analysis

            except Exception as e_parse:
                logger.warning("Failed to parse Gemini exception response (%s): %s", e_parse, content[:100])

    # 3. Fallback / Data-only deterministic analysis
    fallback = _deterministic_fallback_analysis(evidence)
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO ai_exception_analyses
            (invoice_id, run_id, analysis_json, created_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (clean_id, active_run_id, json.dumps(fallback.dict())),
        )
    return fallback
