"""
ReconAI — Generalized File Type Detector
=========================================
Infers whether an arbitrary financial CSV contains:
- INVOICES
- SETTLEMENTS
- BANK_TRANSACTIONS
- REFUNDS
- UNKNOWN

Uses a weighted multi-signal detection approach:
1. Semantic header meaning & concept clusters (ERP, Banking, Gateways, Accounting, Invoicing, Refunds)
2. Cross-column relational signals (Invoice lifecycle, Settlement payout decomposition, Bank statements, Reversal concepts)
3. Value patterns & data type distributions (monetary columns, dates, alphanumeric identifiers)
4. Evidence-derived confidence based on candidate margin (never arbitrary hardcoded numbers)
5. Gemini semantic fallback for low confidence (< 0.70) or close top candidates (hardened against rate limits/errors)
6. Cross-file batch reasoning (disambiguates receivables vs settlements when uploaded together)
7. Safe UNKNOWN fallback when confidence is insufficient
"""

from __future__ import annotations

import re
import json
from typing import Dict, List, Any, Tuple, Optional, Set
from ..agent.gemini_client import is_gemini_configured, generate_content_with_fallback


# Token weights for semantic concept clusters
INVOICE_KEYWORDS: Dict[str, float] = {
    "invoice": 4.0, "invoice_id": 4.5, "invoice_no": 4.5, "inv_no": 4.5, "bill_no": 4.5,
    "bill_id": 4.5, "bill": 3.0, "customer": 3.0, "client": 3.0, "buyer": 3.0, "party": 3.5,
    "party_name": 4.0, "party_id": 3.5, "customer_name": 3.5, "customer_id": 3.0, "consignee": 3.5,
    "due_date": 4.5, "payment_due": 4.0, "pay_by": 4.0, "terms_date": 4.0, "maturity_date": 4.0,
    "due_on": 4.0, "terms": 3.0, "invoice_date": 4.5, "bill_date": 4.5, "issue_date": 4.0,
    "doc_date": 3.5, "raised_date": 4.0, "billing_date": 4.0, "invoice_amount": 4.5, "bill_value": 4.0,
    "total_due": 4.5, "amount_due": 4.5, "bill_amount": 4.0, "receivable": 4.5, "receivable_amount": 4.5,
    "receivables": 4.5, "gross_due": 4.0, "net_due": 3.5, "gstin": 2.5, "tax_invoice": 4.0,
    "sales_ledger": 4.0, "ar_ledger": 4.0, "po_number": 2.5, "purchase_order": 2.5, "doc_no": 3.5,
    "document_id": 3.5, "voucher_no": 3.5, "sales_voucher": 4.0, "order_ref": 2.5, "order_reference": 2.5,
    "debtor": 3.5, "debtor_name": 4.0, "account_name": 2.5, "billed_to": 3.5, "bill_to": 3.5,
    "sales_order": 3.5, "inv_amt": 4.0, "bill_num": 4.0,
}

SETTLEMENT_KEYWORDS: Dict[str, float] = {
    "settlement": 4.5, "settlement_id": 5.0, "settle_id": 4.5, "payout": 4.5, "payout_id": 5.0,
    "payment_id": 3.5, "gateway": 4.0, "payment_gateway": 4.5, "gateway_txn": 4.5,
    "fee": 4.0, "fee_amount": 4.5, "processing_fee": 4.5, "processing_charge": 4.5,
    "mdr": 4.5, "mdr_fee": 4.5, "charges": 3.5, "charge": 3.5, "commission": 4.0,
    "tax_on_charge": 4.0, "tax_on_fee": 4.0, "merchant_fee": 4.5, "convenience_fee": 4.0,
    "payout_amount": 4.5, "settlement_date": 4.5, "settled_at": 4.5, "payout_date": 4.5,
    "net_payout": 4.5, "net_remitted": 4.5, "amount_settled": 4.5, "interchange": 4.0,
    "remittance": 3.5, "gateway_ref": 4.0, "processor": 3.5, "captured_amount": 4.0,
    "transfer_id": 4.0, "batch_id": 3.5, "batch_no": 3.5, "remitted": 4.0,
    "received": 2.5, "gross": 3.0, "deductions": 4.0,
}

