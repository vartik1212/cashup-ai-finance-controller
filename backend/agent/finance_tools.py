"""
ReconAI — Deterministic Finance Tools
=====================================
Strictly grounded tools querying real financial reconciliation records.
These tools are the only source of truth for the Finance Copilot and
Exception Investigator. They NEVER hallucinate or invent transactions.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Any
try:
    from database.db import get_db
except (ImportError, ValueError):
    from ..database.db import get_db


def _resolve_run_id(conn, run_id: Optional[str]) -> Optional[str]:
    if run_id:
        return run_id
    try:
        source_row = conn.execute(
            "SELECT active_run_id FROM active_dataset_source WHERE id = 1"
        ).fetchone()
        if source_row and "active_run_id" in source_row.keys() and source_row["active_run_id"]:
            return source_row["active_run_id"]
    except Exception:
        pass
    return None


def get_run_summary(run_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve full execution and performance metrics for the active reconciliation run."""
    with get_db() as conn:
        rid = _resolve_run_id(conn, run_id)
        if not rid:
            return {"error": "No reconciliation run found."}

        row = conn.execute(
            "SELECT * FROM reconciliation_runs WHERE run_id = ?", (rid,)
        ).fetchone()
        if not row:
            return {"error": f"Run '{rid}' not found."}

        data = dict(row)
        for key in ("scenario_performance_json", "trace_json", "source_metadata_json", "benchmark_evaluation_json"):
            if data.get(key):
                try:
                    data[key.replace("_json", "")] = json.loads(data[key])
                except Exception:
                    pass
        return data


