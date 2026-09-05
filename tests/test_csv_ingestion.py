"""
ReconAI — CSV Ingestion & Schema Understanding Unit & Integration Tests
=======================================================================
Validates:
- CSV Profiling (rows, columns, types, nulls, duplicates)
- Heuristic and deterministic file-type detection
- Schema mapping (synonym dictionary, canonical fields, confidence)
- Validation rules (invalid amount, negative amount, duplicate IDs, missing fields)
- Normalization into existing domain models
- Alternate-schema end-to-end reconciliation via existing LangGraph engine
- Honesty in evaluation metrics when ground truth is absent (N/A)
"""

import io
import csv
import json
import unittest
from pathlib import Path

from backend.ingestion.profiler import profile_csv, detect_type
from backend.ingestion.detector import detect_file_type, score_heuristics
from backend.ingestion.schema_mapper import (
    map_columns_deterministic,
    get_canonical_schema,
    CANONICAL_SCHEMAS,
)
from backend.ingestion.validator import (
    parse_amount,
    parse_date,
    validate_records,
)
from backend.ingestion.normalizer import normalize_and_store
from backend.workflow.reconciliation_graph import reconciliation_graph
from backend.models.schemas import ReconciliationStatus, MatchType


class TestCSVProfiler(unittest.TestCase):
    def test_profiling_standard_csv(self):
        csv_data = b"invoice_id,customer,amount,date\nINV-001,Acme,5000,2026-01-01\nINV-002,Beta,10000,2026-01-02\n"
        prof = profile_csv(csv_data, "invoices.csv")
        self.assertEqual(prof["row_count"], 2)
        self.assertEqual(prof["column_count"], 4)
        self.assertEqual(prof["duplicate_rows"], 0)
        self.assertIn("columns", prof)
        cols = {c["column_name"]: c for c in prof["columns"]}
        self.assertIn("invoice_id", cols)
        self.assertEqual(cols["amount"]["detected_type"], "number")
        self.assertEqual(cols["date"]["detected_type"], "date")

    def test_profiling_duplicate_detection(self):
        csv_data = b"id,val\nA,10\nA,10\nB,20\n"
        prof = profile_csv(csv_data, "test.csv")
        self.assertEqual(prof["row_count"], 3)
        self.assertEqual(prof["duplicate_rows"], 1)

    def test_profiling_empty_file(self):
        prof = profile_csv(b"", "empty.csv")
        self.assertIn("error", prof)


class TestFileTypeDetector(unittest.TestCase):
    def test_detect_invoices(self):
        cols = ["bill_no", "company", "bill_value", "created_date"]
        res = detect_file_type("customer_invoices.csv", cols)
        self.assertEqual(res["file_type"], "INVOICES")
        self.assertGreater(res["confidence"], 0.6)

    def test_detect_settlements(self):
        cols = ["payment_ref", "bill_reference", "gross", "processing_charge", "tax_on_charge", "received", "paid_on"]
        res = detect_file_type("processor.csv", cols)
        self.assertEqual(res["file_type"], "SETTLEMENTS")
        self.assertGreater(res["confidence"], 0.6)

    def test_detect_bank_transactions(self):
        cols = ["utr", "txn_date", "credit", "description"]
        res = detect_file_type("statement.csv", cols)
        self.assertEqual(res["file_type"], "BANK_TRANSACTIONS")
        self.assertGreater(res["confidence"], 0.6)

    def test_detect_unknown(self):
        cols = ["color", "shape", "animal"]
        res = detect_file_type("random.csv", cols)
        self.assertEqual(res["file_type"], "UNKNOWN")


