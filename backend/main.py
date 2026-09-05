"""
ReconAI — FastAPI Application
Orchestrated via LangGraph with stateful execution trace.
Deterministic logic verifies; LangGraph agent pipeline orchestrates.
"""

import os
import json
import uuid
import io
import csv
import base64
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException, UploadFile, File, Response
from fastapi.middleware.cors import CORSMiddleware
import sys
from pathlib import Path
import types
import logging

_current_dir = Path(__file__).parent.resolve()
_parent_dir = _current_dir.parent.resolve()

if str(_parent_dir) not in sys.path:
    sys.path.append(str(_parent_dir))
if str(_current_dir) in sys.path:
    sys.path.remove(str(_current_dir))
sys.path.insert(0, str(_current_dir))

if "backend" not in sys.modules:
    _backend_pkg = types.ModuleType("backend")
    _backend_pkg.__path__ = [str(_current_dir)]
    sys.modules["backend"] = _backend_pkg

from database.db import (
    init_db,
    get_db,
    load_benchmark_dataset,
    reset_uploaded_dataset,
    attach_dataset_ground_truth,
)
from models.schemas import (
    LoadDemoResponse,
    RunReconciliationRequest,
    CopilotRequest,
    CopilotResponse,
    ReconciliationRun,
    ReconciliationResult,
    ReviewDecision,
    ReviewAction,
    AuditEntry,
    TraceStep,
    AIStatusResponse,
    AIExceptionAnalysis,
)
from workflow.reconciliation_graph import reconciliation_graph
from agent.copilot_service import copilot_service
from agent.gemini_client import is_gemini_configured, PRIMARY_MODEL
from agent.exception_investigator import analyze_exception_with_ai
from evaluation.benchmark_evaluator import find_ground_truth_for_invoices, evaluate_benchmark_run
from ingestion import (
    profile_csv,
    detect_file_type,
    disambiguate_batch_file_types,
    map_columns_deterministic,
    map_columns_hybrid,
    map_columns_with_ai,
    get_canonical_schema,
    validate_records,
    normalize_and_store,
    CANONICAL_SCHEMAS,
)