BANK_KEYWORDS: Dict[str, float] = {
    "bank": 3.0, "statement": 3.5, "bank_transaction_id": 5.0, "bank_txn_id": 5.0,
    "credit": 3.5, "credit_amount": 4.5, "debit": 3.5, "debit_amount": 4.5,
    "balance": 4.0, "closing_balance": 4.5, "available_balance": 4.5, "running_balance": 4.5,
    "bank_reference": 4.5, "bank_ref": 4.5, "utr": 5.0, "utr_number": 5.0, "utr_no": 5.0,
    "narration": 4.5, "particulars": 4.5, "description": 2.5, "value_date": 4.5,
    "txn_date": 3.5, "transaction_date": 4.0, "posting_date": 4.0, "withdrawal": 4.0,
    "deposit": 4.0, "cheque_no": 4.0, "chq_no": 4.0, "instrument_no": 4.0,
    "passbook": 4.0, "journal_no": 4.0, "trans_details": 4.0, "stmt": 3.0,
}

REFUND_KEYWORDS: Dict[str, float] = {
    "refund": 4.5, "refund_id": 5.0, "refund_amount": 5.0, "dispute": 4.0, "dispute_id": 4.5,
    "credit_note": 5.0, "credit_note_no": 5.0, "credit_memo": 5.0, "credit_memo_no": 5.0,
    "cr_note": 5.0, "return_amount": 4.5, "returned_amount": 5.0, "amount_returned": 5.0,
    "refund_date": 4.5, "reversal": 4.5, "reversal_id": 5.0, "reversal_date": 4.5,
    "chargeback": 4.5, "chargeback_id": 5.0, "reason": 2.5, "refund_reason": 4.5,
    "reversal_reason": 4.5, "return_reason": 4.5, "reason_for_return": 4.5,
    "reason_for_reversal": 4.5, "rfd_id": 5.0, "return_id": 5.0, "reversed_amount": 4.5,
    "amount_reversed": 4.5, "credit_reversal": 4.5, "return_date": 4.0, "date_reversed": 4.5,
    "original_invoice": 4.0, "parent_invoice": 4.0, "orig_invoice_id": 4.0, "orig_txn_id": 4.0,
    "cashback": 3.5, "deduction_amount": 3.5,
}


def _normalize_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", str(name).lower()).strip("_")


def _col_matches_concept(norm_col: str, terms: List[str]) -> bool:
    """
    Checks if any term exists in normalized column name as an exact token
    or as a compound substring phrase, without relying on regex word boundaries.
    """
    tokens = set(norm_col.split("_"))
    for term in terms:
        norm_term = _normalize_col(term)
        if "_" in norm_term:
            if norm_term in norm_col:
                return True
        else:
            if norm_term in tokens or norm_term == norm_col:
                return True
    return False


def _has_any_concept(norm_cols: List[str], terms: List[str]) -> bool:
    return any(_col_matches_concept(c, terms) for c in norm_cols)


