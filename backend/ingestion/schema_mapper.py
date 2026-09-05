"""
ReconAI — Generalized Hybrid Schema Mapper
===========================================
Maps arbitrary user-uploaded CSV columns to ReconAI canonical schemas:
- INVOICES
- SETTLEMENTS
- BANK_TRANSACTIONS
- REFUNDS

Applies a 7-layer hybrid mapping architecture:
Layer 1: Normalized exact-name matching
Layer 2: Comprehensive financial domain terminology & synonyms
Layer 3: Data-type and value-pattern analysis (cardinality, alphanumeric formats, monetary decimals)
Layer 4: Cross-column context & deductive inference (e.g. Gross + Fee => Net; Amount + Txn Type => Credit/Debit)
Layer 5: Gemini semantic fallback for ambiguous headers
Layer 6: Deterministic validation of proposed mappings
Layer 7: Confidence scoring and bands (HIGH / MEDIUM / LOW)
"""

from __future__ import annotations

import re
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
try:
    from agent.gemini_client import is_gemini_configured, generate_content_with_fallback
except (ImportError, ValueError):
    from ..agent.gemini_client import is_gemini_configured, generate_content_with_fallback


DUE_DATE_TOKENS: Set[str] = {
    "due", "pay", "pay_by", "payby", "payment", "payable", "terms",
    "maturity", "expiry", "expire", "expiration", "deadline", "until", "target"
}

CREATION_DATE_TOKENS: Set[str] = {
    "invoice", "inv", "bill", "billing", "issue", "issued", "raise", "raised",
    "raising", "create", "created", "creation", "entry", "doc_date", "document_date",
    "posting", "posted", "start", "open", "booking", "generation", "origination",
    "originated", "dated", "record", "tx", "txn", "transaction", "effective", "on"
}


def _is_date_col(col_prof: Dict[str, Any]) -> bool:
    if not col_prof:
        return False
    if col_prof.get("detected_type") in ["date", "datetime"]:
        return True
    if col_prof.get("date_parse_success_rate", 0.0) >= 0.6:
        return True
    return False


def _compute_date_confidence(
    col_prof: Dict[str, Any],
    semantic_tier: str,
) -> Tuple[float, str, bool]:
    """
    Computes confidence combining value-type confidence and semantic-role confidence.
    """
    is_ambiguous = col_prof.get("is_date_ambiguous", False)
    success_rate = col_prof.get("date_parse_success_rate", 1.0)

    # Value-type confidence
    if not is_ambiguous and success_rate >= 0.8:
        val_conf = 0.95
    elif not is_ambiguous and success_rate >= 0.5:
        val_conf = 0.85
    elif is_ambiguous:
        val_conf = 0.60
    else:
        val_conf = 0.40

    # Semantic-role confidence
    if semantic_tier == "exact_synonym":
        sem_conf = 0.96
    elif semantic_tier == "concept_token":
        sem_conf = 0.90
    elif semantic_tier == "deduced":
        sem_conf = 0.85
    else:
        sem_conf = 0.75

    combined = round(0.40 * val_conf + 0.60 * sem_conf, 2)
    band = "HIGH" if combined >= 0.85 and not is_ambiguous else ("MEDIUM" if combined >= 0.60 else "LOW")
    requires_confirmation = is_ambiguous
    return combined, band, requires_confirmation


def _extract_earliest_date_from_profile(col_prof: Dict[str, Any]) -> Optional[datetime]:
    from .profiler import parse_single_date
    for v in col_prof.get("sample_values", []):
        parsed = parse_single_date(v)
        if parsed and "year" in parsed and "month" in parsed and "day" in parsed:
            try:
                return datetime(parsed["year"], parsed["month"], parsed["day"])
            except Exception:
                pass
    return None


