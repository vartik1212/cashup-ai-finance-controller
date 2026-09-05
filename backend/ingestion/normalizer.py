"""
ReconAI — Record Normalizer & Persistence
=========================================
Converts validated canonical records into existing Pydantic domain models
and persists them into SQLite source tables.
Enters the EXACT existing LangGraph pipeline.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from ..models.schemas import Invoice, Settlement, BankTransaction
from ..database.db import get_db


def normalize_and_store(
    invoices_data: List[Dict[str, Any]],
    settlements_data: List[Dict[str, Any]],
    bank_data: List[Dict[str, Any]],
    refunds_data: Optional[List[Dict[str, Any]]] = None,
    source_metadata: Optional[Dict[str, Any]] = None,
    clear_existing: bool = True,
    dataset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Stores normalized records into isolated uploaded_* tables and synchronizes active tables.
    If clear_existing is True (default for uploads), clears uploaded_* tables and active tables first.
    If clear_existing is False, appends new records to uploaded dataset without duplicating existing IDs.
    Benchmark dataset is NEVER touched.
    """
    with get_db() as conn:
        if clear_existing:
            # Clear uploaded tables and active tables
            conn.execute("DELETE FROM uploaded_invoices")
            conn.execute("DELETE FROM uploaded_settlements")
            conn.execute("DELETE FROM uploaded_bank_transactions")
            conn.execute("DELETE FROM uploaded_refunds")
            conn.execute("DELETE FROM invoices")
            conn.execute("DELETE FROM settlements")
            conn.execute("DELETE FROM bank_transactions")
            conn.execute("DELETE FROM refunds")

        # Fetch existing IDs from uploaded_* (never from benchmark)
        existing_inv_ids = set(r[0] for r in conn.execute("SELECT invoice_id FROM uploaded_invoices").fetchall())
        existing_set_ids = set(r[0] for r in conn.execute("SELECT settlement_id FROM uploaded_settlements").fetchall())
        existing_bnk_ids = set(r[0] for r in conn.execute("SELECT bank_txn_id FROM uploaded_bank_transactions").fetchall())
        existing_rfd_ids = set(r[0] for r in conn.execute("SELECT refund_id FROM uploaded_refunds").fetchall())

        inserted_invoices = 0
        inserted_settlements = 0
        inserted_bank = 0
        inserted_refunds = 0

        # Insert Invoices (skip if already exists in uploaded dataset)
        for inv in invoices_data:
            iid = inv["invoice_id"]
            if iid in existing_inv_ids and not clear_existing:
                continue
            for tbl in ["uploaded_invoices", "invoices"]:
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {tbl}
                    (invoice_id, customer_name, customer_id, invoice_amount, invoice_date,
                     due_date, currency, description, gstin, ground_truth_scenario, expected_match_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        iid,
                        inv.get("customer_name", "Unknown Client"),
                        inv.get("customer_id", f"CUST-{iid[:4]}"),
                        inv["invoice_amount"],
                        inv["invoice_date"],
                        inv.get("due_date", inv["invoice_date"]),
                        inv.get("currency", "INR"),
                        inv.get("description", ""),
                        inv.get("gstin"),
                        inv.get("ground_truth_scenario", "imported"),
                        inv.get("expected_match_id"),
                    ),
                )
            existing_inv_ids.add(iid)
            inserted_invoices += 1

        # Insert Settlements (skip if already exists in uploaded dataset)
        for s in settlements_data:
            sid = s["settlement_id"]
            if sid in existing_set_ids and not clear_existing:
                continue
            for tbl in ["uploaded_settlements", "settlements"]:
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {tbl}
                    (settlement_id, payment_id, invoice_reference, customer_id, amount, fee,
                     net_amount, payment_date, settlement_date, payment_gateway, utr_number,
                     remarks, ground_truth_invoice_id, ground_truth_scenario)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        sid,
                        s.get("payment_id", f"PAY-{sid}"),
                        s.get("invoice_reference"),
                        s.get("customer_id"),
                        s["amount"],
                        s.get("fee", 0.0),
                        s.get("net_amount", s["amount"]),
                        s.get("payment_date", s["settlement_date"]),
                        s["settlement_date"],
                        s.get("payment_gateway", "Imported Gateway"),
                        s.get("utr_number"),
                        s.get("remarks", "Imported settlement"),
                        s.get("ground_truth_invoice_id"),
                        s.get("ground_truth_scenario", "imported"),
                    ),
                )
            existing_set_ids.add(sid)
            inserted_settlements += 1

        # Insert Bank Transactions (skip if already exists in uploaded dataset)
        for b in bank_data:
            bid = b["bank_txn_id"]
            if bid in existing_bnk_ids and not clear_existing:
                continue
            for tbl in ["uploaded_bank_transactions", "bank_transactions"]:
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {tbl}
                    (bank_txn_id, utr_number, amount, transaction_date, value_date, description,
                     bank_reference, settlement_reference, transaction_type, balance,
                     ground_truth_settlement_id, ground_truth_scenario)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        bid,
                        b.get("utr_number"),
                        b["amount"],
                        b["transaction_date"],
                        b.get("value_date", b["transaction_date"]),
                        b.get("description", "Bank credit remittance"),
                        b.get("bank_reference"),
                        b.get("settlement_reference"),
                        b.get("transaction_type", "credit"),
                        b.get("balance"),
                        b.get("ground_truth_settlement_id"),
                        b.get("ground_truth_scenario", "imported"),
                    ),
                )
            existing_bnk_ids.add(bid)
            inserted_bank += 1

        # Insert Refunds (skip if already exists in uploaded dataset)
        for rfd in (refunds_data or []):
            rid = rfd["refund_id"]
            if rid in existing_rfd_ids and not clear_existing:
                continue
            for tbl in ["uploaded_refunds", "refunds"]:
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO {tbl}
                    (refund_id, invoice_id, refund_date, refund_amount, reason, payment_reference)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (
                        rid,
                        rfd.get("invoice_id"),
                        rfd.get("refund_date"),
                        rfd.get("refund_amount", 0.0),
                        rfd.get("reason", ""),
                        rfd.get("payment_reference"),
                    ),
                )
            existing_rfd_ids.add(rid)
            inserted_refunds += 1

        # Real total counts in isolated uploaded tables
        total_inv = conn.execute("SELECT COUNT(*) FROM uploaded_invoices").fetchone()[0]
        total_set = conn.execute("SELECT COUNT(*) FROM uploaded_settlements").fetchone()[0]
        total_bnk = conn.execute("SELECT COUNT(*) FROM uploaded_bank_transactions").fetchone()[0]
        total_rfd = conn.execute("SELECT COUNT(*) FROM uploaded_refunds").fetchone()[0]

        # Merge file metadata with existing metadata
        merged_files = []
        prev_row = conn.execute(
            "SELECT source_type, metadata_json, dataset_id FROM active_dataset_source WHERE id = 1"
        ).fetchone()
        cur_dataset_id = dataset_id or (prev_row[2] if prev_row and len(prev_row) > 2 and prev_row[2] else f"DATASET-{uuid.uuid4().hex[:8].upper()}")

        if prev_row and prev_row[0] in ("imported", "uploaded") and prev_row[1] and not clear_existing:
            try:
                prev_meta = json.loads(prev_row[1])
                merged_files = prev_meta.get("files", [])
            except Exception:
                merged_files = []

        if source_metadata and source_metadata.get("files"):
            for nf in source_metadata["files"]:
                merged_files = [f for f in merged_files if f.get("filename") != nf.get("filename")]
                merged_files.append(nf)

        final_meta = {
            "dataset_name": "User Uploaded Dataset",
            "dataset_id": cur_dataset_id,
            "imported_at": datetime.utcnow().isoformat(),
            "files": merged_files,
            "total_invoices": total_inv,
            "total_settlements": total_set,
            "total_bank_transactions": total_bnk,
            "total_refunds": total_rfd,
        }

        # Update metadata state, ensuring active_run_id is cleared on new dataset upload
        has_gt_row = conn.execute(
            "SELECT 1 FROM dataset_ground_truth WHERE dataset_id = ?",
            (cur_dataset_id,)
        ).fetchone()
        has_gt = 1 if has_gt_row else 0

        conn.execute(
            """
            INSERT OR REPLACE INTO active_dataset_source (id, source_type, dataset_id, active_run_id, metadata_json, has_ground_truth, updated_at)
            VALUES (1, 'uploaded', ?, NULL, ?, ?, datetime('now'))
            """,
            (cur_dataset_id, json.dumps(final_meta), has_gt),
        )

    return {
        "status": "success",
        "dataset_id": cur_dataset_id,
        "invoices_stored": inserted_invoices,
        "settlements_stored": inserted_settlements,
        "bank_transactions_stored": inserted_bank,
        "refunds_stored": inserted_refunds,
        "total_invoices": total_inv,
        "total_settlements": total_set,
        "total_bank_transactions": total_bnk,
        "total_refunds": total_rfd,
        "source": "uploaded",
        "timestamp": datetime.utcnow().isoformat(),
    }