class TestSchemaMapper(unittest.TestCase):
    def test_invoice_alternate_column_mapping(self):
        cols = ["bill_no", "company", "bill_value", "created_date"]
        mappings = map_columns_deterministic("INVOICES", cols)
        mapped = {m["source_column"]: m["target_field"] for m in mappings}
        self.assertEqual(mapped.get("bill_no"), "invoice_id")
        self.assertEqual(mapped.get("company"), "customer_name")
        self.assertEqual(mapped.get("bill_value"), "amount")
        self.assertEqual(mapped.get("created_date"), "invoice_date")

    def test_settlement_alternate_column_mapping(self):
        cols = ["payment_ref", "bill_reference", "gross", "processing_charge", "tax_on_charge", "received", "paid_on"]
        mappings = map_columns_deterministic("SETTLEMENTS", cols)
        mapped = {m["source_column"]: m["target_field"] for m in mappings}
        self.assertEqual(mapped.get("payment_ref"), "settlement_id")
        self.assertEqual(mapped.get("bill_reference"), "invoice_reference")
        self.assertEqual(mapped.get("gross"), "gross_amount")
        self.assertEqual(mapped.get("processing_charge"), "fee_amount")
        self.assertEqual(mapped.get("tax_on_charge"), "fee_tax")
        self.assertEqual(mapped.get("received"), "net_amount")
        self.assertEqual(mapped.get("paid_on"), "settlement_date")


class TestValidator(unittest.TestCase):
    def test_amount_parsing(self):
        amt, err = parse_amount(" ₹ 45,000.50 ")
        self.assertIsNone(err)
        self.assertEqual(amt, 45000.50)

        amt, err = parse_amount("-100.00")
        self.assertIsNotNone(err)
        self.assertIn("Negative amount", err)

        amt, err = parse_amount("invalid_val")
        self.assertIsNotNone(err)

    def test_date_parsing(self):
        d, err = parse_date("2026-03-01")
        self.assertEqual(d, "2026-03-01")

        d, err = parse_date("01/03/2026")
        self.assertEqual(d, "2026-03-01")

        d, err = parse_date("not-a-date")
        self.assertIsNone(d)

    def test_validation_rejects_missing_required_and_duplicate(self):
        raw_rows = [
            {"bill_no": "INV-100", "amt": "1000", "dt": "2026-01-01"},
            {"bill_no": "INV-100", "amt": "2000", "dt": "2026-01-02"},  # duplicate
            {"bill_no": "", "amt": "3000", "dt": "2026-01-03"},         # missing ID
            {"bill_no": "INV-101", "amt": "-500", "dt": "2026-01-04"},  # negative
        ]
        mapping = {
            "bill_no": "invoice_id",
            "amt": "amount",
            "dt": "invoice_date",
        }
        res = validate_records("INVOICES", raw_rows, mapping)
        self.assertEqual(res["stats"]["valid_count"], 1)
        self.assertEqual(res["stats"]["rejected_count"], 3)
        self.assertEqual(res["stats"]["duplicate_ids"], 1)


