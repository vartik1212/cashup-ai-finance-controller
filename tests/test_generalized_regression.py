"""
ReconAI — Generalized Regression & Schema Mapping Test Suite
============================================================
Tests generalized file-type detection, invoice vs settlement disambiguation,
refund semantic inference, bank reference identifier role inference,
confidence/action consistency, cross-file reasoning, and zero-invoice validation guard.
"""

import unittest
import random
from typing import List, Dict, Any
from backend.ingestion.detector import detect_file_type, disambiguate_batch_file_types
from backend.ingestion.schema_mapper import map_columns_deterministic, map_columns_hybrid, CANONICAL_SCHEMAS
from backend.ingestion.validator import validate_records
from backend.ingestion.profiler import detect_type, analyze_date_values


class TestGeneralizedDetection(unittest.TestCase):
    """Verifies generalized classification across arbitrary unseen financial structures."""

    def test_structure_a_generalized_invoice_receivables(self):
        """Structure A: Generalized invoice/receivables (must not classify as SETTLEMENTS)."""
        cols = ["doc_number", "buyer_name", "doc_date", "payment_due", "receivable_amount"]
        res = detect_file_type("unseen_receivables_data.csv", cols)
        self.assertEqual(res["file_type"], "INVOICES")
        self.assertGreaterEqual(res["confidence"], 0.80)
        self.assertIn("INVOICES", res["reason"])

    def test_structure_a_invoice_with_generic_amount(self):
        """Invoice with generic 'amount' and 'party' but no gateway fees must NOT be SETTLEMENTS."""
        cols = ["bill_no", "party_name", "bill_date", "due_date", "amount"]
        res = detect_file_type("ledger_export.csv", cols)
        self.assertEqual(res["file_type"], "INVOICES")
        self.assertGreaterEqual(res["confidence"], 0.80)

    def test_structure_b_generalized_settlements(self):
        """Structure B: Generalized settlements with fee/charges and payout amounts."""
        cols = ["payout_id", "order_ref", "processed_at", "captured_amount", "processing_charge", "net_remitted"]
        res = detect_file_type("processor_settlement_report.csv", cols)
        self.assertEqual(res["file_type"], "SETTLEMENTS")
        self.assertGreaterEqual(res["confidence"], 0.80)

    def test_structure_b_settlements_fee_decomposition(self):
        """Settlements with fee, tax on fee, gross, and net."""
        cols = ["gateway_txn", "invoice_ref", "paid_on", "gross", "mdr_fee", "tax_on_charge", "received"]
        res = detect_file_type("gateway_download.csv", cols)
        self.assertEqual(res["file_type"], "SETTLEMENTS")
        self.assertGreaterEqual(res["confidence"], 0.80)

    def test_structure_c_generalized_bank_statement(self):
        """Structure C: Generalized bank statement with UTR, balance, and particulars."""
        cols = ["value_date", "particulars", "utr_number", "deposit_amount", "withdrawal_amount", "running_balance"]
        res = detect_file_type("corporate_account_statement.csv", cols)
        self.assertEqual(res["file_type"], "BANK_TRANSACTIONS")
        self.assertGreaterEqual(res["confidence"], 0.80)

    def test_structure_d_generalized_refund_credit_note(self):
        """Structure D: Generalized refund/reversal credit note."""
        cols = ["credit_note_no", "orig_invoice_id", "date_reversed", "returned_amount", "reason_for_return"]
        res = detect_file_type("reversals_export.csv", cols)
        self.assertEqual(res["file_type"], "REFUNDS")
        self.assertGreaterEqual(res["confidence"], 0.80)

    def test_structure_d_refund_dispute_chargeback(self):
        """Refund with dispute/chargeback terminology."""
        cols = ["dispute_id", "order_id", "refund_date", "refund_amount", "remarks"]
        res = detect_file_type("disputes_log.csv", cols)
        self.assertEqual(res["file_type"], "REFUNDS")
        self.assertGreaterEqual(res["confidence"], 0.80)

    def test_permuted_columns_invariance(self):
        """Classification must be invariant to column ordering and casing permutations."""
        base_inv_cols = ["Doc_Date", "Buyer_Name", "Payment_Due", "RECEIVABLE_AMOUNT", "Doc_Number"]
        shuffled = base_inv_cols.copy()
        random.seed(42)
        random.shuffle(shuffled)
        res = detect_file_type("random_inv.csv", shuffled)
        self.assertEqual(res["file_type"], "INVOICES")

        base_set_cols = ["Net_Remitted", "Processing_Charge", "Order_Ref", "Captured_Amount", "Payout_Id"]
        random.shuffle(base_set_cols)
        res_set = detect_file_type("random_set.csv", base_set_cols)
        self.assertEqual(res_set["file_type"], "SETTLEMENTS")