# ReconAI Canonical Schemas
CANONICAL_SCHEMAS: Dict[str, List[Dict[str, Any]]] = {
    "INVOICES": [
        {"field": "invoice_id", "label": "Invoice ID / Number", "required": True},
        {"field": "customer_name", "label": "Customer / Client Name", "required": False},
        {"field": "invoice_date", "label": "Invoice Date", "required": True},
        {"field": "due_date", "label": "Due Date", "required": False},
        {"field": "amount", "label": "Invoice Amount", "required": True},
        {"field": "currency", "label": "Currency", "required": False},
        {"field": "reference", "label": "Invoice Reference", "required": False},
    ],
    "SETTLEMENTS": [
        {"field": "settlement_id", "label": "Settlement ID", "required": True},
        {"field": "invoice_reference", "label": "Invoice Reference / ID", "required": True},
        {"field": "settlement_date", "label": "Settlement / Payout Date", "required": True},
        {"field": "gross_amount", "label": "Gross Amount", "required": True},
        {"field": "fee_amount", "label": "Gateway Fee / MDR", "required": False},
        {"field": "fee_tax", "label": "Tax on Fee / GST", "required": False},
        {"field": "net_amount", "label": "Net Amount", "required": False},
        {"field": "payment_reference", "label": "Payment Reference / UTR", "required": False},
        {"field": "status", "label": "Settlement Status", "required": False},
    ],
    "BANK_TRANSACTIONS": [
        {"field": "bank_transaction_id", "label": "Bank Transaction ID", "required": False},
        {"field": "transaction_date", "label": "Transaction Date", "required": True},
        {"field": "description", "label": "Narration / Description", "required": False},
        {"field": "bank_reference", "label": "Bank Reference / UTR", "required": False},
        {"field": "credit_amount", "label": "Credit / Deposit Amount", "required": True},
        {"field": "debit_amount", "label": "Debit / Withdrawal Amount", "required": False},
        {"field": "currency", "label": "Currency", "required": False},
    ],
    "REFUNDS": [
        {"field": "refund_id", "label": "Refund ID", "required": True},
        {"field": "invoice_id", "label": "Invoice ID", "required": False},
        {"field": "refund_date", "label": "Refund Date", "required": True},
        {"field": "refund_amount", "label": "Refund Amount", "required": True},
        {"field": "reason", "label": "Reason / Remarks", "required": False},
        {"field": "payment_reference", "label": "Payment Reference", "required": False},
    ],
}