class TestAlternateSchemaEndToEnd(unittest.TestCase):
    def test_alternate_schema_reconciliation(self):
        fixtures_dir = Path(__file__).parent / "fixtures" / "alternate_schemas"

        with open(fixtures_dir / "customer_invoices.csv", "r") as f:
            inv_rows = list(csv.DictReader(f))
        with open(fixtures_dir / "processor.csv", "r") as f:
            set_rows = list(csv.DictReader(f))
        with open(fixtures_dir / "statement.csv", "r") as f:
            bnk_rows = list(csv.DictReader(f))

        inv_map = {
            "bill_no": "invoice_id",
            "company": "customer_name",
            "bill_value": "amount",
            "created_date": "invoice_date",
        }
        set_map = {
            "payment_ref": "settlement_id",
            "bill_reference": "invoice_reference",
            "gross": "gross_amount",
            "processing_charge": "fee_amount",
            "tax_on_charge": "fee_tax",
            "received": "net_amount",
            "paid_on": "settlement_date",
        }
        bnk_map = {
            "utr": "bank_transaction_id",
            "txn_date": "transaction_date",
            "credit": "credit_amount",
            "description": "description",
        }

        val_inv = validate_records("INVOICES", inv_rows, inv_map)
        val_set = validate_records("SETTLEMENTS", set_rows, set_map)
        val_bnk = validate_records("BANK_TRANSACTIONS", bnk_rows, bnk_map)

        self.assertEqual(val_inv["stats"]["valid_count"], 3)
        self.assertEqual(val_set["stats"]["valid_count"], 3)
        self.assertEqual(val_bnk["stats"]["valid_count"], 3)

        # Store in database and execute LangGraph workflow
        normalize_and_store(
            invoices_data=val_inv["valid_records"],
            settlements_data=val_set["valid_records"],
            bank_data=val_bnk["valid_records"],
            source_metadata={"dataset_name": "Test Alternate Dataset"},
        )

        state = {
            "run_id": "TEST-RUN-ALT-SCHEMA",
            "raw_invoices": val_inv["valid_records"],
            "raw_settlements": val_set["valid_records"],
            "raw_bank_transactions": val_bnk["valid_records"],
            "ground_truth_records": [],  # No ground truth for user uploads!
        }

        output = reconciliation_graph.invoke(state)
        run = output["run_summary"]
        results = output["reconciliation_results"]

        self.assertEqual(run.records_processed, 3)
        self.assertEqual(run.match_rate, 1.0)  # All 3 matched!
        self.assertEqual(run.exact_matches, 1)  # INV-ALT-001 (clean exact)
        self.assertEqual(run.fee_matches, 1)    # INV-ALT-002 (fee adjusted)
        self.assertEqual(run.probable_matches, 1) # INV-ALT-003 (delayed 15 days)

        # Ground truth honesty check:
        self.assertIsNone(run.verified_accuracy)
        self.assertIsNone(run.precision)
        self.assertIsNone(run.recall)


class TestIncrementalCSVImport(unittest.TestCase):
    def test_duplicate_id_detection_against_active_dataset(self):
        existing_ids = {"INV-EXISTING-001"}
        rows = [
            {"invoice_no": "INV-EXISTING-001", "amt": "5000", "date": "2026-08-01"},
            {"invoice_no": "INV-NEW-002", "amt": "7500", "date": "2026-08-02"},
        ]
        mapping = {"invoice_no": "invoice_id", "amt": "amount", "date": "invoice_date"}
        res = validate_records("INVOICES", rows, mapping, existing_ids=existing_ids)

        self.assertEqual(res["stats"]["valid_count"], 1)
        self.assertEqual(res["stats"]["rejected_count"], 1)
        self.assertEqual(res["stats"]["duplicate_ids"], 1)
        self.assertEqual(res["valid_records"][0]["invoice_id"], "INV-NEW-002")
        self.assertTrue(any("already exists in active dataset" in w for w in res["warnings"]))

    def test_normalize_and_store_incremental_preserves_records(self):
        # 1. Store first batch (invoices only)
        inv1 = [{"invoice_id": "INV-TEST-A1", "invoice_amount": 1000.0, "invoice_date": "2026-08-01"}]
        res1 = normalize_and_store(invoices_data=inv1, settlements_data=[], bank_data=[], clear_existing=True)
        self.assertEqual(res1["total_invoices"], 1)
        self.assertEqual(res1["total_settlements"], 0)

        # 2. Incrementally store settlements without invoices
        set1 = [{
            "settlement_id": "SET-TEST-B1",
            "invoice_reference": "INV-TEST-A1",
            "amount": 1000.0,
            "fee": 20.0,
            "net_amount": 980.0,
            "settlement_date": "2026-08-02",
        }]
        res2 = normalize_and_store(invoices_data=[], settlements_data=set1, bank_data=[], clear_existing=False)
        self.assertEqual(res2["total_invoices"], 1)  # Preserved!
        self.assertEqual(res2["total_settlements"], 1)

        # 3. Incrementally store duplicate settlement (must not duplicate)
        res3 = normalize_and_store(invoices_data=[], settlements_data=set1, bank_data=[], clear_existing=False)
        self.assertEqual(res3["total_invoices"], 1)
        self.assertEqual(res3["total_settlements"], 1)  # Still 1, not 2!


if __name__ == "__main__":
    unittest.main()