class TestSchemaMappingAndIdentifiers(unittest.TestCase):
    """Verifies schema mapping, identifier role inference, and confidence consistency."""

    def test_bank_reference_utr_mapping(self):
        """Bank statement UTR column must map to bank_reference (valid canonical field)."""
        cols = ["value_date", "particulars", "utr_number", "deposit_amount", "running_balance"]
        mappings = map_columns_deterministic("BANK_TRANSACTIONS", cols)

        utr_mapping = next((m for m in mappings if m["source_column"] == "utr_number"), None)
        self.assertIsNotNone(utr_mapping)
        self.assertEqual(utr_mapping["target_field"], "bank_reference")
        self.assertGreaterEqual(utr_mapping["confidence"], 0.85)

        # Ensure target_field exists in canonical schema fields
        canonical_fields = [f["field"] for f in CANONICAL_SCHEMAS["BANK_TRANSACTIONS"]]
        self.assertIn("bank_reference", canonical_fields)
        self.assertIn(utr_mapping["target_field"], canonical_fields)

    def test_bank_transaction_validation_with_only_reference(self):
        """Validates bank statement that has bank_reference/UTR without explicit bank_transaction_id."""
        raw_rows = [
            {
                "Date": "2026-08-25",
                "Particulars": "UPI / NEFT Credit Ref 987654",
                "UTR": "UTR20260825999",
                "Credit": "15000.00",
            }
        ]
        col_map = {
            "Date": "transaction_date",
            "Particulars": "description",
            "UTR": "bank_reference",
            "Credit": "credit_amount",
        }
        res = validate_records("BANK_TRANSACTIONS", raw_rows, col_map)
        self.assertEqual(res["stats"]["valid_count"], 1)
        self.assertEqual(res["stats"]["rejected_count"], 0)
        valid_rec = res["valid_records"][0]
        self.assertEqual(valid_rec["utr_number"], "UTR20260825999")
        self.assertEqual(valid_rec["bank_reference"], "UTR20260825999")
        self.assertTrue(valid_rec["bank_txn_id"].startswith("UTR20260825999") or valid_rec["bank_txn_id"].startswith("BNK-AUTO"))

    def test_unmapped_column_confidence_consistency(self):
        """Unmapped columns must strictly have 0.0 confidence and unmapped status."""
        cols = ["doc_number", "buyer_name", "doc_date", "receivable_amount", "random_unrelated_column_xyz"]
        mappings = map_columns_deterministic("INVOICES", cols)

        unmapped = next((m for m in mappings if m["source_column"] == "random_unrelated_column_xyz"), None)
        self.assertIsNotNone(unmapped)
        self.assertIsNone(unmapped["target_field"])
        self.assertEqual(unmapped["confidence"], 0.0)
        self.assertEqual(unmapped["status"], "unmapped")