app = FastAPI(
    title="ReconAI API",
    description="AI Finance Controller — LangGraph-Orchestrated Multi-Source Reconciliation",
    version="2.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent.parent / "data"


@app.on_event("startup")
def startup():
    try:
        init_db()
    except Exception as e:
        logging.getLogger("reconai.startup").warning(f"Database initialization warning: {e}")


@app.get("/health")
def root_health():
    return {"status": "ok"}


@app.get("/api/health")
def health():
    ai_key = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "status": "ok",
        "version": "2.5.0",
        "engine": "LangGraph",
        "ai_ready": ai_key,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/data/load-demo", response_model=LoadDemoResponse)
def load_demo_dataset():
    """
    Activates Benchmark Mode.
    Restores active dataset strictly from immutable benchmark_* tables.
    Never alters or mutates uploadedDataset.
    """
    load_benchmark_dataset()
    with get_db() as conn:
        inv_cnt = conn.execute("SELECT COUNT(*) FROM benchmark_invoices").fetchone()[0]
        set_cnt = conn.execute("SELECT COUNT(*) FROM benchmark_settlements").fetchone()[0]
        bnk_cnt = conn.execute("SELECT COUNT(*) FROM benchmark_bank_transactions").fetchone()[0]

    return LoadDemoResponse(
        invoices_loaded=inv_cnt,
        settlements_loaded=set_cnt,
        bank_transactions_loaded=bnk_cnt,
        message="Demo benchmark dataset loaded successfully.",
    )


@app.get("/api/data/status")
def data_status():
    with get_db() as conn:
        try:
            source_row = conn.execute(
                "SELECT source_type, metadata_json, dataset_id, active_run_id, has_ground_truth, updated_at FROM active_dataset_source WHERE id = 1"
            ).fetchone()
        except Exception:
            source_row = None

        source_type = source_row["source_type"] if source_row else "benchmark"
        dataset_id = (
            source_row["dataset_id"]
            if (source_row and "dataset_id" in source_row.keys() and source_row["dataset_id"])
            else ("DATASET-BENCHMARK" if source_type == "benchmark" else "DATASET-UPLOADED")
        )
        active_run_id = source_row["active_run_id"] if (source_row and "active_run_id" in source_row.keys()) else None

        if source_type == "benchmark":
            inv_count = conn.execute("SELECT COUNT(*) FROM benchmark_invoices").fetchone()[0]
            set_count = conn.execute("SELECT COUNT(*) FROM benchmark_settlements").fetchone()[0]
            bnk_count = conn.execute("SELECT COUNT(*) FROM benchmark_bank_transactions").fetchone()[0]
            rfd_count = 0
        else:
            inv_count = conn.execute("SELECT COUNT(*) FROM uploaded_invoices").fetchone()[0]
            set_count = conn.execute("SELECT COUNT(*) FROM uploaded_settlements").fetchone()[0]
            bnk_count = conn.execute("SELECT COUNT(*) FROM uploaded_bank_transactions").fetchone()[0]
            try:
                rfd_count = conn.execute("SELECT COUNT(*) FROM uploaded_refunds").fetchone()[0]
            except Exception:
                rfd_count = 0

        runs_count = conn.execute("SELECT COUNT(*) FROM reconciliation_runs").fetchone()[0]

        has_gt = False
        if source_row and "has_ground_truth" in source_row.keys() and source_row["has_ground_truth"]:
            has_gt = True
        gt_exists = conn.execute(
            "SELECT 1 FROM dataset_ground_truth WHERE dataset_id = ?",
            (dataset_id,)
        ).fetchone()
        has_ground_truth = bool(has_gt or gt_exists)

    source_meta = {}
    if source_row and source_row["metadata_json"]:
        try:
            source_meta = json.loads(source_row["metadata_json"])
        except Exception:
            source_meta = {}

    return {
        "invoices": inv_count,
        "settlements": set_count,
        "bank_transactions": bnk_count,
        "refunds": rfd_count,
        "reconciliation_runs": runs_count,
        "ready": inv_count > 0,
        "dataset_source": source_type,
        "dataset_id": dataset_id,
        "has_ground_truth": has_ground_truth,
        "active_run_id": active_run_id,
        "has_active_run": bool(active_run_id),
        "source_metadata": source_meta,
    }


def _execute_langgraph_pipeline(run_id: Optional[str] = None) -> Dict[str, Any]:
    """Executes the compiled LangGraph stateful graph on the strictly active dataset."""
    with get_db() as conn:
        try:
            source_row = conn.execute(
                "SELECT source_type, metadata_json, dataset_id FROM active_dataset_source WHERE id = 1"
            ).fetchone()
        except Exception:
            source_row = None

        source_type = source_row["source_type"] if source_row else "benchmark"
        dataset_id = (
            source_row["dataset_id"]
            if (source_row and "dataset_id" in source_row.keys() and source_row["dataset_id"])
            else ("DATASET-BENCHMARK" if source_type == "benchmark" else "DATASET-UPLOADED")
        )

        if source_type == "benchmark":
            inv_rows = conn.execute("SELECT * FROM benchmark_invoices").fetchall()
            set_rows = conn.execute("SELECT * FROM benchmark_settlements").fetchall()
            bnk_rows = conn.execute("SELECT * FROM benchmark_bank_transactions").fetchall()
            ground_truth_records = []
            gt_path = DATA_DIR / "ground_truth.json"
            if gt_path.exists():
                with open(gt_path, "r", encoding="utf-8") as f:
                    ground_truth_records = json.load(f)
        else:
            inv_rows = conn.execute("SELECT * FROM uploaded_invoices").fetchall()
            set_rows = conn.execute("SELECT * FROM uploaded_settlements").fetchall()
            bnk_rows = conn.execute("SELECT * FROM uploaded_bank_transactions").fetchall()
            ground_truth_records = []

    if not inv_rows:
        raise HTTPException(
            status_code=400,
            detail="No invoices loaded in active dataset. Load demo dataset or upload CSV files first.",
        )

    source_metadata = {}
    if source_row:
        try:
            meta_str = source_row["metadata_json"] if "metadata_json" in source_row.keys() else source_row[1]
            if meta_str:
                source_metadata = json.loads(meta_str)
        except Exception:
            source_metadata = {}

    raw_invoices = [dict(r) for r in inv_rows]
    raw_settlements = [dict(r) for r in set_rows]
    raw_bank_transactions = [dict(r) for r in bnk_rows]

    target_run_id = run_id or f"RUN-{uuid.uuid4().hex[:8].upper()}"

    initial_state = {
        "run_id": target_run_id,
        "started_at": datetime.utcnow().isoformat(),
        "raw_invoices": raw_invoices,
        "raw_settlements": raw_settlements,
        "raw_bank_transactions": raw_bank_transactions,
        "ground_truth_records": [],  # Engine never sees expected labels
    }

    final_state = reconciliation_graph.invoke(initial_state)

    run: ReconciliationRun = final_state["run_summary"]
    results: List[ReconciliationResult] = final_state["reconciliation_results"]
    trace: List[TraceStep] = final_state["trace"]

    run.dataset_source = source_type
    run.source_metadata = source_metadata
    run.dataset_id = dataset_id

    # Post-reconciliation evaluation layer:
    # Ground truth answer key is loaded ONLY here, strictly outside the engine.
    # STRICT DATASET OWNERSHIP ENFORCEMENT:
    # Verified Accuracy may ONLY be numeric when:
    # 1. current_dataset.has_ground_truth == true
    # 2. ground_truth.dataset_id == current_dataset.dataset_id
    # 3. predictions for the current run were finalized BEFORE evaluation.
    # Otherwise:
    # Verified Accuracy = None (displayed as N/A in UI)
    invoice_ids = [inv["invoice_id"] for inv in raw_invoices]
    gt_map = find_ground_truth_for_invoices(invoice_ids, dataset_id=dataset_id)
    if gt_map:
        eval_metrics = evaluate_benchmark_run(results, gt_map)
        run.verified_accuracy = eval_metrics["classification_accuracy"]
        run.precision = eval_metrics["precision"]
        run.recall = eval_metrics["recall"]
        run.scenario_performance = eval_metrics["scenario_performance"]
        run.benchmark_evaluation = eval_metrics["benchmark_evaluation"]
    else:
        run.verified_accuracy = None
        run.precision = None
        run.recall = None
        run.scenario_performance = []
        run.benchmark_evaluation = None

    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO reconciliation_runs
            (run_id, timestamp, records_processed, invoices_count, settlements_count,
             bank_transactions_count, exact_matches, fee_matches, probable_matches,
             human_review, unresolved, auto_resolved, open_exception_count,
             reconciled_amount, unresolved_amount, match_rate, verified_accuracy,
             auto_resolution_rate, processing_time_ms, scenario_performance_json,
             precision, recall, trace_json, dataset_source, source_metadata_json,
             benchmark_evaluation_json, dataset_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
            (
                run.run_id,
                run.timestamp.isoformat(),
                run.records_processed,
                run.invoices_count,
                run.settlements_count,
                run.bank_transactions_count,
                run.exact_matches,
                run.fee_matches,
                run.probable_matches,
                run.human_review,
                run.unresolved,
                run.auto_resolved,
                run.open_exception_count,
                run.reconciled_amount,
                run.unresolved_amount,
                run.match_rate,
                run.verified_accuracy,
                run.auto_resolution_rate,
                run.processing_time_ms,
                json.dumps([sp.dict() for sp in run.scenario_performance]),
                run.precision,
                run.recall,
                json.dumps([t.dict() for t in trace]),
                run.dataset_source,
                json.dumps(run.source_metadata or {}),
                json.dumps(run.benchmark_evaluation.dict() if run.benchmark_evaluation else None),
                run.dataset_id,
            ),
        )

        for r in results:
            conn.execute(
                """
                INSERT OR REPLACE INTO reconciliation_results
                (result_id, run_id, invoice_id, settlement_id, bank_txn_id,
                 invoice_amount, settlement_amount, bank_amount, difference,
                 invoice_date, payment_date, settlement_date, days_delayed,
                 customer_name, customer_id, match_type, status, confidence_score,
                 exception_category, evidence_json, system_assessment, recommendation,
                 ground_truth_scenario, is_correct_prediction, processed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
                (
                    r.result_id,
                    r.run_id,
                    r.invoice_id,
                    r.settlement_id,
                    r.bank_txn_id,
                    r.invoice_amount,
                    r.settlement_amount,
                    r.bank_amount,
                    r.difference,
                    r.invoice_date.isoformat(),
                    r.payment_date.isoformat() if r.payment_date else None,
                    r.settlement_date.isoformat() if r.settlement_date else None,
                    r.days_delayed,
                    r.customer_name,
                    r.customer_id,
                    r.match_type.value,
                    r.status.value,
                    r.confidence_score,
                    r.exception_category.value if r.exception_category else None,
                    json.dumps([e.dict() for e in r.evidence]),
                    r.system_assessment,
                    r.recommendation,
                    r.ground_truth_scenario,
                    1 if r.is_correct_prediction else (0 if r.is_correct_prediction is False else None),
                    r.processed_at.isoformat(),
                ),
            )

        conn.execute(
            "UPDATE active_dataset_source SET active_run_id = ? WHERE id = 1",
            (run.run_id,),
        )

    return {
        "run_id": run.run_id,
        "summary": run.dict(),
        "trace": [t.dict() for t in trace],
        "message": f"LangGraph pipeline executed ({len(trace)} nodes). {run.records_processed} records processed in {run.processing_time_ms:.1f}ms.",
    }


@app.post("/api/reconcile")
def run_reconciliation(req: RunReconciliationRequest):
    return _execute_langgraph_pipeline(req.run_id)


@app.post("/api/reconciliation/run")
def run_reconciliation_alias(req: RunReconciliationRequest):
    return _execute_langgraph_pipeline(req.run_id)


@app.get("/api/reconcile/latest")
@app.get("/api/reconciliation/latest")
@app.get("/api/reports/latest")
def get_latest_run():
    with get_db() as conn:
        try:
            source_row = conn.execute(
                "SELECT dataset_id, active_run_id FROM active_dataset_source WHERE id = 1"
            ).fetchone()
        except Exception:
            source_row = None

        active_run_id = None
        current_dataset_id = None
        if source_row:
            if "dataset_id" in source_row.keys():
                current_dataset_id = source_row["dataset_id"]
            if "active_run_id" in source_row.keys():
                active_run_id = source_row["active_run_id"]

        if not active_run_id:
            return {"has_run": False, "dataset_id": current_dataset_id}

        row = conn.execute(
            "SELECT * FROM reconciliation_runs WHERE run_id = ?", (active_run_id,)
        ).fetchone()
        if not row:
            return {"has_run": False, "dataset_id": current_dataset_id}

        if current_dataset_id and row["dataset_id"] != current_dataset_id:
            return {"has_run": False, "dataset_id": current_dataset_id}

        run_data = dict(row)
        if run_data.get("scenario_performance_json"):
            run_data["scenario_performance"] = json.loads(run_data["scenario_performance_json"])
        if run_data.get("trace_json"):
            run_data["trace"] = json.loads(run_data["trace_json"])
        if run_data.get("source_metadata_json"):
            try:
                run_data["source_metadata"] = json.loads(run_data["source_metadata_json"])
            except Exception:
                run_data["source_metadata"] = {}
        if run_data.get("benchmark_evaluation_json"):
            try:
                run_data["benchmark_evaluation"] = json.loads(run_data["benchmark_evaluation_json"])
            except Exception:
                run_data["benchmark_evaluation"] = None
        has_gt_row = conn.execute(
            "SELECT 1 FROM dataset_ground_truth WHERE dataset_id = ?",
            (run_data.get("dataset_id"),)
        ).fetchone()
        run_data["has_ground_truth"] = bool(has_gt_row and run_data.get("dataset_source") == "benchmark")
        run_data["has_run"] = True
        return run_data


@app.post("/api/data/attach-ground-truth")
def attach_ground_truth_endpoint(payload: Dict[str, Any]):
    """
    Explicitly associates ground truth with the current active dataset.
    Only when ground truth is explicitly attached to the active dataset
    can benchmark evaluation run and numeric Verified Accuracy appear.
    """
    ground_truth_records = payload.get("ground_truth", [])
    if not ground_truth_records:
        raise HTTPException(status_code=400, detail="No ground truth records provided.")

    with get_db() as conn:
        source_row = conn.execute(
            "SELECT dataset_id FROM active_dataset_source WHERE id = 1"
        ).fetchone()
        if not source_row or not source_row["dataset_id"]:
            raise HTTPException(status_code=400, detail="No active dataset found.")
        dataset_id = source_row["dataset_id"]

    attach_dataset_ground_truth(dataset_id, json.dumps(ground_truth_records))
    return {
        "status": "success",
        "dataset_id": dataset_id,
        "message": f"Ground truth successfully attached to dataset {dataset_id}.",
    }


@app.get("/api/reconcile/runs")
def list_runs():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM reconciliation_runs ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()
        runs = []
        for r in rows:
            data = dict(r)
            if data.get("scenario_performance_json"):
                data["scenario_performance"] = json.loads(data["scenario_performance_json"])
            if data.get("source_metadata_json"):
                try:
                    data["source_metadata"] = json.loads(data["source_metadata_json"])
                except Exception:
                    data["source_metadata"] = {}
            if data.get("benchmark_evaluation_json"):
                try:
                    data["benchmark_evaluation"] = json.loads(data["benchmark_evaluation_json"])
                except Exception:
                    data["benchmark_evaluation"] = None
            runs.append(data)
        return runs


@app.get("/api/reconcile/runs/{run_id}")
def get_run(run_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM reconciliation_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        data = dict(row)
        if data.get("scenario_performance_json"):
            data["scenario_performance"] = json.loads(data["scenario_performance_json"])
        if data.get("trace_json"):
            data["trace"] = json.loads(data["trace_json"])
        if data.get("benchmark_evaluation_json"):
            try:
                data["benchmark_evaluation"] = json.loads(data["benchmark_evaluation_json"])
            except Exception:
                data["benchmark_evaluation"] = None
        has_gt_row = conn.execute(
            "SELECT 1 FROM dataset_ground_truth WHERE dataset_id = ?",
            (data.get("dataset_id"),)
        ).fetchone()
        data["has_ground_truth"] = bool(has_gt_row and data.get("dataset_source") == "benchmark")
        return data


@app.get("/api/reconciliation/{run_id}/trace")
def get_run_trace(run_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT trace_json FROM reconciliation_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not row or not row["trace_json"]:
            return []
        return json.loads(row["trace_json"])


@app.get("/api/reconcile/runs/{run_id}/results")
@app.get("/api/reconciliation/results")
def get_run_results(
    run_id: Optional[str] = None,
    status: Optional[str] = None,
    match_type: Optional[str] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    search: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
):
    with get_db() as conn:
        try:
            source_row = conn.execute(
                "SELECT dataset_id, active_run_id FROM active_dataset_source WHERE id = 1"
            ).fetchone()
            cur_ds = source_row["dataset_id"] if (source_row and "dataset_id" in source_row.keys()) else None
            default_run_id = source_row["active_run_id"] if (source_row and "active_run_id" in source_row.keys()) else None
        except Exception:
            cur_ds = None
            default_run_id = None

        target_run_id = run_id or default_run_id
        if not target_run_id:
            return []

        if not run_id and cur_ds:
            run_check = conn.execute(
                "SELECT dataset_id FROM reconciliation_runs WHERE run_id = ?", (target_run_id,)
            ).fetchone()
            if not run_check or run_check["dataset_id"] != cur_ds:
                return []

        query = "SELECT * FROM reconciliation_results WHERE run_id = ?"
        params: List[Any] = [target_run_id]

        if status:
            query += " AND status = ?"
            params.append(status)
        if match_type:
            query += " AND match_type = ?"
            params.append(match_type)
        if min_confidence is not None:
            query += " AND confidence_score >= ?"
            params.append(min_confidence)
        if max_confidence is not None:
            query += " AND confidence_score <= ?"
            params.append(max_confidence)
        if search:
            query += " AND (invoice_id LIKE ? OR customer_name LIKE ? OR settlement_id LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        query += " ORDER BY invoice_date LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("evidence_json"):
                d["evidence"] = json.loads(d["evidence_json"])
            results.append(d)
        return results


@app.get("/api/reconcile/runs/{run_id}/exceptions")
@app.get("/api/reconciliation/exceptions")
def get_exceptions(run_id: Optional[str] = None):
    with get_db() as conn:
        try:
            source_row = conn.execute(
                "SELECT dataset_id, active_run_id FROM active_dataset_source WHERE id = 1"
            ).fetchone()
            cur_ds = source_row["dataset_id"] if (source_row and "dataset_id" in source_row.keys()) else None
            default_run_id = source_row["active_run_id"] if (source_row and "active_run_id" in source_row.keys()) else None
        except Exception:
            cur_ds = None
            default_run_id = None

        target_run_id = run_id or default_run_id
        if not target_run_id:
            return []

        if not run_id and cur_ds:
            run_check = conn.execute(
                "SELECT dataset_id FROM reconciliation_runs WHERE run_id = ?", (target_run_id,)
            ).fetchone()
            if not run_check or run_check["dataset_id"] != cur_ds:
                return []

        rows = conn.execute(
            """
            SELECT * FROM reconciliation_results
            WHERE run_id = ? AND status IN ('Unresolved', 'Human Review')
            ORDER BY invoice_amount DESC
            """,
            (target_run_id,),
        ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            if d.get("evidence_json"):
                d["evidence"] = json.loads(d["evidence_json"])
            results.append(d)
        return results


@app.get("/api/reconcile/runs/{run_id}/result/{invoice_id}")
@app.get("/api/reconciliation/result/{invoice_id}")
def get_result_by_invoice(invoice_id: str, run_id: Optional[str] = None):
    with get_db() as conn:
        try:
            source_row = conn.execute(
                "SELECT dataset_id, active_run_id FROM active_dataset_source WHERE id = 1"
            ).fetchone()
            cur_ds = source_row["dataset_id"] if (source_row and "dataset_id" in source_row.keys()) else None
            default_run_id = source_row["active_run_id"] if (source_row and "active_run_id" in source_row.keys()) else None
        except Exception:
            cur_ds = None
            default_run_id = None

        target_run_id = run_id or default_run_id
        if not target_run_id:
            raise HTTPException(status_code=404, detail="No active reconciliation run found for invoice")

        if not run_id and cur_ds:
            run_check = conn.execute(
                "SELECT dataset_id FROM reconciliation_runs WHERE run_id = ?", (target_run_id,)
            ).fetchone()
            if not run_check or run_check["dataset_id"] != cur_ds:
                raise HTTPException(status_code=404, detail="No active reconciliation run found for invoice")

        row = conn.execute(
            "SELECT * FROM reconciliation_results WHERE run_id = ? AND invoice_id = ?",
            (target_run_id, invoice_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Result not found")
        data = dict(row)
        if data.get("evidence_json"):
            data["evidence"] = json.loads(data["evidence_json"])
        return data


STATUS_AFTER_ACTION = {
    ReviewAction.APPROVE: "Exact Match",
    ReviewAction.REJECT: "Unresolved",
    ReviewAction.KEEP: "Human Review",
}


@app.post("/api/reconcile/runs/{run_id}/results/{result_id}/review")
def review_result(run_id: str, result_id: str, decision: ReviewDecision):
    with get_db() as conn:
        row = conn.execute(
            "SELECT status, invoice_id FROM reconciliation_results WHERE result_id = ? AND run_id = ?",
            (result_id, run_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Result not found")

        prev_status = row["status"]
        invoice_id = row["invoice_id"]
        new_status = STATUS_AFTER_ACTION[decision.action]

        conn.execute(
            "UPDATE reconciliation_results SET status = ? WHERE result_id = ?",
            (new_status, result_id),
        )

        if prev_status in ("Human Review", "Unresolved") and new_status == "Exact Match":
            conn.execute(
                "UPDATE reconciliation_runs SET open_exception_count = MAX(0, open_exception_count - 1) WHERE run_id = ?",
                (run_id,),
            )

        audit_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
        conn.execute(
            """
            INSERT INTO audit_log
            (audit_id, result_id, invoice_id, action, previous_status, new_status, actor, notes, timestamp)
            VALUES (?,?,?,?,?,?,?,?,?)
        """,
            (
                audit_id,
                result_id,
                invoice_id,
                decision.action.value,
                prev_status,
                new_status,
                decision.actor or "human",
                decision.notes,
                datetime.utcnow().isoformat(),
            ),
        )

    return AuditEntry(
        audit_id=audit_id,
        result_id=result_id,
        invoice_id=invoice_id,
        action=decision.action,
        previous_status=prev_status,
        new_status=new_status,
        actor=decision.actor or "human",
        notes=decision.notes,
        timestamp=datetime.utcnow(),
    )


@app.get("/api/reconcile/runs/{run_id}/audit")
def get_audit_log(run_id: str):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT al.* FROM audit_log al
            JOIN reconciliation_results rr ON al.result_id = rr.result_id
            WHERE rr.run_id = ?
            ORDER BY al.timestamp DESC
        """,
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/copilot/chat", response_model=CopilotResponse)
async def copilot_chat(req: CopilotRequest):
    return await copilot_service.handle_query(req)


@app.get("/api/ai/status", response_model=AIStatusResponse)
def get_ai_status():
    configured = is_gemini_configured()
    return {
        "available": configured,
        "provider": "Gemini",
        "mode": "connected" if configured else "data_only",
        "model": PRIMARY_MODEL if configured else None,
    }


@app.post("/api/ai/exceptions/{invoice_id}/analyze", response_model=AIExceptionAnalysis)
async def analyze_exception_endpoint(invoice_id: str, run_id: Optional[str] = None, force: bool = False):
    try:
        return await analyze_exception_with_ai(invoice_id, run_id=run_id, force_refresh=force)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Exception analysis failed: {e}")



# ===========================================================================
# CSV Ingestion Endpoints (Import Mode)
# ===========================================================================

@app.post("/api/upload/profile")
async def upload_and_profile_csvs(files: List[UploadFile] = File(...)):
    """
    Step 1 of Import Mode:
    Receives CSV files via multipart form-data, computes profiling metrics,
    detects file type, and proposes column mappings.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    file_tuples = []
    for f in files:
        content = await f.read()
        file_tuples.append((f.filename, content))
    return _profile_files_internal(file_tuples)


@app.post("/api/upload/profile-json")
def upload_and_profile_json(payload: Dict[str, Any]):
    """JSON alternative for profiling (accepts base64 or raw text content)."""
    files_input = payload.get("files", [])
    if not files_input:
        raise HTTPException(status_code=400, detail="No files provided in payload.")

    file_tuples = []
    for f in files_input:
        name = f.get("filename", "upload.csv")
        content_b64 = f.get("content_b64", "")
        raw_text = f.get("content_text", "")
        if content_b64:
            content = base64.b64decode(content_b64)
        elif raw_text:
            content = raw_text.encode("utf-8")
        else:
            continue
        file_tuples.append((name, content))

    return _profile_files_internal(file_tuples)


def _profile_files_internal(file_tuples: List[Tuple[str, bytes]]) -> Dict[str, Any]:
    profiles = []
    for filename, content in file_tuples:
        if not filename.lower().endswith(".csv"):
            raise HTTPException(
                status_code=400, detail=f"File '{filename}' is not a CSV file."
            )

        if len(content) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=400, detail=f"File '{filename}' exceeds 10MB limit."
            )

        prof = profile_csv(content, filename)
        if prof.get("error"):
            profiles.append({
                "filename": filename,
                "error": prof["error"],
                "file_type": "UNKNOWN",
                "confidence": 0.0,
            })
            continue

        cols = [c["column_name"] for c in prof["columns"]]
        detection = detect_file_type(filename, cols, prof.get("preview_rows"))
        file_type = detection["file_type"]

        mappings = map_columns_hybrid(file_type, prof["columns"])
        canonical = get_canonical_schema(file_type)

        profiles.append({
            "filename": filename,
            "row_count": prof["row_count"],
            "column_count": prof["column_count"],
            "columns": prof["columns"],
            "duplicate_rows": prof["duplicate_rows"],
            "preview_rows": prof["preview_rows"],
            "delimiter": prof["delimiter"],
            "detected_file_type": file_type,
            "detection_confidence": detection["confidence"],
            "detection_confidence_band": detection.get("confidence_band", "MEDIUM"),
            "detection_reason": detection["reason"],
            "detection_source": detection["source"],
            "column_mappings": mappings,
            "canonical_schema": canonical,
            "file_content_b64": base64.b64encode(content).decode("ascii"),
        })

    # Cross-file reasoning: evaluate collective batch context and resolve ambiguities
    profiles = disambiguate_batch_file_types(profiles)
    for p in profiles:
        if p.get("detection_source") == "cross_file_reasoning":
            detected_type = p.get("detected_file_type")
            if detected_type and detected_type != "UNKNOWN":
                p["column_mappings"] = map_columns_hybrid(detected_type, p["columns"])
                p["canonical_schema"] = get_canonical_schema(detected_type)

    with get_db() as conn:
        try:
            source_row = conn.execute("SELECT source_type FROM active_dataset_source WHERE id = 1").fetchone()
        except Exception:
            source_row = None
        curr_mode = source_row[0] if source_row else "benchmark"
        if curr_mode == "benchmark":
            curr_inv = 0
            curr_set = 0
            curr_bnk = 0
        else:
            curr_inv = conn.execute("SELECT count(*) FROM uploaded_invoices").fetchone()[0]
            curr_set = conn.execute("SELECT count(*) FROM uploaded_settlements").fetchone()[0]
            curr_bnk = conn.execute("SELECT count(*) FROM uploaded_bank_transactions").fetchone()[0]

    return {
        "status": "success",
        "file_count": len(profiles),
        "profiles": profiles,
        "available_schemas": CANONICAL_SCHEMAS,
        "existing_dataset": {
            "invoices": curr_inv,
            "settlements": curr_set,
            "bank_transactions": curr_bnk,
        },
    }


@app.post("/api/upload/confirm")
def confirm_and_import_data(payload: Dict[str, Any]):
    """
    Step 2 of Import Mode:
    Receives user-confirmed mappings per file, validates records,
    normalizes them, and persists into isolated uploaded_* tables.
    If currently in Benchmark mode, creates/resets uploadedDataset to start fresh.
    """
    files_to_import = payload.get("files", [])
    if not files_to_import:
        raise HTTPException(
            status_code=400, detail="No files provided for import confirmation."
        )

    is_append = bool(payload.get("append", False))
    clear_existing = not is_append

    if clear_existing:
        active_ds_id = reset_uploaded_dataset()
        existing_inv = 0
        existing_set = 0
        existing_bnk = 0
        existing_rfd = 0
    else:
        with get_db() as conn:
            source_row = conn.execute(
                "SELECT dataset_id FROM active_dataset_source WHERE id = 1"
            ).fetchone()
            active_ds_id = (
                source_row["dataset_id"]
                if (source_row and "dataset_id" in source_row.keys() and source_row["dataset_id"])
                else "DATASET-UPLOADED"
            )
            existing_inv = conn.execute("SELECT count(*) FROM uploaded_invoices").fetchone()[0]
            existing_set = conn.execute("SELECT count(*) FROM uploaded_settlements").fetchone()[0]
            existing_bnk = conn.execute("SELECT count(*) FROM uploaded_bank_transactions").fetchone()[0]
            try:
                existing_rfd = conn.execute("SELECT count(*) FROM uploaded_refunds").fetchone()[0]
            except Exception:
                existing_rfd = 0

    invoices_records: List[Dict[str, Any]] = []
    settlements_records: List[Dict[str, Any]] = []
    bank_records: List[Dict[str, Any]] = []
    refunds_records: List[Dict[str, Any]] = []

    validation_summaries = []
    files_meta = []

    for file_spec in files_to_import:
        filename = file_spec.get("filename", "upload.csv")
        file_type = file_spec.get("file_type", "UNKNOWN")
        column_mapping = file_spec.get("column_mapping", {})
        content_b64 = file_spec.get("file_content_b64", "")

        if not content_b64:
            raise HTTPException(
                status_code=400, detail=f"Missing content for file '{filename}'."
            )

        try:
            content_bytes = base64.b64decode(content_b64)
            text = content_bytes.decode("utf-8-sig", errors="replace")
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to decode file '{filename}': {e}"
            )

        # Parse CSV rows
        reader = csv.DictReader(io.StringIO(text))
        raw_rows = [row for row in reader]

        # Check for duplicate IDs against uploaded dataset ONLY (never benchmark)
        with get_db() as conn:
            if clear_existing:
                existing_ids = set()
            else:
                if file_type == "INVOICES":
                    existing_ids = set(r[0] for r in conn.execute("SELECT invoice_id FROM uploaded_invoices").fetchall())
                elif file_type == "SETTLEMENTS":
                    existing_ids = set(r[0] for r in conn.execute("SELECT settlement_id FROM uploaded_settlements").fetchall())
                elif file_type == "BANK_TRANSACTIONS":
                    existing_ids = set(r[0] for r in conn.execute("SELECT bank_txn_id FROM uploaded_bank_transactions").fetchall())
                elif file_type == "REFUNDS":
                    existing_ids = set(r[0] for r in conn.execute("SELECT refund_id FROM uploaded_refunds").fetchall())
                else:
                    existing_ids = set()

        val_result = validate_records(file_type, raw_rows, column_mapping, existing_ids=existing_ids)
        stats = val_result["stats"]

        validation_summaries.append({
            "filename": filename,
            "file_type": file_type,
            "stats": stats,
            "errors": val_result["errors"],
            "warnings": val_result["warnings"],
        })

        files_meta.append({
            "filename": filename,
            "file_type": file_type,
            "rows_imported": stats["valid_count"],
            "rows_rejected": stats["rejected_count"],
            "warnings_count": stats["warning_count"],
        })

        if file_type == "INVOICES":
            invoices_records.extend(val_result["valid_records"])
        elif file_type == "SETTLEMENTS":
            settlements_records.extend(val_result["valid_records"])
        elif file_type == "BANK_TRANSACTIONS":
            bank_records.extend(val_result["valid_records"])
        elif file_type == "REFUNDS":
            refunds_records.extend(val_result["valid_records"])

    total_valid_new = len(invoices_records) + len(settlements_records) + len(bank_records) + len(refunds_records)
    total_existing = existing_inv + existing_set + existing_bnk + existing_rfd

    # Allow incremental upload of any valid financial file type
    if total_valid_new == 0 and total_existing == 0:
        raise HTTPException(
            status_code=400,
            detail="No valid records found in uploaded files. Please verify column mappings.",
        )

    # Zero-Invoice Validation Guard:
    # If the upload results in 0 invoices while settlements exist, block with clear warning
    total_invoices_after_import = len(invoices_records) + existing_inv
    total_settlements_after_import = len(settlements_records) + existing_set
    if total_invoices_after_import == 0 and total_settlements_after_import > 0:
        raise HTTPException(
            status_code=400,
            detail="No invoice source detected. Review file classifications before ingestion.",
        )

    # Persist normalized data into isolated uploaded dataset
    store_meta = {
        "dataset_name": "User Uploaded Dataset",
        "imported_at": datetime.utcnow().isoformat(),
        "files": files_meta,
    }

    norm_res = normalize_and_store(
        invoices_data=invoices_records,
        settlements_data=settlements_records,
        bank_data=bank_records,
        refunds_data=refunds_records,
        source_metadata=store_meta,
        clear_existing=clear_existing,
        dataset_id=active_ds_id,
    )

    return {
        "status": "success",
        "dataset_id": active_ds_id,
        "message": f"Successfully imported {len(invoices_records)} invoices, {len(settlements_records)} settlements, {len(bank_records)} bank records, and {len(refunds_records)} refunds.",
        "summaries": validation_summaries,
        "metadata": store_meta,
        "dataset_counts": {
            "existing": {
                "invoices": existing_inv,
                "settlements": existing_set,
                "bank_transactions": existing_bnk,
                "refunds": existing_rfd,
            },
            "added": {
                "invoices": len(invoices_records),
                "settlements": len(settlements_records),
                "bank_transactions": len(bank_records),
                "refunds": len(refunds_records),
            },
            "result": {
                "invoices": norm_res["total_invoices"],
                "settlements": norm_res["total_settlements"],
                "bank_transactions": norm_res["total_bank_transactions"],
                "refunds": norm_res.get("total_refunds", len(refunds_records)),
            },
        },
    }


# ===========================================================================
# Export Endpoints (Download Results, Exceptions & Reports)
# ===========================================================================

@app.get("/api/reports/export/results.csv")
def export_results_csv(run_id: Optional[str] = None):
    with get_db() as conn:
        if not run_id:
            run_row = conn.execute(
                "SELECT run_id FROM reconciliation_runs ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            if not run_row:
                raise HTTPException(status_code=404, detail="No reconciliation runs found.")
            target_run = run_row[0]
        else:
            target_run = run_id

        results = conn.execute(
            "SELECT * FROM reconciliation_results WHERE run_id = ?", (target_run,)
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID", "Run ID", "Invoice ID", "Settlement ID", "Bank Txn ID",
        "Customer Name", "Invoice Amount", "Settlement Amount", "Bank Amount",
        "Difference", "Match Type", "Status", "Confidence Score",
        "Exception Category", "System Assessment", "Recommendation", "Processed At"
    ])
    for r in results:
        writer.writerow([
            r["result_id"], r["run_id"], r["invoice_id"], r["settlement_id"] or "N/A",
            r["bank_txn_id"] or "N/A", r["customer_name"], r["invoice_amount"],
            r["settlement_amount"] if r["settlement_amount"] is not None else "N/A",
            r["bank_amount"] if r["bank_amount"] is not None else "N/A",
            r["difference"], r["match_type"], r["status"], f"{r['confidence_score']:.2f}",
            r["exception_category"] or "None", r["system_assessment"],
            r["recommendation"], r["processed_at"]
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=reconciliation_results_{target_run}.csv"}
    )


@app.get("/api/reports/export/exceptions.csv")
def export_exceptions_csv(run_id: Optional[str] = None):
    with get_db() as conn:
        if not run_id:
            run_row = conn.execute(
                "SELECT run_id FROM reconciliation_runs ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            if not run_row:
                raise HTTPException(status_code=404, detail="No reconciliation runs found.")
            target_run = run_row[0]
        else:
            target_run = run_id

        results = conn.execute(
            "SELECT * FROM reconciliation_results WHERE run_id = ? AND status IN ('Unresolved', 'Human Review') ORDER BY invoice_amount DESC",
            (target_run,)
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID", "Run ID", "Invoice ID", "Settlement ID",
        "Customer Name", "Invoice Amount", "Difference", "Match Type", "Status",
        "Confidence Score", "Exception Category", "System Assessment", "Recommendation"
    ])
    for r in results:
        writer.writerow([
            r["result_id"], r["run_id"], r["invoice_id"], r["settlement_id"] or "N/A",
            r["customer_name"], r["invoice_amount"], r["difference"],
            r["match_type"], r["status"], f"{r['confidence_score']:.2f}",
            r["exception_category"] or "Discrepancy", r["system_assessment"], r["recommendation"]
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=exceptions_{target_run}.csv"}
    )


@app.get("/api/reports/export/run_report.json")
def export_run_report_json(run_id: Optional[str] = None):
    with get_db() as conn:
        if not run_id:
            run_row = conn.execute(
                "SELECT * FROM reconciliation_runs ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
        else:
            run_row = conn.execute(
                "SELECT * FROM reconciliation_runs WHERE run_id = ?", (run_id,)
            ).fetchone()

        if not run_row:
            raise HTTPException(status_code=404, detail="No reconciliation run found.")

        run = dict(run_row)
        rid = run["run_id"]
        results = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM reconciliation_results WHERE run_id = ?", (rid,)
            ).fetchall()
        ]

    if run.get("scenario_performance_json"):
        run["scenario_performance"] = json.loads(run["scenario_performance_json"])
    if run.get("trace_json"):
        run["trace"] = json.loads(run["trace_json"])
    if run.get("source_metadata_json"):
        try:
            run["source_metadata"] = json.loads(run["source_metadata_json"])
        except Exception:
            pass

    data = {
        "run_summary": run,
        "total_results": len(results),
        "results": results,
    }

    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=run_report_{rid}.json"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