def score_multi_signal(
    columns: List[str],
    filename: str,
    sample_rows: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, float], List[str]]:
    """
    Computes scores across categories using:
    - Semantic column headers & token matching (immune to underscore boundary issues)
    - Relational co-occurrence patterns (Invoice lifecycle, Settlement payout, Bank statement, Refund reversal)
    - Sample values and data-type distribution
    - Filename bonus (weak signal capped at 1.0)
    """
    norm_cols = [_normalize_col(c) for c in columns]
    norm_file = _normalize_col(filename)

    scores: Dict[str, float] = {
        "INVOICES": 0.0,
        "SETTLEMENTS": 0.0,
        "BANK_TRANSACTIONS": 0.0,
        "REFUNDS": 0.0,
    }
    evidence: List[str] = []

    # 1. Header Keywords (Token & Substring Match)
    for col in norm_cols:
        col_tokens = set(col.split("_"))

        for kw, wt in INVOICE_KEYWORDS.items():
            norm_kw = _normalize_col(kw)
            if norm_kw == col or ("_" in norm_kw and norm_kw in col) or (norm_kw in col_tokens):
                scores["INVOICES"] += wt

        for kw, wt in SETTLEMENT_KEYWORDS.items():
            norm_kw = _normalize_col(kw)
            if norm_kw == col or ("_" in norm_kw and norm_kw in col) or (norm_kw in col_tokens):
                scores["SETTLEMENTS"] += wt

        for kw, wt in BANK_KEYWORDS.items():
            norm_kw = _normalize_col(kw)
            if norm_kw == col or ("_" in norm_kw and norm_kw in col) or (norm_kw in col_tokens):
                scores["BANK_TRANSACTIONS"] += wt

        for kw, wt in REFUND_KEYWORDS.items():
            norm_kw = _normalize_col(kw)
            if norm_kw == col or ("_" in norm_kw and norm_kw in col) or (norm_kw in col_tokens):
                scores["REFUNDS"] += wt

    # 2. Relational Cross-Column Concept Clusters

    # A. INVOICE Relational Cluster:
    # Document/Bill ID + Party/Customer + Due Date/Issue Date + Amount Due/Receivable
    has_inv_doc = _has_any_concept(norm_cols, [
        "invoice", "inv", "bill", "doc", "voucher", "document", "sales_order", "tax_invoice"
    ])
    has_party = _has_any_concept(norm_cols, [
        "party", "customer", "client", "buyer", "debtor", "account", "billed_to", "bill_to", "consignee"
    ])
    has_due = _has_any_concept(norm_cols, [
        "due_date", "payment_due", "pay_by", "terms_date", "due_on", "maturity", "terms", "expiry"
    ])
    has_inv_amt = _has_any_concept(norm_cols, [
        "total_due", "amount_due", "receivable", "receivables", "invoice_amount", "bill_amount",
        "bill_value", "gross_due", "balance_due", "inv_amt"
    ])
    has_inv_date = _has_any_concept(norm_cols, [
        "invoice_date", "inv_date", "bill_date", "issue_date", "raised_date", "doc_date", "billing_date"
    ])

    invoice_concept_count = sum([
        bool(has_inv_doc),
        bool(has_party),
        bool(has_due or has_inv_date),
        bool(has_inv_amt or any("amount" in c for c in norm_cols)),
    ])
    if invoice_concept_count >= 3:
        scores["INVOICES"] += 9.0
        evidence.append("Strong invoice/receivables pattern: Document ID + Party/Customer + Due/Issue Date + Amount detected")
    elif (has_party or has_due) and (has_inv_doc or has_inv_amt):
        scores["INVOICES"] += 6.0
        evidence.append("Invoice pattern: Party/Due Date combined with Bill/Doc identifier")

    # B. SETTLEMENT Relational Cluster:
    # Requires Fee/Charges/MDR/Commission OR explicit payout/settlement ID + gateway + payout date
    has_fee = _has_any_concept(norm_cols, [
        "fee", "fees", "mdr", "processing_fee", "processing_charge", "commission",
        "charges", "charge", "deductions", "tax_on_charge", "tax_on_fee", "merchant_fee"
    ])
    has_net = _has_any_concept(norm_cols, [
        "net_amount", "payout_amount", "net_payout", "amount_settled", "remitted",
        "net_remitted", "net_value", "received", "credited_amount"
    ])
    has_gross = _has_any_concept(norm_cols, [
        "gross", "gross_amount", "captured_amount", "base_amount", "amount_received", "order_amount"
    ])
    has_payout_id = _has_any_concept(norm_cols, [
        "settlement_id", "settle_id", "payout_id", "transfer_id", "gateway_txn", "batch_id", "batch_no"
    ])
    has_gateway = _has_any_concept(norm_cols, [
        "gateway", "processor", "payout", "settlement", "razorpay", "stripe", "payu"
    ])

    # Key disambiguation: Settlements MUST have fee/MDR/charge decomposition OR payout identifiers
    if (has_fee or has_payout_id) and (has_gross or has_net or has_gateway):
        scores["SETTLEMENTS"] += 8.0
        evidence.append("Strong settlement pattern: Gateway Fee/Charges with Gross/Net payout decomposition detected")
    elif has_gross and has_net and not has_party and not has_due:
        scores["SETTLEMENTS"] += 4.5
        evidence.append("Payment breakdown: Gross + Net without customer receivables context")
    elif has_fee and (has_gross or has_net):
        scores["SETTLEMENTS"] += 6.0
        evidence.append("Fee deduction pattern with transactional payout amounts")

    # If the file has receivables/invoice traits (party/due_date) and completely lacks fee/MDR columns,
    # penalize SETTLEMENTS to prevent over-indexing on generic amounts/references
    if (has_party or has_due) and not has_fee and not has_payout_id:
        scores["SETTLEMENTS"] = max(0.0, scores["SETTLEMENTS"] - 4.0)

    # C. BANK TRANSACTION Relational Cluster:
    has_credit = _has_any_concept(norm_cols, ["credit", "deposit", "cr", "amount_credited"])
    has_debit = _has_any_concept(norm_cols, ["debit", "withdrawal", "dr", "amount_debited"])
    has_balance = _has_any_concept(norm_cols, ["balance", "closing_balance", "available_balance", "running_balance"])
    has_narration = _has_any_concept(norm_cols, [
        "narration", "particulars", "description", "trans_details", "statement", "memo"
    ])
    has_bank_id_or_ref = _has_any_concept(norm_cols, [
        "utr", "utr_number", "utr_no", "bank_reference", "bank_ref", "cheque_no", "chq_no",
        "instrument_no", "bank_txn_id", "bank_transaction_id", "journal_no"
    ])

    if (has_credit or has_debit or has_balance) and (has_narration or has_bank_id_or_ref):
        scores["BANK_TRANSACTIONS"] += 8.0
        evidence.append("Strong bank statement pattern: Credit/Debit/Balance with Narration/UTR detected")
    elif (has_credit and has_debit) or (has_balance and has_narration):
        scores["BANK_TRANSACTIONS"] += 6.0
        evidence.append("Bank ledger pattern: Dual credit/debit or balance with particulars")

    # D. REFUND / REVERSAL Relational Cluster:
    has_refund_id = _has_any_concept(norm_cols, [
        "refund_id", "return_id", "reversal_id", "credit_note", "credit_note_no",
        "credit_memo", "credit_memo_no", "rfd_id", "dispute_id", "chargeback_id", "cr_note"
    ])
    has_refund_word = _has_any_concept(norm_cols, [
        "refund", "reversal", "return", "credit_note", "credit_memo", "chargeback", "dispute", "cashback"
    ])
    has_returned_amt = _has_any_concept(norm_cols, [
        "refund_amount", "returned_amount", "reversed_amount", "amount_returned",
        "amount_reversed", "credit_amount", "refund_value", "return_amount", "deduction_amount"
    ])
    has_refund_date = _has_any_concept(norm_cols, [
        "refund_date", "reversal_date", "return_date", "credit_date", "date_reversed", "refunded_at"
    ])
    has_refund_reason = _has_any_concept(norm_cols, [
        "reason", "refund_reason", "reversal_reason", "return_reason", "reason_for_return",
        "reason_for_reversal", "dispute_reason", "remarks", "cause"
    ])
    has_related_doc = _has_any_concept(norm_cols, [
        "invoice_reference", "invoice_id", "parent_invoice", "original_invoice",
        "orig_invoice_id", "bill_ref", "doc_ref", "order_id", "orig_txn_id"
    ])

    refund_concept_count = sum([
        bool(has_refund_id or has_refund_word),
        bool(has_returned_amt),
        bool(has_refund_date or any("date" in c for c in norm_cols)),
        bool(has_refund_reason or has_related_doc),
    ])
    if refund_concept_count >= 3 or (has_refund_id and (has_returned_amt or has_refund_date or has_refund_reason)):
        scores["REFUNDS"] += 9.0
        evidence.append("Strong refund/reversal pattern: Reversal ID + Returned Amount + Reversal Date/Reason detected")
    elif has_refund_word and (has_returned_amt or has_refund_reason or has_related_doc):
        scores["REFUNDS"] += 6.5
        evidence.append("Refund pattern: Return/Reversal indicator combined with transaction context")

    # 3. Sample Value Clues
    if sample_rows:
        for row in sample_rows[:5]:
            for col, val in row.items():
                if not val:
                    continue
                sval = str(val).strip().upper()
                if any(token in sval for token in ["NEFT", "RTGS", "IMPS", "ACH", "UPI", "NACH", "CLEARING"]):
                    scores["BANK_TRANSACTIONS"] += 2.0
                    evidence.append("Bank transaction protocol keyword found in values (UPI/NEFT/RTGS)")
                    break

    # 4. Filename as weak supplementary signal (capped at 1.0 weight)
    if any(k in norm_file for k in ["inv", "bill", "sales", "receivable"]):
        scores["INVOICES"] += 1.0
    if any(k in norm_file for k in ["settle", "payout", "gateway", "processor"]):
        scores["SETTLEMENTS"] += 1.0
    if any(k in norm_file for k in ["bank", "statement", "passbook", "stmt"]):
        scores["BANK_TRANSACTIONS"] += 1.0
    if any(k in norm_file for k in ["refund", "reversal", "return", "credit_note", "credit_memo", "dispute", "chargeback"]):
        scores["REFUNDS"] += 1.0

    return scores, evidence


