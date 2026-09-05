"""
ReconAI — SQLite Database Layer
Handles connection, schema creation, and basic CRUD.
"""

from __future__ import annotations

import sqlite3
import os
import uuid
import json
from typing import Optional
from pathlib import Path
from contextlib import contextmanager

def _resolve_db_path() -> Path:
    if os.getenv("DATABASE_PATH"):
        return Path(os.getenv("DATABASE_PATH"))
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("VERCEL_ENV"):
        return Path("/tmp/reconai.db")

    default_path = Path(__file__).parent.parent.parent / "data" / "reconai.db"
    try:
        default_path.parent.mkdir(parents=True, exist_ok=True)
        return default_path
    except (OSError, PermissionError):
        return Path("/tmp/reconai.db")

DB_PATH = _resolve_db_path()


def get_connection() -> sqlite3.Connection:
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError):
        pass
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
        -- Source tables
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            invoice_amount REAL NOT NULL,
            invoice_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            currency TEXT DEFAULT 'INR',
            description TEXT,
            gstin TEXT,
            ground_truth_scenario TEXT NOT NULL,
            expected_match_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settlements (
            settlement_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            invoice_reference TEXT,
            customer_id TEXT,
            amount REAL NOT NULL,
            fee REAL NOT NULL,
            net_amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            settlement_date TEXT NOT NULL,
            payment_gateway TEXT NOT NULL,
            utr_number TEXT,
            remarks TEXT,
            ground_truth_invoice_id TEXT,
            ground_truth_scenario TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bank_transactions (
            bank_txn_id TEXT PRIMARY KEY,
            utr_number TEXT,
            amount REAL NOT NULL,
            transaction_date TEXT NOT NULL,
            value_date TEXT NOT NULL,
            description TEXT NOT NULL,
            bank_reference TEXT,
            settlement_reference TEXT,
            transaction_type TEXT NOT NULL,
            balance REAL,
            ground_truth_settlement_id TEXT,
            ground_truth_scenario TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Dedicated Benchmark Tables (Immutable, never mutated by user uploads)
        CREATE TABLE IF NOT EXISTS benchmark_invoices (
            invoice_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            invoice_amount REAL NOT NULL,
            invoice_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            currency TEXT DEFAULT 'INR',
            description TEXT,
            gstin TEXT,
            ground_truth_scenario TEXT NOT NULL,
            expected_match_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS benchmark_settlements (
            settlement_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            invoice_reference TEXT,
            customer_id TEXT,
            amount REAL NOT NULL,
            fee REAL NOT NULL,
            net_amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            settlement_date TEXT NOT NULL,
            payment_gateway TEXT NOT NULL,
            utr_number TEXT,
            remarks TEXT,
            ground_truth_invoice_id TEXT,
            ground_truth_scenario TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS benchmark_bank_transactions (
            bank_txn_id TEXT PRIMARY KEY,
            utr_number TEXT,
            amount REAL NOT NULL,
            transaction_date TEXT NOT NULL,
            value_date TEXT NOT NULL,
            description TEXT NOT NULL,
            bank_reference TEXT,
            settlement_reference TEXT,
            transaction_type TEXT NOT NULL,
            balance REAL,
            ground_truth_settlement_id TEXT,
            ground_truth_scenario TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Dedicated Uploaded Tables (Isolated user-uploaded datasets)
        CREATE TABLE IF NOT EXISTS uploaded_invoices (
            invoice_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            invoice_amount REAL NOT NULL,
            invoice_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            currency TEXT DEFAULT 'INR',
            description TEXT,
            gstin TEXT,
            ground_truth_scenario TEXT NOT NULL,
            expected_match_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS uploaded_settlements (
            settlement_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            invoice_reference TEXT,
            customer_id TEXT,
            amount REAL NOT NULL,
            fee REAL NOT NULL,
            net_amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            settlement_date TEXT NOT NULL,
            payment_gateway TEXT NOT NULL,
            utr_number TEXT,
            remarks TEXT,
            ground_truth_invoice_id TEXT,
            ground_truth_scenario TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS uploaded_bank_transactions (
            bank_txn_id TEXT PRIMARY KEY,
            utr_number TEXT,
            amount REAL NOT NULL,
            transaction_date TEXT NOT NULL,
            value_date TEXT NOT NULL,
            description TEXT NOT NULL,
            bank_reference TEXT,
            settlement_reference TEXT,
            transaction_type TEXT NOT NULL,
            balance REAL,
            ground_truth_settlement_id TEXT,
            ground_truth_scenario TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS uploaded_refunds (
            refund_id TEXT PRIMARY KEY,
            invoice_id TEXT,
            refund_date TEXT NOT NULL,
            refund_amount REAL NOT NULL,
            reason TEXT,
            payment_reference TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS refunds (
            refund_id TEXT PRIMARY KEY,
            invoice_id TEXT,
            refund_date TEXT NOT NULL,
            refund_amount REAL NOT NULL,
            reason TEXT,
            payment_reference TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Reconciliation runs
        CREATE TABLE IF NOT EXISTS reconciliation_runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            records_processed INTEGER NOT NULL,
            invoices_count INTEGER NOT NULL,
            settlements_count INTEGER NOT NULL,
            bank_transactions_count INTEGER NOT NULL,
            exact_matches INTEGER NOT NULL,
            fee_matches INTEGER NOT NULL,
            probable_matches INTEGER NOT NULL,
            human_review INTEGER NOT NULL,
            unresolved INTEGER NOT NULL,
            auto_resolved INTEGER NOT NULL,
            open_exception_count INTEGER DEFAULT 0,
            reconciled_amount REAL NOT NULL,
            unresolved_amount REAL NOT NULL,
            match_rate REAL NOT NULL,
            verified_accuracy REAL,
            auto_resolution_rate REAL NOT NULL,
            processing_time_ms REAL NOT NULL,
            scenario_performance_json TEXT,
            precision REAL DEFAULT 0.0,
            recall REAL DEFAULT 0.0,
            trace_json TEXT,
            dataset_source TEXT DEFAULT 'benchmark',
            dataset_id TEXT DEFAULT 'DATASET-BENCHMARK',
            source_metadata_json TEXT,
            benchmark_evaluation_json TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Reconciliation results
        CREATE TABLE IF NOT EXISTS reconciliation_results (
            result_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            invoice_id TEXT NOT NULL,
            settlement_id TEXT,
            bank_txn_id TEXT,
            invoice_amount REAL NOT NULL,
            settlement_amount REAL,
            bank_amount REAL,
            difference REAL NOT NULL,
            invoice_date TEXT NOT NULL,
            payment_date TEXT,
            settlement_date TEXT,
            days_delayed INTEGER,
            customer_name TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            match_type TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            exception_category TEXT,
            evidence_json TEXT,
            system_assessment TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            ground_truth_scenario TEXT NOT NULL,
            is_correct_prediction INTEGER,
            processed_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES reconciliation_runs(run_id)
        );

        -- Copilot chat history
        CREATE TABLE IF NOT EXISTS copilot_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            referenced_ids_json TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        );

        -- AI Exception Analyses cache
        CREATE TABLE IF NOT EXISTS ai_exception_analyses (
            invoice_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (invoice_id, run_id)
        );

        -- Dataset-scoped ground truth (strictly bound to dataset_id)
        CREATE TABLE IF NOT EXISTS dataset_ground_truth (
            dataset_id TEXT PRIMARY KEY,
            ground_truth_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        -- Active dataset tracking
        CREATE TABLE IF NOT EXISTS active_dataset_source (
            id INTEGER PRIMARY KEY,
            source_type TEXT NOT NULL,
            dataset_id TEXT NOT NULL DEFAULT 'DATASET-BENCHMARK',
            active_run_id TEXT,
            metadata_json TEXT,
            has_ground_truth INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Human review audit log
        CREATE TABLE IF NOT EXISTS audit_log (
            audit_id TEXT PRIMARY KEY,
            result_id TEXT NOT NULL,
            invoice_id TEXT NOT NULL,
            action TEXT NOT NULL,
            previous_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            actor TEXT NOT NULL,
            notes TEXT,
            timestamp TEXT NOT NULL
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_results_run_id ON reconciliation_results(run_id);
        CREATE INDEX IF NOT EXISTS idx_results_status ON reconciliation_results(status);
        CREATE INDEX IF NOT EXISTS idx_results_match_type ON reconciliation_results(match_type);
        CREATE INDEX IF NOT EXISTS idx_results_confidence ON reconciliation_results(confidence_score);
        CREATE INDEX IF NOT EXISTS idx_audit_result_id ON audit_log(result_id);
        """)

        table_info = conn.execute("PRAGMA table_info(reconciliation_runs)").fetchall()
        existing_cols = [row["name"] for row in table_info]
        if "open_exception_count" not in existing_cols:
            conn.execute("ALTER TABLE reconciliation_runs ADD COLUMN open_exception_count INTEGER DEFAULT 0")
        if "trace_json" not in existing_cols:
            conn.execute("ALTER TABLE reconciliation_runs ADD COLUMN trace_json TEXT")
        if "precision" not in existing_cols:
            conn.execute("ALTER TABLE reconciliation_runs ADD COLUMN precision REAL DEFAULT 0.0")
        if "benchmark_evaluation_json" not in existing_cols:
            conn.execute("ALTER TABLE reconciliation_runs ADD COLUMN benchmark_evaluation_json TEXT")
        if "dataset_id" not in existing_cols:
            conn.execute("ALTER TABLE reconciliation_runs ADD COLUMN dataset_id TEXT DEFAULT 'DATASET-BENCHMARK'")

        active_source_info = conn.execute("PRAGMA table_info(active_dataset_source)").fetchall()
        active_cols = [row["name"] for row in active_source_info]
        if "dataset_id" not in active_cols:
            conn.execute("ALTER TABLE active_dataset_source ADD COLUMN dataset_id TEXT DEFAULT 'DATASET-BENCHMARK'")
        if "active_run_id" not in active_cols:
            conn.execute("ALTER TABLE active_dataset_source ADD COLUMN active_run_id TEXT")
        if "has_ground_truth" not in active_cols:
            conn.execute("ALTER TABLE active_dataset_source ADD COLUMN has_ground_truth INTEGER DEFAULT 0")


def _find_data_dir() -> Path:
    candidates = [
        Path(__file__).parent.parent.parent / "data",
        Path(__file__).parent.parent / "data",
        Path(__file__).parent / "data",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def ensure_benchmark_data(conn: sqlite3.Connection):
    """Populates benchmark_* tables from data/*.csv if empty. Never mutates them afterwards."""
    count = conn.execute("SELECT COUNT(*) FROM benchmark_invoices").fetchone()[0]
    if count == 0:
        data_dir = _find_data_dir()
        import csv

        inv_file = data_dir / "invoices.csv"
        if inv_file.exists():
            with open(inv_file, "r", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO benchmark_invoices
                        (invoice_id, customer_name, customer_id, invoice_amount, invoice_date,
                         due_date, currency, description, gstin, ground_truth_scenario, expected_match_id)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            row["invoice_id"],
                            row["customer_name"],
                            row["customer_id"],
                            float(row["invoice_amount"]),
                            row["invoice_date"],
                            row["due_date"],
                            row.get("currency", "INR"),
                            row.get("description", ""),
                            row.get("gstin", ""),
                            row.get("ground_truth_scenario", "exact_match"),
                            row.get("expected_match_id"),
                        ),
                    )

        set_file = data_dir / "settlements.csv"
        if set_file.exists():
            with open(set_file, "r", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO benchmark_settlements
                        (settlement_id, payment_id, invoice_reference, customer_id, amount, fee,
                         net_amount, payment_date, settlement_date, payment_gateway, utr_number,
                         remarks, ground_truth_invoice_id, ground_truth_scenario)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            row["settlement_id"],
                            row["payment_id"],
                            row.get("invoice_reference"),
                            row.get("customer_id"),
                            float(row["amount"]),
                            float(row.get("fee", 0.0)),
                            float(row.get("net_amount", row["amount"])),
                            row["payment_date"],
                            row["settlement_date"],
                            row.get("payment_gateway", "Razorpay"),
                            row.get("utr_number"),
                            row.get("remarks", ""),
                            row.get("ground_truth_invoice_id"),
                            row.get("ground_truth_scenario", "exact_match"),
                        ),
                    )

        bank_file = data_dir / "bank_transactions.csv"
        if bank_file.exists():
            with open(bank_file, "r", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO benchmark_bank_transactions
                        (bank_txn_id, utr_number, amount, transaction_date, value_date, description,
                         bank_reference, settlement_reference, transaction_type, balance,
                         ground_truth_settlement_id, ground_truth_scenario)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            row["bank_txn_id"],
                            row.get("utr_number"),
                            float(row["amount"]),
                            row["transaction_date"],
                            row.get("value_date", row["transaction_date"]),
                            row.get("description", ""),
                            row.get("bank_reference"),
                            row.get("settlement_reference"),
                            row.get("transaction_type", "credit"),
                            float(row["balance"]) if row.get("balance") else None,
                            row.get("ground_truth_settlement_id"),
                            row.get("ground_truth_scenario", "exact_match"),
                        ),
                    )

    data_dir = _find_data_dir()
    gt_file = data_dir / "ground_truth.json"
    if gt_file.exists():
        with open(gt_file, "r", encoding="utf-8") as f:
            gt_text = f.read()
            conn.execute(
                "INSERT OR REPLACE INTO dataset_ground_truth (dataset_id, ground_truth_json, created_at) VALUES ('DATASET-BENCHMARK', ?, datetime('now'))",
                (gt_text,)
            )


def load_benchmark_dataset(dataset_id: str = "DATASET-BENCHMARK") -> str:
    """
    Activates Benchmark Mode.
    Restores active tables strictly from benchmark_* without touching uploaded_*.
    Sets has_ground_truth = 1 explicitly for DATASET-BENCHMARK.
    """
    with get_db() as conn:
        ensure_benchmark_data(conn)
        conn.execute("DELETE FROM invoices")
        conn.execute("INSERT INTO invoices SELECT * FROM benchmark_invoices")
        conn.execute("DELETE FROM settlements")
        conn.execute("INSERT INTO settlements SELECT * FROM benchmark_settlements")
        conn.execute("DELETE FROM bank_transactions")
        conn.execute("INSERT INTO bank_transactions SELECT * FROM benchmark_bank_transactions")
        conn.execute("DELETE FROM refunds")

        conn.execute(
            """
            INSERT OR REPLACE INTO active_dataset_source (id, source_type, dataset_id, active_run_id, metadata_json, has_ground_truth, updated_at)
            VALUES (1, 'benchmark', ?, NULL, '{}', 1, datetime('now'))
            """,
            (dataset_id,)
        )
    return dataset_id


def reset_uploaded_dataset(new_dataset_id: Optional[str] = None) -> str:
    """
    Begins a brand new uploaded dataset session from scratch.
    Clears uploaded_* tables, active tables, resets active_run_id.
    Sets activeDatasetMode = 'uploaded' with a new unique dataset_id.
    Sets has_ground_truth = 0 (no ground truth attached unless explicitly provided for this dataset).
    Benchmark tables are never touched. Historical runs in reconciliation_runs are preserved.
    """
    ds_id = new_dataset_id or f"DATASET-{uuid.uuid4().hex[:8].upper()}"
    with get_db() as conn:
        conn.execute("DELETE FROM uploaded_invoices")
        conn.execute("DELETE FROM uploaded_settlements")
        conn.execute("DELETE FROM uploaded_bank_transactions")
        conn.execute("DELETE FROM uploaded_refunds")
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM settlements")
        conn.execute("DELETE FROM bank_transactions")
        conn.execute("DELETE FROM refunds")
        conn.execute(
            """
            INSERT OR REPLACE INTO active_dataset_source (id, source_type, dataset_id, active_run_id, metadata_json, has_ground_truth, updated_at)
            VALUES (1, 'uploaded', ?, NULL, '{}', 0, datetime('now'))
            """,
            (ds_id,)
        )
    return ds_id


def attach_dataset_ground_truth(dataset_id: str, ground_truth_json: str):
    """Explicitly associates a ground truth answer key with one specific dataset_id only."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO dataset_ground_truth (dataset_id, ground_truth_json, created_at) VALUES (?, ?, datetime('now'))",
            (dataset_id, ground_truth_json),
        )
        conn.execute(
            "UPDATE active_dataset_source SET has_ground_truth = 1 WHERE dataset_id = ?",
            (dataset_id,),
        )


def get_dataset_ground_truth(dataset_id: str) -> Optional[List[Dict[str, Any]]]:
    """Retrieves ground truth strictly scoped to the specified dataset_id. Never falls back globally."""
    if not dataset_id:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT ground_truth_json FROM dataset_ground_truth WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchone()
        if row and row["ground_truth_json"]:
            try:
                return json.loads(row["ground_truth_json"])
            except Exception:
                return None
    return None


if __name__ == "__main__":
    init_db()
    with get_db() as c:
        ensure_benchmark_data(c)
    print("Database initialized at ", DB_PATH)