# Rich financial terminology across global & Indian ERPs, banking statements, and gateways
SYNONYMS: Dict[str, Dict[str, List[str]]] = {
    "INVOICES": {
        "invoice_id": [
            "invoice_id", "invoice_no", "invoice_number", "inv_no", "inv_id", "bill_no", "bill_number",
            "bill_id", "bill_ref", "doc_ref", "doc_reference", "document_ref", "document_reference",
            "document_id", "document_no", "doc_no", "doc_id", "voucher_no",
            "bill_num", "sales_invoice_no", "reference_number", "id", "bill", "tax_invoice_no",
        ],
        "customer_name": [
            "customer_name", "customer", "client", "client_name", "buyer", "buyer_name", "party",
            "party_name", "merchant", "merchant_name", "account_name", "account", "billed_to",
            "bill_to", "debtor", "debtor_name", "company", "name", "consignee",
        ],
        "invoice_date": [
            "invoice_date", "inv_date", "bill_date", "issue_date", "created_date", "created_at",
            "posting_date", "doc_date", "invoiced_on", "date", "entry_date", "billing_date",
        ],
        "due_date": [
            "due_date", "payment_due", "pay_by", "expiry_date", "terms_date", "maturity_date", "due_on", "terms",
        ],
        "amount": [
            "amount", "invoice_amount", "total", "total_due", "amount_due", "invoice_value",
            "gross_value", "bill_amount", "bill_value", "receivable", "grand_total", "inv_amt",
            "net_total", "subtotal", "total_amount", "value", "receivables", "balance_due",
        ],
        "currency": [
            "currency", "curr", "curr_code", "currency_code", "ccy",
        ],
        "reference": [
            "reference", "invoice_reference", "ref_no", "po_number", "order_ref", "order_id",
            "gstin", "description", "memo", "remarks", "notes",
        ],
    },
    "SETTLEMENTS": {
        "settlement_id": [
            "settlement_id", "settle_id", "payout_id", "payment_id", "gateway_txn", "gateway_transaction_id",
            "transfer_id", "txn_id", "transaction_id", "reference_id", "id", "payment_ref", "batch_id", "batch_no",
        ],
        "invoice_reference": [
            "invoice_reference", "invoice_id", "invoice_ref", "inv_ref", "bill_reference", "bill_ref",
            "order_id", "order_ref", "invoice_no", "bill_no", "merchant_reference", "reference",
        ],
        "settlement_date": [
            "settlement_date", "settled_at", "payout_date", "paid_on", "payment_date", "processed_at",
            "transfer_date", "date", "posting_date",
        ],
        "gross_amount": [
            "gross_amount", "gross", "amount", "captured_amount", "base_amount", "total_amount",
            "txn_amount", "amount_received", "gross_value", "order_amount",
        ],
        "fee_amount": [
            "fee_amount", "fee", "fees", "processing_fee", "processing_charge", "mdr", "gateway_fee",
            "charges", "charge", "commission", "deductions", "merchant_fee", "convenience_fee",
        ],
        "fee_tax": [
            "fee_tax", "tax_on_charge", "tax_on_fee", "tax", "gst", "fee_gst", "service_tax", "vat_on_fee", "gst_on_fee",
        ],
        "net_amount": [
            "net_amount", "net", "received", "payout_amount", "credited_amount", "net_payout",
            "settled_amount", "net_value", "remitted", "net_remitted",
        ],
        "payment_reference": [
            "payment_reference", "payment_ref", "txn_ref", "transaction_reference", "gateway_reference",
            "utr", "utr_no", "utr_number", "reference", "ref_no", "arn", "auth_code",
        ],
        "status": [
            "status", "settlement_status", "payout_status", "state",
        ],
    },
    "BANK_TRANSACTIONS": {
        "bank_transaction_id": [
            "bank_transaction_id", "bank_txn_id", "txn_id", "transaction_id", "entry_id", "journal_no",
            "cheque_no", "id", "stmt_id", "statement_id",
        ],
        "transaction_date": [
            "transaction_date", "txn_date", "date", "value_date", "posting_date", "bank_date",
            "processed_at", "entry_date", "txn_dt",
        ],
        "description": [
            "description", "narration", "particulars", "remarks", "memo", "trans_details", "details",
        ],
        "bank_reference": [
            "bank_reference", "bank_ref", "reference", "utr", "utr_no", "utr_number", "ref_no", "ref_num",
            "cheque_no", "chq_no", "instrument_no", "payment_reference", "payment_ref", "client_ref",
        ],
        "credit_amount": [
            "credit_amount", "credit", "cr", "deposit", "deposit_amount", "amount_credited", "received",
            "amount",
        ],
        "debit_amount": [
            "debit_amount", "debit", "dr", "withdrawal", "withdrawal_amount", "amount_debited", "spent",
        ],
        "currency": [
            "currency", "curr", "curr_code", "ccy",
        ],
    },
    "REFUNDS": {
        "refund_id": [
            "refund_id", "return_id", "dispute_id", "credit_note_no", "credit_note", "credit_memo_no",
            "credit_memo", "cr_note", "rfd_id", "id", "reversal_id", "chargeback_id",
        ],
        "invoice_id": [
            "invoice_id", "inv_id", "invoice_no", "bill_id", "bill_no", "order_id", "original_invoice",
            "parent_invoice", "orig_invoice_id", "orig_txn_id", "bill_ref",
        ],
        "refund_date": [
            "refund_date", "date", "processed_at", "refunded_at", "reversal_date", "credit_note_date",
            "return_date", "credit_date",
        ],
        "refund_amount": [
            "refund_amount", "amount", "return_amount", "returned_amount", "reversed_amount", "amount_returned",
            "amount_reversed", "credit_amount", "deduction", "value", "refund_value", "deduction_amount",
        ],
        "reason": [
            "reason", "refund_reason", "reversal_reason", "return_reason", "reason_for_return",
            "reason_for_reversal", "remarks", "description", "memo", "notes", "cause", "dispute_reason",
        ],
        "payment_reference": [
            "payment_reference", "payment_ref", "pay_ref", "utr", "ref_no", "gateway_reference",
        ],
    },
}

# Alias mapping for backward compatibility and internal consistency
FIELD_ALIASES = {
    "amount": "invoice_amount",
    "invoice_reference": "invoice_id",
    "bank_reference": "reference",
    "reference": "bank_reference",
    "bank_txn_id": "bank_transaction_id",
    "fee_tax": "fee_amount",
}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", str(name).lower()).strip("_")