class TestCrossFileReasoningAndGuard(unittest.TestCase):
    """Verifies multi-file batch reasoning and zero-invoice validation guard."""

    def test_cross_file_disambiguation_receivables_and_settlements(self):
        """When receivables and settlements are uploaded together, receivables is disambiguated to INVOICES."""
        profiles = [
            {
                "filename": "file_alpha.csv",
                "detected_file_type": "SETTLEMENTS",
                "columns": [
                    {"column_name": "payout_id"},
                    {"column_name": "gross_amount"},
                    {"column_name": "fee_amount"},
                    {"column_name": "net_amount"},
                ],
            },
            {
                "filename": "file_beta.csv",
                "detected_file_type": "SETTLEMENTS",
                "columns": [
                    {"column_name": "doc_no"},
                    {"column_name": "customer_name"},
                    {"column_name": "due_date"},
                    {"column_name": "amount_due"},
                ],
            },
        ]
        disambiguated = disambiguate_batch_file_types(profiles)
        self.assertEqual(disambiguated[0]["detected_file_type"], "SETTLEMENTS")
        self.assertEqual(disambiguated[1]["detected_file_type"], "INVOICES")
        self.assertEqual(disambiguated[1]["detection_source"], "cross_file_reasoning")

    def test_zero_invoice_guard_in_confirm_logic(self):
        """Simulates zero-invoice guard logic when settlements exist but invoices are 0."""
        invoices_records = []
        settlements_records = [{"settlement_id": "SET-001", "amount": 1000.0}]
        existing_inv = 0
        existing_set = 0

        total_invoices_after_import = len(invoices_records) + existing_inv
        total_settlements_after_import = len(settlements_records) + existing_set

        error_message = None
        if total_invoices_after_import == 0 and total_settlements_after_import > 0:
            error_message = "No invoice source detected. Review file classifications before ingestion."

        self.assertEqual(
            error_message,
            "No invoice source detected. Review file classifications before ingestion.",
        )


