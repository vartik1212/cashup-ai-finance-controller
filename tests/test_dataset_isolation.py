"""
Tests for Complete Dataset Isolation in ReconAI
================================================
Verifies that:
- Benchmark Dataset and Uploaded Dataset maintain completely isolated state.
- Uploading from Benchmark mode creates a fresh, empty uploadedDataset without inheriting benchmark records.
- Zero INV-2026-* IDs exist in uploadedDataset.
- Switching to Load Demo restores 120 / 120 / 120 without touching uploaded data.
- Subsequent uploads in uploaded mode append only to uploadedDataset.
- Duplicate primary keys within the uploaded dataset are rejected and not silently duplicated.
"""

import os
import json
import base64
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.database.db import get_db, init_db, load_benchmark_dataset, reset_uploaded_dataset

client = TestClient(app)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "alternate_schemas"
INVOICES_CSV = FIXTURES_DIR / "reconai_customer_invoices.csv"
SETTLEMENTS_CSV = FIXTURES_DIR / "reconai_processor_settlements.csv"
BANK_CSV = FIXTURES_DIR / "reconai_bank_statement.csv"


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database initialized and demo loaded before tests."""
    init_db()
    load_benchmark_dataset()


def test_1_load_demo_counts():
    """TEST 1: Load Demo => 120 / 120 / 120"""
    resp = client.post("/api/data/load-demo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["invoices_loaded"] == 120
    assert data["settlements_loaded"] == 120
    assert data["bank_transactions_loaded"] == 120

    status = client.get("/api/data/status").json()
    assert status["invoices"] == 120
    assert status["settlements"] == 120
    assert status["bank_transactions"] == 120
    assert status["dataset_source"] == "benchmark"


def test_2_and_3_and_4_upload_three_files_from_benchmark_mode():
    """
    TEST 2: From Benchmark mode upload all three custom files => 60 / 63 / 58
    TEST 3: Assert zero INV-2026-* benchmark IDs exist in uploaded dataset.
    TEST 4: Assert BILL-2026* uploaded IDs exist.
    """
    # 1. Ensure benchmark mode is active
    client.post("/api/data/load-demo")
    status_before = client.get("/api/data/status").json()
    assert status_before["dataset_source"] == "benchmark"
    assert status_before["invoices"] == 120

    # 2. Upload all 3 custom files together
    with open(INVOICES_CSV, "rb") as f: inv_b64 = base64.b64encode(f.read()).decode("ascii")
    with open(SETTLEMENTS_CSV, "rb") as f: set_b64 = base64.b64encode(f.read()).decode("ascii")
    with open(BANK_CSV, "rb") as f: bnk_b64 = base64.b64encode(f.read()).decode("ascii")

    confirm_payload = {
        "files": [
            {
                "filename": "reconai_customer_invoices.csv",
                "file_type": "INVOICES",
                "column_mapping": {
                    "bill_no": "invoice_id",
                    "company": "customer_name",
                    "bill_value": "amount",
                    "created_date": "invoice_date",
                    "currency_code": "currency",
                },
                "file_content_b64": inv_b64,
            },
            {
                "filename": "reconai_processor_settlements.csv",
                "file_type": "SETTLEMENTS",
                "column_mapping": {
                    "payment_ref": "settlement_id",
                    "bill_reference": "invoice_reference",
                    "gross": "gross_amount",
                    "processing_charge": "fee_amount",
                    "tax_on_charge": "fee_tax",
                    "received": "net_amount",
                    "paid_on": "settlement_date",
                },
                "file_content_b64": set_b64,
            },
            {
                "filename": "reconai_bank_statement.csv",
                "file_type": "BANK_TRANSACTIONS",
                "column_mapping": {
                    "utr": "bank_reference",
                    "txn_date": "transaction_date",
                    "credit": "credit_amount",
                    "description": "description",
                },
                "file_content_b64": bnk_b64,
            },
        ]
    }

    resp = client.post("/api/upload/confirm", json=confirm_payload)
    assert resp.status_code == 200
    res_data = resp.json()
    counts = res_data["dataset_counts"]

    # TEST 2: Assert counts are strictly 60 / 63 / 58
    assert counts["existing"]["invoices"] == 0
    assert counts["existing"]["settlements"] == 0
    assert counts["existing"]["bank_transactions"] == 0
    assert counts["added"]["invoices"] == 60
    assert counts["added"]["settlements"] == 63
    assert counts["added"]["bank_transactions"] == 58
    assert counts["result"]["invoices"] == 60
    assert counts["result"]["settlements"] == 63
    assert counts["result"]["bank_transactions"] == 58

    status = client.get("/api/data/status").json()
    assert status["invoices"] == 60
    assert status["settlements"] == 63
    assert status["bank_transactions"] == 58
    assert status["dataset_source"] == "uploaded"

    # TEST 3: Assert zero INV-2026-* benchmark IDs exist in uploaded dataset
    with get_db() as conn:
        inv_ids = [r[0] for r in conn.execute("SELECT invoice_id FROM uploaded_invoices").fetchall()]
        active_inv_ids = [r[0] for r in conn.execute("SELECT invoice_id FROM invoices").fetchall()]

    benchmark_ids_in_uploaded = [iid for iid in inv_ids if iid.startswith("INV-2026-")]
    benchmark_ids_in_active = [iid for iid in active_inv_ids if iid.startswith("INV-2026-")]
    assert len(benchmark_ids_in_uploaded) == 0, f"Found benchmark IDs in uploaded table: {benchmark_ids_in_uploaded}"
    assert len(benchmark_ids_in_active) == 0, f"Found benchmark IDs in active invoices: {benchmark_ids_in_active}"

    # TEST 4: Assert BILL-2026* uploaded IDs exist
    bill_ids = [iid for iid in inv_ids if iid.startswith("BILL-2026")]
    assert len(bill_ids) == 60, f"Expected 60 BILL-2026* IDs, found {len(bill_ids)}"
    assert "BILL-2026001" in bill_ids
    assert "BILL-2026060" in bill_ids


def test_5_switch_back_to_load_demo():
    """TEST 5: Switch back to Load Demo => 120 / 120 / 120"""
    # 1. First upload custom files to be in uploaded mode
    with open(INVOICES_CSV, "rb") as f: inv_b64 = base64.b64encode(f.read()).decode("ascii")
    client.post("/api/upload/confirm", json={
        "files": [{
            "filename": "reconai_customer_invoices.csv",
            "file_type": "INVOICES",
            "column_mapping": {"bill_no": "invoice_id", "company": "customer_name", "bill_value": "amount", "created_date": "invoice_date"},
            "file_content_b64": inv_b64,
        }]
    })
    status_uploaded = client.get("/api/data/status").json()
    assert status_uploaded["dataset_source"] == "uploaded"
    assert status_uploaded["invoices"] == 60

    # 2. Switch back to demo
    load_resp = client.post("/api/data/load-demo")
    assert load_resp.status_code == 200

    status_demo = client.get("/api/data/status").json()
    assert status_demo["dataset_source"] == "benchmark"
    assert status_demo["invoices"] == 120
    assert status_demo["settlements"] == 120
    assert status_demo["bank_transactions"] == 120

    with get_db() as conn:
        active_ids = [r[0] for r in conn.execute("SELECT invoice_id FROM invoices").fetchall()]
    assert any(iid.startswith("INV-2026-") for iid in active_ids)
    assert not any(iid.startswith("BILL-2026") for iid in active_ids)


def test_6_start_another_uploaded_dataset_from_benchmark():
    """TEST 6: Start another uploaded dataset => previous benchmark records are not inherited."""
    # Ensure in benchmark mode
    client.post("/api/data/load-demo")

    # Start upload with invoices only
    with open(INVOICES_CSV, "rb") as f: inv_b64 = base64.b64encode(f.read()).decode("ascii")
    resp = client.post("/api/upload/confirm", json={
        "files": [{
            "filename": "reconai_customer_invoices.csv",
            "file_type": "INVOICES",
            "column_mapping": {"bill_no": "invoice_id", "company": "customer_name", "bill_value": "amount", "created_date": "invoice_date"},
            "file_content_b64": inv_b64,
        }]
    })
    assert resp.status_code == 200
    res = resp.json()["dataset_counts"]
    assert res["existing"]["invoices"] == 0
    assert res["added"]["invoices"] == 60
    assert res["result"]["invoices"] == 60
    assert res["result"]["settlements"] == 0
    assert res["result"]["bank_transactions"] == 0


def test_7_duplicate_primary_ids_not_duplicated():
    """TEST 7: Upload same CSV twice within same uploaded dataset. Duplicate primary IDs must not silently duplicate."""
    # Start fresh uploaded dataset
    with open(INVOICES_CSV, "rb") as f: inv_b64 = base64.b64encode(f.read()).decode("ascii")
    payload = {
        "files": [{
            "filename": "reconai_customer_invoices.csv",
            "file_type": "INVOICES",
            "column_mapping": {"bill_no": "invoice_id", "company": "customer_name", "bill_value": "amount", "created_date": "invoice_date"},
            "file_content_b64": inv_b64,
        }]
    }
    # First upload (replaces active dataset)
    res1 = client.post("/api/upload/confirm", json=payload).json()
    assert res1["dataset_counts"]["result"]["invoices"] == 60

    # Second upload of the same file with explicit append within same dataset
    payload_append = {**payload, "append": True}
    res2 = client.post("/api/upload/confirm", json=payload_append).json()
    # Should detect 60 duplicate IDs and reject them from being added again
    summary = res2["summaries"][0]
    assert summary["stats"]["valid_count"] == 0
    assert summary["stats"]["duplicate_ids"] == 60
    assert summary["stats"]["warning_count"] == 60
    assert len(summary["warnings"]) == 20  # capped display sample
    assert res2["dataset_counts"]["result"]["invoices"] == 60


def test_8_verified_accuracy_ground_truth_isolation():
    """
    Assert:
    - Benchmark mode: reconciliation computes verified_accuracy against ground truth.
    - Uploaded mode: reconciliation leaves verified_accuracy as None (N/A) since no ground truth was supplied.
    """
    # 1. Benchmark Mode
    client.post("/api/data/load-demo")
    rec_bench = client.post("/api/reconcile", json={}).json()
    run_bench = client.get("/api/reconcile/latest").json()
    assert run_bench["dataset_source"] == "benchmark"
    assert run_bench["verified_accuracy"] is not None
    assert run_bench["verified_accuracy"] > 0.0

    # 2. Uploaded Mode (3 operational files without explicit ground truth)
    with open(INVOICES_CSV, "rb") as f: inv_b64 = base64.b64encode(f.read()).decode("ascii")
    with open(SETTLEMENTS_CSV, "rb") as f: set_b64 = base64.b64encode(f.read()).decode("ascii")
    with open(BANK_CSV, "rb") as f: bnk_b64 = base64.b64encode(f.read()).decode("ascii")

    client.post("/api/upload/confirm", json={
        "files": [
            {"filename": "reconai_customer_invoices.csv", "file_type": "INVOICES", "column_mapping": {"bill_no": "invoice_id", "company": "customer_name", "bill_value": "amount", "created_date": "invoice_date"}, "file_content_b64": inv_b64},
            {"filename": "reconai_processor_settlements.csv", "file_type": "SETTLEMENTS", "column_mapping": {"payment_ref": "settlement_id", "bill_reference": "invoice_reference", "gross": "gross_amount", "processing_charge": "fee_amount", "tax_on_charge": "fee_tax", "received": "net_amount", "paid_on": "settlement_date"}, "file_content_b64": set_b64},
            {"filename": "reconai_bank_statement.csv", "file_type": "BANK_TRANSACTIONS", "column_mapping": {"utr": "bank_reference", "txn_date": "transaction_date", "credit": "credit_amount", "description": "description"}, "file_content_b64": bnk_b64},
        ]
    })
    rec_up = client.post("/api/reconcile", json={}).json()
    run_up = client.get("/api/reconcile/latest").json()
    status_up = client.get("/api/data/status").json()
    assert run_up["dataset_source"] == "uploaded"
    assert status_up["dataset_source"] == "uploaded"
    assert status_up["has_ground_truth"] is False
    # Without explicitly attached ground truth, verified_accuracy MUST be None (N/A)
    assert run_up["verified_accuracy"] is None
    assert run_up.get("benchmark_evaluation") is None

    # 3. Explicit ground truth attachment: ONLY when ground truth is explicitly attached to this dataset_id
    from evaluation.evaluate_baseline import GT_PATH
    import csv
    with open(GT_PATH, "r", encoding="utf-8-sig") as f:
        gt_rows = list(csv.DictReader(f))

    attach_res = client.post("/api/data/attach-ground-truth", json={"ground_truth": gt_rows})
    assert attach_res.status_code == 200
    status_attached = client.get("/api/data/status").json()
    assert status_attached["has_ground_truth"] is True

    # Reconciling with explicitly attached ground truth enables numeric verified_accuracy
    client.post("/api/reconcile", json={})
    run_attached = client.get("/api/reconcile/latest").json()
    assert run_attached["verified_accuracy"] is not None
    assert run_attached["verified_accuracy"] == 0.85

    # 4. Normal uploaded dataset WITHOUT ground truth (arbitrary invoices)
    reset_uploaded_dataset()
    inv_custom = "invoice_id,customer_name,amount,invoice_date\nINV-CUSTOM-001,Acme Corp,50000,2026-03-01\nINV-CUSTOM-002,Beta LLC,75000,2026-03-02\n"
    inv_custom_b64 = base64.b64encode(inv_custom.encode("utf-8")).decode("ascii")
    client.post("/api/upload/confirm", json={
        "files": [
            {"filename": "custom_invoices.csv", "file_type": "INVOICES", "column_mapping": {"invoice_id": "invoice_id", "customer_name": "customer_name", "amount": "amount", "invoice_date": "invoice_date"}, "file_content_b64": inv_custom_b64}
        ]
    })
    client.post("/api/reconcile", json={})
    run_no_gt = client.get("/api/reconcile/latest").json()
    assert run_no_gt["dataset_source"] == "uploaded"
    assert run_no_gt["verified_accuracy"] is None

    # Restore 60-record benchmark uploaded dataset for subsequent tests
    reset_uploaded_dataset()
    client.post("/api/upload/confirm", json={
        "files": [
            {"filename": "reconai_customer_invoices.csv", "file_type": "INVOICES", "column_mapping": {"bill_no": "invoice_id", "company": "customer_name", "bill_value": "amount", "created_date": "invoice_date"}, "file_content_b64": inv_b64},
            {"filename": "reconai_processor_settlements.csv", "file_type": "SETTLEMENTS", "column_mapping": {"payment_ref": "settlement_id", "bill_reference": "invoice_reference", "gross": "gross_amount", "processing_charge": "fee_amount", "tax_on_charge": "fee_tax", "received": "net_amount", "paid_on": "settlement_date"}, "file_content_b64": set_b64},
            {"filename": "reconai_bank_statement.csv", "file_type": "BANK_TRANSACTIONS", "column_mapping": {"utr": "bank_reference", "txn_date": "transaction_date", "credit": "credit_amount", "description": "description"}, "file_content_b64": bnk_b64},
        ]
    })
    client.post("/api/reconcile", json={})