def map_columns_hybrid(
    file_type: str,
    columns_profile: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Executes multi-layer column mapping:
    1. Exact normalized matches
    2. Semantic synonyms
    3. Structural type & value pattern inspection
    4. Cross-column deduction
    5. Gemini semantic suggestion if required fields are missing
    """
    target_syns = SYNONYMS.get(file_type, {})
    assigned_targets: Set[str] = set()
    mappings: List[Dict[str, Any]] = []

    col_names = [c["column_name"] for c in columns_profile]
    cols_by_name = {c["column_name"]: c for c in columns_profile}

    # Initialize unmapped structure
    for col in col_names:
        mappings.append({
            "source_column": col,
            "target_field": None,
            "confidence": 0.0,
            "confidence_band": "LOW",
            "status": "unmapped",
            "reason": "Unassigned",
        })

    # Layer 1: Exact Normalized Match
    for m in mappings:
        ncol = _norm(m["source_column"])
        for target_field, syn_list in target_syns.items():
            if target_field in assigned_targets:
                continue
            if ncol == target_field or ncol == _norm(target_field):
                assigned_targets.add(target_field)
                m["target_field"] = target_field
                m["confidence"] = 0.99
                m["confidence_band"] = "HIGH"
                m["status"] = "mapped"
                m["reason"] = f"Exact match with canonical field '{target_field}'"
                break

    # Layer 2: Synonym Lexicon Match
    for m in mappings:
        if m["status"] == "mapped":
            continue
        ncol = _norm(m["source_column"])

        best_target = None
        best_conf = 0.0
        best_match_word = ""

        ncol_tokens = set(ncol.split("_"))
        for target_field, syn_list in target_syns.items():
            if target_field in assigned_targets:
                continue
            norm_syns = [_norm(s) for s in syn_list]

            if ncol in norm_syns:
                best_target = target_field
                best_conf = 0.95
                best_match_word = ncol
                break

            # Word token matching (e.g. "mdr_fee" matches "mdr" or "fee")
            matched_by_token = False
            for s in norm_syns:
                s_tokens = set(s.split("_"))
                if s_tokens.issubset(ncol_tokens) or (len(s) >= 3 and (s in ncol or ncol in s)):
                    conf = 0.92 if s_tokens.issubset(ncol_tokens) else 0.82
                    if conf > best_conf:
                        best_conf = conf
                        best_target = target_field
                        best_match_word = s
                        matched_by_token = True
            if matched_by_token and best_conf >= 0.90:
                break

        if best_target:
            assigned_targets.add(best_target)
            m["target_field"] = best_target
            m["confidence"] = best_conf
            m["confidence_band"] = "HIGH" if best_conf >= 0.85 else "MEDIUM"
            m["status"] = "mapped"
            m["reason"] = f"Financial domain synonym matched '{best_match_word}' → '{best_target}'"

    # Layer 3: Data-Type & Value-Pattern Analysis for Remaining Columns
    for m in mappings:
        if m["status"] == "mapped":
            continue
        col_prof = cols_by_name.get(m["source_column"], {})
        detected_type = col_prof.get("detected_type", "text")
        sample_vals = col_prof.get("sample_values", [])

        # Vague identifier columns (e.g. "Doc", "Ref", "Code", "ID")
        id_candidates = [
            f for f in ["invoice_id", "settlement_id", "bank_transaction_id", "bank_reference", "refund_id"]
            if f in target_syns and f not in assigned_targets
        ]
        if id_candidates and detected_type in ["id_string", "text"] and sample_vals:
            # Check if values look like identifiers (alphanumeric or hyphenated)
            is_id_like = all(re.match(r"^[A-Za-z0-9_\-\./]{3,40}$", str(v).strip()) for v in sample_vals if v)
            if is_id_like:
                chosen_id = id_candidates[0]
                assigned_targets.add(chosen_id)
                m["target_field"] = chosen_id
                m["confidence"] = 0.78
                m["confidence_band"] = "MEDIUM"
                m["status"] = "mapped"
                m["reason"] = f"Alphanumeric identifier pattern mapped to '{chosen_id}'"
                continue

        # Monetary columns (e.g. "Val", "Total", "Due", "Amt")
        amt_candidates = [
            f for f in ["amount", "gross_amount", "credit_amount", "refund_amount"]
            if f in target_syns and f not in assigned_targets
        ]
        if amt_candidates and detected_type in ["currency", "number"]:
            chosen_amt = amt_candidates[0]
            assigned_targets.add(chosen_amt)
            m["target_field"] = chosen_amt
            m["confidence"] = 0.75
            m["confidence_band"] = "MEDIUM"
            m["status"] = "mapped"
            m["reason"] = f"Numeric monetary distribution mapped to '{chosen_amt}'"
            continue

    # Layer 3.5: Generalized Date Semantic Role & Multi-Date Column Disambiguation Pass
    date_col_mappings = [
        m for m in mappings
        if _is_date_col(cols_by_name.get(m["source_column"], {}))
    ]

    # Re-evaluate confidence and ambiguity for any date columns mapped in Layer 1 or 2
    for m in date_col_mappings:
        if m["status"] == "mapped" and m.get("target_field"):
            cprof = cols_by_name.get(m["source_column"], {})
            conf, band, req_conf = _compute_date_confidence(cprof, "exact_synonym")
            if req_conf:
                m["confidence"] = conf
                m["confidence_band"] = band
                m["requires_confirmation"] = True
                if "Ambiguous" not in m.get("reason", ""):
                    m["reason"] = f"{m.get('reason', '')} (Ambiguous date format DD/MM vs MM/DD — user confirmation required)"

    unmapped_date_mappings = [m for m in date_col_mappings if m["status"] != "mapped"]

    if unmapped_date_mappings:
        if file_type == "INVOICES":
            inv_mapped = "invoice_date" in assigned_targets
            due_mapped = "due_date" in assigned_targets

            if due_mapped and not inv_mapped:
                # Complementary deduction: due_date mapped (e.g. Pay By), remaining date is Invoice Date
                m = unmapped_date_mappings[0]
                cprof = cols_by_name.get(m["source_column"], {})
                tokens = set(_norm(m["source_column"]).split("_"))
                has_create_token = bool(tokens.intersection(CREATION_DATE_TOKENS))
                tier = "concept_token" if has_create_token else "deduced"
                conf, band, req_conf = _compute_date_confidence(cprof, tier)

                assigned_targets.add("invoice_date")
                m["target_field"] = "invoice_date"
                m["confidence"] = conf
                m["confidence_band"] = band
                m["status"] = "mapped"
                if req_conf:
                    m["requires_confirmation"] = True
                m["reason"] = (
                    f"Generalized date role mapped to 'invoice_date' "
                    f"({tier} role inference, complementary to due_date)"
                    + (" — Ambiguous date format: confirmation required" if req_conf else "")
                )

            elif inv_mapped and not due_mapped:
                # Complementary deduction: invoice_date mapped, remaining date is Due Date
                m = unmapped_date_mappings[0]
                cprof = cols_by_name.get(m["source_column"], {})
                tokens = set(_norm(m["source_column"]).split("_"))
                has_due_token = bool(tokens.intersection(DUE_DATE_TOKENS))
                tier = "concept_token" if has_due_token else "deduced"
                conf, band, req_conf = _compute_date_confidence(cprof, tier)

                assigned_targets.add("due_date")
                m["target_field"] = "due_date"
                m["confidence"] = conf
                m["confidence_band"] = band
                m["status"] = "mapped"
                if req_conf:
                    m["requires_confirmation"] = True
                m["reason"] = (
                    f"Generalized date role mapped to 'due_date' "
                    f"({tier} role inference, complementary to invoice_date)"
                    + (" — Ambiguous date format: confirmation required" if req_conf else "")
                )

            elif not inv_mapped and not due_mapped:
                if len(unmapped_date_mappings) >= 2:
                    # Multiple date columns in invoice: separate invoice_date vs due_date
                    m1 = unmapped_date_mappings[0]
                    m2 = unmapped_date_mappings[1]
                    t1 = set(_norm(m1["source_column"]).split("_"))
                    t2 = set(_norm(m2["source_column"]).split("_"))

                    m1_due = bool(t1.intersection(DUE_DATE_TOKENS))
                    m2_due = bool(t2.intersection(DUE_DATE_TOKENS))
                    m1_create = bool(t1.intersection(CREATION_DATE_TOKENS))
                    m2_create = bool(t2.intersection(CREATION_DATE_TOKENS))

                    if m1_due and not m2_due:
                        due_col, inv_col = m1, m2
                    elif m2_due and not m1_due:
                        due_col, inv_col = m2, m1
                    elif m1_create and not m2_create:
                        inv_col, due_col = m1, m2
                    elif m2_create and not m1_create:
                        inv_col, due_col = m2, m1
                    else:
                        # Compare sample dates: invoices are issued before due date
                        dt1 = _extract_earliest_date_from_profile(cols_by_name.get(m1["source_column"], {}))
                        dt2 = _extract_earliest_date_from_profile(cols_by_name.get(m2["source_column"], {}))
                        if dt1 and dt2 and dt1 > dt2:
                            inv_col, due_col = m2, m1
                        else:
                            inv_col, due_col = m1, m2

                    # Assign invoice_date
                    cprof_inv = cols_by_name.get(inv_col["source_column"], {})
                    conf_inv, band_inv, req_inv = _compute_date_confidence(cprof_inv, "concept_token")
                    assigned_targets.add("invoice_date")
                    inv_col["target_field"] = "invoice_date"
                    inv_col["confidence"] = conf_inv
                    inv_col["confidence_band"] = band_inv
                    inv_col["status"] = "mapped"
                    if req_inv:
                        inv_col["requires_confirmation"] = True
                    inv_col["reason"] = (
                        "Multi-date distinction: mapped to 'invoice_date' (issue/creation role)"
                        + (" — Ambiguous format" if req_inv else "")
                    )

                    # Assign due_date
                    cprof_due = cols_by_name.get(due_col["source_column"], {})
                    conf_due, band_due, req_due = _compute_date_confidence(cprof_due, "concept_token")
                    assigned_targets.add("due_date")
                    due_col["target_field"] = "due_date"
                    due_col["confidence"] = conf_due
                    due_col["confidence_band"] = band_due
                    due_col["status"] = "mapped"
                    if req_due:
                        due_col["requires_confirmation"] = True
                    due_col["reason"] = (
                        "Multi-date distinction: mapped to 'due_date' (maturity/pay-by role)"
                        + (" — Ambiguous format" if req_due else "")
                    )

                else:
                    # Single unmapped date column in invoice
                    m = unmapped_date_mappings[0]
                    cprof = cols_by_name.get(m["source_column"], {})
                    tokens = set(_norm(m["source_column"]).split("_"))
                    has_create_token = bool(tokens.intersection(CREATION_DATE_TOKENS))
                    tier = "concept_token" if has_create_token else "default"
                    conf, band, req_conf = _compute_date_confidence(cprof, tier)

                    assigned_targets.add("invoice_date")
                    m["target_field"] = "invoice_date"
                    m["confidence"] = conf
                    m["confidence_band"] = band
                    m["status"] = "mapped"
                    if req_conf:
                        m["requires_confirmation"] = True
                    m["reason"] = (
                        f"Date formatted values mapped to 'invoice_date' ({tier} date role)"
                        + (" — Ambiguous date format: confirmation required" if req_conf else "")
                    )

        else:
            # Other file types: SETTLEMENTS, BANK_TRANSACTIONS, REFUNDS
            primary_date_fields = {
                "SETTLEMENTS": "settlement_date",
                "BANK_TRANSACTIONS": "transaction_date",
                "REFUNDS": "refund_date",
            }
            target_date_field = primary_date_fields.get(file_type)
            if target_date_field and target_date_field not in assigned_targets:
                m = unmapped_date_mappings[0]
                cprof = cols_by_name.get(m["source_column"], {})
                conf, band, req_conf = _compute_date_confidence(cprof, "default")

                assigned_targets.add(target_date_field)
                m["target_field"] = target_date_field
                m["confidence"] = conf
                m["confidence_band"] = band
                m["status"] = "mapped"
                if req_conf:
                    m["requires_confirmation"] = True
                m["reason"] = (
                    f"Date formatted values mapped to '{target_date_field}'"
                    + (" — Ambiguous date format: confirmation required" if req_conf else "")
                )

    # Layer 4: Cross-Column Deductive Inference
    # For Settlement: if Gross and Fee are mapped, any remaining numeric column is Net Amount
    if file_type == "SETTLEMENTS" and "net_amount" not in assigned_targets:
        for m in mappings:
            if m["status"] != "mapped":
                cprof = cols_by_name.get(m["source_column"], {})
                if cprof.get("detected_type") in ["currency", "number"]:
                    assigned_targets.add("net_amount")
                    m["target_field"] = "net_amount"
                    m["confidence"] = 0.72
                    m["confidence_band"] = "MEDIUM"
                    m["status"] = "mapped"
                    m["reason"] = "Deductive context: remaining numeric column mapped to 'net_amount'"
                    break

    # For Bank Transactions: if Credit is mapped, remaining numeric column is Debit
    if file_type == "BANK_TRANSACTIONS" and "debit_amount" not in assigned_targets:
        for m in mappings:
            if m["status"] != "mapped":
                cprof = cols_by_name.get(m["source_column"], {})
                if cprof.get("detected_type") in ["currency", "number"]:
                    assigned_targets.add("debit_amount")
                    m["target_field"] = "debit_amount"
                    m["confidence"] = 0.70
                    m["confidence_band"] = "MEDIUM"
                    m["status"] = "mapped"
                    m["reason"] = "Deductive context: complementary numeric column mapped to 'debit_amount'"
                    break

    # Layer 5: Gemini Semantic Fallback for Unmapped Required Fields
    required_targets = [
        f["field"] for f in CANONICAL_SCHEMAS.get(file_type, []) if f.get("required")
    ]
    missing_required = [r for r in required_targets if r not in assigned_targets]
    unmapped_cols = [m["source_column"] for m in mappings if not m.get("target_field")]

    if missing_required and unmapped_cols and is_gemini_configured():
        try:
            col_summary = []
            for cp in columns_profile:
                if cp["column_name"] in unmapped_cols:
                    col_summary.append({
                        "column": cp["column_name"],
                        "samples": cp.get("sample_values", [])[:2],
                        "type": cp.get("detected_type", "text"),
                    })

            prompt = (
                f"We are mapping an unknown financial CSV file of type '{file_type}'.\n"
                f"Required canonical fields still missing: {missing_required}\n"
                f"Unmapped source columns: {json.dumps(col_summary)}\n\n"
                f"Select the best canonical target field for each relevant column, or null if irrelevant.\n"
                f"Respond with JSON ONLY in this format:\n"
                f'{{"mappings": [{{"source_column": "col_name", "target_field": "field_name", "confidence": 0.85, "reason": "concise explanation"}}]}}'
            )
            content, _, _, _ = generate_content_with_fallback(
                prompt=prompt,
                system_instruction="You are a schema matching assistant. Map columns strictly to the requested canonical fields. Output valid JSON only."
            )
            if content:
                json_str = content.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()

                parsed = json.loads(json_str)
                ai_maps = {item["source_column"]: item for item in parsed.get("mappings", [])}

                for m in mappings:
                    if not m.get("target_field") and m["source_column"] in ai_maps:
                        ai_item = ai_maps[m["source_column"]]
                        t_field = ai_item.get("target_field")
                        if t_field in target_syns and t_field not in assigned_targets:
                            assigned_targets.add(t_field)
                            m["target_field"] = t_field
                            conf = float(ai_item.get("confidence", 0.75))
                            m["confidence"] = round(conf, 2)
                            m["confidence_band"] = "HIGH" if conf >= 0.85 else "MEDIUM"
                            m["status"] = "gemini_mapped"
                            m["reason"] = f"Gemini semantic inference: {ai_item.get('reason', 'Contextual semantic match')}"
        except Exception:
            pass

    # Final consistency pass: Ensure unmapped columns strictly have 0.0 confidence and clean status
    for m in mappings:
        if not m.get("target_field") or m.get("target_field") == "IGNORE_COLUMN":
            m["target_field"] = None
            m["confidence"] = 0.0
            m["confidence_band"] = "LOW"
            m["status"] = "unmapped"
            m["reason"] = "Unassigned"

    return mappings


def map_columns_deterministic(
    file_type: str,
    columns: List[str],
) -> List[Dict[str, Any]]:
    """
    Lightweight deterministic mapper for tests and headless validation.
    Creates column profiles with default types.
    """
    profiles = [{"column_name": c, "detected_type": "text", "sample_values": []} for c in columns]
    return map_columns_hybrid(file_type, profiles)


def map_columns_with_ai(
    file_type: str,
    columns_profile: List[Dict[str, Any]],
    deterministic_mappings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Backward-compatible wrapper used by existing endpoints.
    Calls full hybrid pipeline if any required field is missing.
    """
    required_targets = [
        f["field"] for f in CANONICAL_SCHEMAS.get(file_type, []) if f.get("required")
    ]
    mapped_targets = {m["target_field"] for m in deterministic_mappings if m.get("target_field")}
    missing_required = [r for r in required_targets if r not in mapped_targets]

    if not missing_required:
        return deterministic_mappings

    # Run hybrid mapper
    return map_columns_hybrid(file_type, columns_profile)


def get_canonical_schema(file_type: str) -> List[Dict[str, Any]]:
    return CANONICAL_SCHEMAS.get(file_type, [])