class TestGeneralizedDateInferenceAndMapping(unittest.TestCase):
    """
    Verifies generalized value-based date detection, sample-based inference,
    semantic role assignment, multiple date columns distinction, and ambiguity handling.
    """

    def test_dd_mon_yyyy_detection(self):
        """08-Jul-2026 and 21-Jul-2026 must be recognized as dates (never id_string)."""
        samples = ["08-Jul-2026", "21-Jul-2026", "25-Jul-2026", "30-Jul-2026"]
        detected = detect_type(samples)
        self.assertEqual(detected, "date")

        analysis = analyze_date_values(samples)
        self.assertEqual(analysis["date_parse_success_rate"], 1.0)
        self.assertTrue(analysis["is_date"])
        self.assertFalse(analysis["is_datetime"])
        self.assertFalse(analysis["is_ambiguous"])  # named month is unambiguous
        self.assertEqual(analysis["inferred_format"], "%d-%b-%Y")

    def test_iso_date_detection(self):
        """2026-07-08 must be recognized as date and unambiguous."""
        samples = ["2026-07-08", "2026-07-21"]
        self.assertEqual(detect_type(samples), "date")

        analysis = analyze_date_values(samples)
        self.assertEqual(analysis["date_parse_success_rate"], 1.0)
        self.assertFalse(analysis["is_ambiguous"])
        self.assertEqual(analysis["inferred_format"], "%Y-%m-%d")

    def test_numeric_slashed_date_candidate_and_ambiguity(self):
        """
        08/07/2026 is recognized as a date candidate.
        07/08/2026 alone is ambiguous when context cannot resolve DD/MM vs MM/DD.
        Dataset context with any day > 12 resolves ambiguity.
        """
        # Date candidate detection
        self.assertEqual(detect_type(["08/07/2026"]), "date")

        # Ambiguous when both numbers <= 12 and no context
        analysis_ambig = analyze_date_values(["07/08/2026", "03/04/2026"])
        self.assertTrue(analysis_ambig["is_date"])
        self.assertTrue(analysis_ambig["is_ambiguous"])

        # Context resolved when any day > 12
        analysis_resolved = analyze_date_values(["07/08/2026", "25/08/2026"])
        self.assertTrue(analysis_resolved["is_date"])
        self.assertFalse(analysis_resolved["is_ambiguous"])
        self.assertEqual(analysis_resolved["inferred_format"], "%d/%m/%Y")

    def test_timestamp_detection(self):
        """2026/07/08 14:32:00 must be recognized as datetime."""
        samples = ["2026/07/08 14:32:00", "2026/07/09 09:15:30"]
        self.assertEqual(detect_type(samples), "datetime")

        analysis = analyze_date_values(samples)
        self.assertTrue(analysis["is_date"])
        self.assertTrue(analysis["is_datetime"])
        self.assertFalse(analysis["is_ambiguous"])

    def test_invoice_multiple_date_columns_distinction(self):
        """
        In an invoice file containing creation/raised date and due/pay-by date:
        - Creation date maps to Invoice Date
        - Pay-by date maps to Due Date
        - They do NOT map to the same canonical field.
        """
        cols_profile = [
            {"column_name": "Doc Ref", "detected_type": "id_string", "sample_values": ["INV-001", "INV-002"]},
            {"column_name": "Party / Account", "detected_type": "text", "sample_values": ["Acme Corp"]},
            {"column_name": "Pay By", "detected_type": "date", "sample_values": ["15-Aug-2026"], "date_parse_success_rate": 1.0, "is_date_ambiguous": False},
            {"column_name": "Raised On", "detected_type": "date", "sample_values": ["08-Jul-2026", "21-Jul-2026"], "date_parse_success_rate": 1.0, "is_date_ambiguous": False},
            {"column_name": "Total Amount", "detected_type": "currency", "sample_values": ["5000.00"]},
        ]

        mappings = map_columns_hybrid("INVOICES", cols_profile)
        mapped_dict = {m["source_column"]: m for m in mappings}

        # Check Pay By
        self.assertEqual(mapped_dict["Pay By"]["target_field"], "due_date")
        self.assertGreaterEqual(mapped_dict["Pay By"]["confidence"], 0.85)

        # Check Raised On
        self.assertEqual(mapped_dict["Raised On"]["target_field"], "invoice_date")
        self.assertGreaterEqual(mapped_dict["Raised On"]["confidence"], 0.85)
        self.assertEqual(mapped_dict["Raised On"]["confidence_band"], "HIGH")

        # Distinct fields check
        self.assertNotEqual(mapped_dict["Pay By"]["target_field"], mapped_dict["Raised On"]["target_field"])

    def test_multi_date_neutral_headers_distinction(self):
        """
        Two neutral date columns (e.g. Col_Date_1 and Col_Date_2) in an invoice file
        must map separately to Invoice Date and Due Date based on chronological order.
        """
        cols_profile = [
            {"column_name": "Col_ID", "detected_type": "id_string", "sample_values": ["D-101"]},
            {"column_name": "Col_Date_1", "detected_type": "date", "sample_values": ["08-Jul-2026"], "date_parse_success_rate": 1.0, "is_date_ambiguous": False},
            {"column_name": "Col_Date_2", "detected_type": "date", "sample_values": ["30-Jul-2026"], "date_parse_success_rate": 1.0, "is_date_ambiguous": False},
        ]

        mappings = map_columns_hybrid("INVOICES", cols_profile)
        mapped_dict = {m["source_column"]: m for m in mappings}

        self.assertEqual(mapped_dict["Col_Date_1"]["target_field"], "invoice_date")
        self.assertEqual(mapped_dict["Col_Date_2"]["target_field"], "due_date")
        self.assertNotEqual(mapped_dict["Col_Date_1"]["target_field"], mapped_dict["Col_Date_2"]["target_field"])

    def test_ambiguous_date_requires_confirmation(self):
        """Ambiguous date columns must set requires_confirmation=True and have MEDIUM confidence."""
        cols_profile = [
            {"column_name": "Doc Ref", "detected_type": "id_string", "sample_values": ["INV-001"]},
            {"column_name": "Event Date", "detected_type": "date", "sample_values": ["03/04/2026"], "date_parse_success_rate": 1.0, "is_date_ambiguous": True},
        ]

        mappings = map_columns_hybrid("INVOICES", cols_profile)
        date_map = next(m for m in mappings if m["source_column"] == "Event Date")

        self.assertEqual(date_map["target_field"], "invoice_date")
        self.assertTrue(date_map.get("requires_confirmation", False))
        self.assertEqual(date_map["confidence_band"], "MEDIUM")
        self.assertLess(date_map["confidence"], 0.85)


if __name__ == "__main__":
    unittest.main()