def get_open_exceptions(run_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve all open exceptions (Human Review or Unresolved) ordered by invoice amount."""
    with get_db() as conn:
        rid = _resolve_run_id(conn, run_id)
        if not rid:
            return []

        rows = conn.execute(
            """
            SELECT invoice_id, customer_name, customer_id, invoice_amount, settlement_amount,
                   difference, status, match_type, confidence_score, exception_category,
                   system_assessment, recommendation, days_delayed
            FROM reconciliation_results
            WHERE run_id = ? AND status IN ('Unresolved', 'Human Review')
            ORDER BY invoice_amount DESC
            LIMIT ?
            """,
            (rid, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_exception_by_invoice(invoice_id: str, run_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve open exception details for a specific invoice ID."""
    with get_db() as conn:
        rid = _resolve_run_id(conn, run_id)
        if not rid:
            return None

        clean_id = invoice_id.strip().upper()
        row = conn.execute(
            """
            SELECT * FROM reconciliation_results
            WHERE run_id = ? AND UPPER(invoice_id) = ? AND status IN ('Unresolved', 'Human Review')
            """,
            (rid, clean_id),
        ).fetchone()

        if not row:
            return None
        data = dict(row)
        if data.get("evidence_json"):
            try:
                data["evidence"] = json.loads(data["evidence_json"])
            except Exception:
                pass
        return data


def get_reconciliation_by_invoice(invoice_id: str, run_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve reconciliation status for any invoice in the current run (matched or exception).
    Returns None if the invoice does NOT exist in the run.
    """
    with get_db() as conn:
        rid = _resolve_run_id(conn, run_id)
        if not rid:
            return None

        clean_id = invoice_id.strip().upper()
        row = conn.execute(
            """
            SELECT * FROM reconciliation_results
            WHERE run_id = ? AND UPPER(invoice_id) = ?
            """,
            (rid, clean_id),
        ).fetchone()

        if not row:
            # Also check if it exists in the raw invoice table
            inv_row = conn.execute(
                "SELECT * FROM invoices WHERE UPPER(invoice_id) = ?", (clean_id,)
            ).fetchone()
            if inv_row:
                return {
                    "invoice_id": clean_id,
                    "status": "Loaded in dataset, awaiting reconciliation run",
                    "invoice_amount": inv_row["invoice_amount"],
                    "customer_name": inv_row["customer_name"],
                }
            return None

        data = dict(row)
        if data.get("evidence_json"):
            try:
                data["evidence"] = json.loads(data["evidence_json"])
            except Exception:
                pass
        return data


def get_exceptions_by_category(category: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Filter open exceptions by category (e.g. Duplicate, Partial Payment, Refund, Missing Settlement)."""
    with get_db() as conn:
        rid = _resolve_run_id(conn, run_id)
        if not rid:
            return []

        cat_clean = category.strip().lower()
        rows = conn.execute(
            """
            SELECT invoice_id, customer_name, invoice_amount, settlement_amount, difference,
                   status, exception_category, match_type, confidence_score, system_assessment, recommendation
            FROM reconciliation_results
            WHERE run_id = ?
              AND (
                  LOWER(exception_category) LIKE ?
                  OR LOWER(match_type) LIKE ?
              )
            ORDER BY invoice_amount DESC
            """,
            (rid, f"%{cat_clean}%", f"%{cat_clean}%"),
        ).fetchall()
        return [dict(r) for r in rows]


def get_low_confidence_records(run_id: Optional[str] = None, threshold: float = 0.70) -> List[Dict[str, Any]]:
    """Retrieve records where confidence score falls below the specified threshold."""
    with get_db() as conn:
        rid = _resolve_run_id(conn, run_id)
        if not rid:
            return []

        rows = conn.execute(
            """
            SELECT invoice_id, customer_name, invoice_amount, confidence_score, status, match_type, exception_category
            FROM reconciliation_results
            WHERE run_id = ? AND confidence_score < ?
            ORDER BY confidence_score ASC
            LIMIT 20
            """,
            (rid, threshold),
        ).fetchall()
        return [dict(r) for r in rows]


def get_high_value_exceptions(run_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieve the highest-value unresolved or human-review transactions posing greatest financial risk."""
    with get_db() as conn:
        rid = _resolve_run_id(conn, run_id)
        if not rid:
            return []

        rows = conn.execute(
            """
            SELECT invoice_id, customer_name, invoice_amount, difference,
                   status, exception_category, confidence_score, system_assessment
            FROM reconciliation_results
            WHERE run_id = ? AND status IN ('Unresolved', 'Human Review')
            ORDER BY invoice_amount DESC
            LIMIT ?
            """,
            (rid, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_delayed_settlements(run_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve transactions with settlements delayed past the standard SLA window (> 5 days)."""
    with get_db() as conn:
        rid = _resolve_run_id(conn, run_id)
        if not rid:
            return []

        rows = conn.execute(
            """
            SELECT invoice_id, customer_name, settlement_id, invoice_amount, settlement_amount,
                   days_delayed, invoice_date, settlement_date, status, confidence_score
            FROM reconciliation_results
            WHERE run_id = ? AND (days_delayed > 5 OR match_type = 'delayed_settlement')
            ORDER BY days_delayed DESC
            LIMIT ?
            """,
            (rid, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_unresolved_amount(run_id: Optional[str] = None) -> Dict[str, Any]:
    """Calculate the total outstanding unresolved financial value and breakdown."""
    with get_db() as conn:
        rid = _resolve_run_id(conn, run_id)
        if not rid:
            return {"total_unresolved_amount": 0.0, "unresolved_count": 0}

        row = conn.execute(
            """
            SELECT COUNT(*) as count, COALESCE(SUM(invoice_amount), 0.0) as total_val
            FROM reconciliation_results
            WHERE run_id = ? AND status = 'Unresolved'
            """,
            (rid,),
        ).fetchone()

        largest = conn.execute(
            """
            SELECT invoice_id, customer_name, invoice_amount, exception_category
            FROM reconciliation_results
            WHERE run_id = ? AND status = 'Unresolved'
            ORDER BY invoice_amount DESC LIMIT 1
            """,
            (rid,),
        ).fetchone()

        return {
            "run_id": rid,
            "unresolved_count": row["count"],
            "total_unresolved_amount": round(row["total_val"], 2),
            "largest_unresolved": dict(largest) if largest else None,
        }


def get_execution_trace(run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve execution nodes, timings, and statuses from the LangGraph reconciliation pipeline."""
    with get_db() as conn:
        rid = _resolve_run_id(conn, run_id)
        if not rid:
            return []

        row = conn.execute(
            "SELECT trace_json FROM reconciliation_runs WHERE run_id = ?", (rid,)
        ).fetchone()
        if not row or not row["trace_json"]:
            return []
        try:
            return json.loads(row["trace_json"])
        except Exception:
            return []