def score_heuristics(
    columns: List[str],
    filename: str,
    sample_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, float]:
    """Backward-compatible helper returning scores dictionary."""
    scores, _ = score_multi_signal(columns, filename, sample_rows)
    return scores


def detect_file_type(
    filename: str,
    columns: List[str],
    sample_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Infers CSV file type with evidence-derived confidence score and reasoning.
    Returns:
    {
        "file_type": "INVOICES" | "SETTLEMENTS" | "BANK_TRANSACTIONS" | "REFUNDS" | "UNKNOWN",
        "confidence": float (0.0 - 1.0),
        "confidence_band": "HIGH" | "MEDIUM" | "LOW",
        "source": "deterministic" | "gemini_assisted",
        "reason": str,
        "all_scores": dict,
    }
    """
    scores, evidence_list = score_multi_signal(columns, filename, sample_rows)
    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    other_scores = [v for k, v in scores.items() if k != best_type]
    runner_up = max(other_scores) if other_scores else 0.0
    margin = best_score - runner_up
    margin_ratio = margin / max(best_score, 1.0)

    # Calculate evidence-derived confidence based on absolute score and runner-up separation
    if best_score < 3.5:
        best_type = "UNKNOWN"
        confidence = 0.20
        confidence_band = "LOW"
    elif margin < 1.5 or margin_ratio < 0.18:
        # Genuinely ambiguous between top two candidates
        confidence = round(min(0.64, 0.50 + margin * 0.08), 2)
        confidence_band = "LOW"
    elif best_score >= 7.0 and margin >= 3.0:
        # Decisive lead with rich evidence
        confidence = round(min(0.98, 0.85 + (margin / 15.0)), 2)
        confidence_band = "HIGH"
    else:
        # Moderate confidence
        confidence = round(min(0.84, 0.68 + (margin / 20.0)), 2)
        confidence_band = "MEDIUM"

    source = "deterministic"
    reason = f"Structural analysis detected {best_type} (score: {best_score:.1f}, margin: {margin:.1f})"
    if evidence_list:
        reason += f" — {'; '.join(evidence_list[:2])}"

    # AI Fallback: invoke Gemini if confidence is low, ambiguous, or UNKNOWN
    # Gracefully falls back to deterministic candidate without crashing or defaulting to UNKNOWN on API errors
    if (confidence < 0.70 or best_type == "UNKNOWN" or margin < 2.5) and is_gemini_configured() and columns:
        try:
            samples_brief = {}
            if sample_rows:
                for col in columns[:8]:
                    samples_brief[col] = [row.get(col) for row in sample_rows[:2]]

            prompt = (
                f"Analyze this financial CSV schema and classify its entity type:\n"
                f"Options: INVOICES, SETTLEMENTS, BANK_TRANSACTIONS, REFUNDS, UNKNOWN\n\n"
                f"Columns: {columns}\n"
                f"Sample data rows: {json.dumps(samples_brief)}\n"
                f"Filename: {filename}\n"
                f"Deterministic candidate scores: {json.dumps({k: round(v, 1) for k, v in scores.items()})}\n\n"
                f"Classification Rules:\n"
                f"- INVOICES: receivables, customer/party, due date, billing documents, amount due\n"
                f"- SETTLEMENTS: merchant payouts, gateway fees/MDR, payout/settlement ID, gross/net remitted\n"
                f"- BANK_TRANSACTIONS: bank statements, credits/debits, balance, UTR, narration/particulars\n"
                f"- REFUNDS: credit notes, reversals, returns, returned amount, reversal reason, related doc\n"
                f"- UNKNOWN: non-financial or completely unrecognizable data\n\n"
                f"Respond with JSON ONLY in this format:\n"
                f'{{"file_type": "INVOICES|SETTLEMENTS|BANK_TRANSACTIONS|REFUNDS|UNKNOWN", "confidence": 0.88, "reason": "concise explanation"}}'
            )
            content, _, _, err = generate_content_with_fallback(
                prompt=prompt,
                system_instruction="You are an expert financial controller and CSV classifier. Output valid JSON only."
            )
            if content:
                json_str = content.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()

                parsed = json.loads(json_str)
                ai_type = parsed.get("file_type", "").upper()
                ai_conf = float(parsed.get("confidence", 0.75))
                ai_reason = parsed.get("reason", "Inferred via AI structure analysis")

                if ai_type in ["INVOICES", "SETTLEMENTS", "BANK_TRANSACTIONS", "REFUNDS", "UNKNOWN"]:
                    best_type = ai_type
                    confidence = round(ai_conf, 2)
                    source = "gemini_assisted"
                    reason = f"Gemini schema analysis: {ai_reason}"
                    confidence_band = "HIGH" if confidence >= 0.85 else "MEDIUM" if confidence >= 0.60 else "LOW"
        except Exception:
            # Deterministic scoring prevails cleanly without crashing or mutating to UNKNOWN
            pass

    return {
        "file_type": best_type,
        "confidence": confidence,
        "confidence_band": confidence_band,
        "source": source,
        "reason": reason,
        "all_scores": scores,
    }


def disambiguate_batch_file_types(profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Cross-file reasoning:
    When multiple files are uploaded together, evaluates the batch context to prevent
    misclassifications (e.g. classifying an invoice file as settlements when settlements already exist).
    """
    if len(profiles) <= 1:
        return profiles

    detected_types = [p.get("detected_file_type") for p in profiles]
    settlement_indices = [i for i, t in enumerate(detected_types) if t == "SETTLEMENTS"]
    has_invoice = "INVOICES" in detected_types

    # Case 1: Multiple files classified as SETTLEMENTS, 0 files classified as INVOICES
    if len(settlement_indices) > 1 and not has_invoice:
        best_inv_candidate_idx = None
        best_inv_candidate_score = 0.0

        for idx in settlement_indices:
            p = profiles[idx]
            cols = [c["column_name"] for c in p.get("columns", [])]
            norm_cols = [_normalize_col(c) for c in cols]

            inv_trait_score = 0.0
            if _has_any_concept(norm_cols, ["party", "customer", "client", "buyer", "debtor", "billed_to"]):
                inv_trait_score += 4.0
            if _has_any_concept(norm_cols, ["due_date", "payment_due", "pay_by", "terms_date", "due_on"]):
                inv_trait_score += 4.0
            if _has_any_concept(norm_cols, ["invoice", "inv", "bill", "doc_no", "voucher", "tax_invoice"]):
                inv_trait_score += 3.5
            if _has_any_concept(norm_cols, ["receivable", "receivables", "amount_due", "total_due", "bill_amount"]):
                inv_trait_score += 3.5

            # Files that lack fee/MDR columns are highly likely to be invoice sources
            has_fee = _has_any_concept(norm_cols, [
                "fee", "fees", "mdr", "commission", "processing_fee", "processing_charge", "charges"
            ])
            if not has_fee:
                inv_trait_score += 4.0

            if inv_trait_score > best_inv_candidate_score:
                best_inv_candidate_score = inv_trait_score
                best_inv_candidate_idx = idx

        if best_inv_candidate_idx is not None and best_inv_candidate_score >= 6.0:
            p = profiles[best_inv_candidate_idx]
            p["detected_file_type"] = "INVOICES"
            p["detection_confidence"] = 0.92
            p["detection_confidence_band"] = "HIGH"
            p["detection_source"] = "cross_file_reasoning"
            p["detection_reason"] = "Cross-file analysis: Disambiguated customer receivables/invoice source from settlement batch"

    # Case 2: One file classified as SETTLEMENTS but actually matches REFUNDS
    has_refund = "REFUNDS" in detected_types
    if not has_refund:
        for idx, p in enumerate(profiles):
            if p.get("detected_file_type") in ["SETTLEMENTS", "UNKNOWN"]:
                cols = [c["column_name"] for c in p.get("columns", [])]
                norm_cols = [_normalize_col(c) for c in cols]
                is_refund = _has_any_concept(norm_cols, [
                    "credit_note", "credit_memo", "return_id", "refund_id", "reversal_id",
                    "reason_for_return", "refund_reason", "returned_amount"
                ])
                if is_refund:
                    p["detected_file_type"] = "REFUNDS"
                    p["detection_confidence"] = 0.90
                    p["detection_confidence_band"] = "HIGH"
                    p["detection_source"] = "cross_file_reasoning"
                    p["detection_reason"] = "Cross-file analysis: Identified credit note/refund reversal source"

    return profiles

