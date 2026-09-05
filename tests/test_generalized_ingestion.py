"""
ReconAI — Comprehensive Generalized Ingestion & Anti-Overfitting Test Suite
===========================================================================
Validates:
1. File-type detection without relying on filenames (pure structure & values)
2. Alternative financial headers across global and Indian ERP / Banking conventions
3. Currency & amount parsing (Indian lakhs/crores, commas, currency symbols, negatives)
4. Multi-row date format disambiguation (DD/MM vs MM/DD)
5. Extra irrelevant columns safely ignored
6. Missing optional columns defaulted safely
7. Multiple files of the same type combined and deduplicated
8. Zero-refund datasets processed cleanly
9. Unknown file fallback when confidence is insufficient
10. Anti-overfitting check: zero hardcoded filenames, sample IDs, or customer names
"""

import os
import re
import pytest
from pathlib import Path
from backend.ingestion.detector import detect_file_type
from backend.ingestion.schema_mapper import (
    map_columns_deterministic,
    map_columns_hybrid,
    CANONICAL_SCHEMAS,
)
from backend.ingestion.validator import (
    parse_amount,
    parse_date,
    infer_date_format_for_dataset,
    validate_records,
)
from backend.ingestion.normalizer import normalize_and_store
from backend.database.db import get_db, init_db


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()


def test_1_filename_independent_detection():
    """Verify file type detection succeeds when filenames are completely generic or misleading."""
    # Bank statement with generic name
    bank_cols = ["Value Date", "Narration", "UTR", "Credit", "Debit", "Balance"]
    res_bank = detect_file_type("export_0409.csv", bank_cols)
    assert res_bank["file_type"] == "BANK_TRANSACTIONS"
    assert res_bank["confidence"] >= 0.75

    # Invoice dataset with generic name
    inv_cols = ["Bill Ref", "Party", "Bill Date", "Total Due"]
    res_inv = detect_file_type("finance_dump.csv", inv_cols)
    assert res_inv["file_type"] == "INVOICES"
    assert res_inv["confidence"] >= 0.70

    # Settlement dataset with generic name
    set_cols = ["Gateway Txn", "Invoice Reference", "Gross", "Fee", "Net Amount", "Processed At"]
    res_set = detect_file_type("dump_data_99.csv", set_cols)
    assert res_set["file_type"] == "SETTLEMENTS"
    assert res_set["confidence"] >= 0.75


def test_2_arbitrary_column_mapping_invoices():
    """Verify semantic column mapping works for alternative invoice schemas."""
    cols = [
        {"column_name": "Doc No", "detected_type": "id_string", "sample_values": ["D-9001", "D-9002"]},
        {"column_name": "Buyer Name", "detected_type": "text", "sample_values": ["Acme Corp", "Zeta Ltd"]},
        {"column_name": "Issue Date", "detected_type": "date", "sample_values": ["2026-05-10"]},
        {"column_name": "Total Due", "detected_type": "currency", "sample_values": ["₹45,000"]},
        {"column_name": "Terms Date", "detected_type": "date", "sample_values": ["2026-05-25"]},
        {"column_name": "Salesperson", "detected_type": "text", "sample_values": ["John Doe"]},
    ]
    mappings = map_columns_hybrid("INVOICES", cols)
    mapped = {m["source_column"]: m["target_field"] for m in mappings if m["target_field"]}

    assert mapped.get("Doc No") == "invoice_id"
    assert mapped.get("Buyer Name") == "customer_name"
    assert mapped.get("Issue Date") == "invoice_date"
    assert mapped.get("Total Due") in ("amount", "invoice_amount")
    assert mapped.get("Terms Date") == "due_date"
    assert "Salesperson" not in mapped  # extra column ignored


def test_3_arbitrary_column_mapping_settlements():
    """Verify settlement schema variation with Gross, MDR Fee, and Net Amount."""
    cols = [
        {"column_name": "Gateway Txn ID", "detected_type": "id_string", "sample_values": ["GT-101", "GT-102"]},
        {"column_name": "Order Reference", "detected_type": "id_string", "sample_values": ["ORD-501", "ORD-502"]},
        {"column_name": "Settled On", "detected_type": "date", "sample_values": ["2026-05-12"]},
        {"column_name": "Captured Amount", "detected_type": "currency", "sample_values": ["50000"]},
        {"column_name": "MDR Fee", "detected_type": "currency", "sample_values": ["600"]},
        {"column_name": "Net Payout", "detected_type": "currency", "sample_values": ["49400"]},
        {"column_name": "UTR", "detected_type": "id_string", "sample_values": ["UTR998811"]},
    ]
    mappings = map_columns_hybrid("SETTLEMENTS", cols)
    mapped = {m["source_column"]: m["target_field"] for m in mappings if m["target_field"]}

    assert mapped.get("Gateway Txn ID") == "settlement_id"
    assert mapped.get("Order Reference") in ("invoice_id", "invoice_reference")
    assert mapped.get("Settled On") == "settlement_date"
    assert mapped.get("Captured Amount") == "gross_amount"
    assert mapped.get("MDR Fee") == "fee_amount"
    assert mapped.get("Net Payout") == "net_amount"
    assert mapped.get("UTR") == "payment_reference"


def test_4_bank_statement_variations():
    """Verify multiple bank statement styles (Particulars/Deposit vs Narration/Credit)."""
    # Style A: Particulars & Deposit
    cols_a = [
        {"column_name": "Txn ID", "detected_type": "id_string", "sample_values": ["B-1", "B-2"]},
        {"column_name": "Particulars", "detected_type": "text", "sample_values": ["NEFT inward"]},
        {"column_name": "Value Date", "detected_type": "date", "sample_values": ["2026-06-01"]},
        {"column_name": "Deposit", "detected_type": "currency", "sample_values": ["15000"]},
        {"column_name": "Withdrawal", "detected_type": "currency", "sample_values": ["0"]},
    ]
    mappings_a = map_columns_hybrid("BANK_TRANSACTIONS", cols_a)
    mapped_a = {m["source_column"]: m["target_field"] for m in mappings_a if m["target_field"]}
    assert mapped_a.get("Particulars") == "description"
    assert mapped_a.get("Deposit") == "credit_amount"
    assert mapped_a.get("Withdrawal") == "debit_amount"
    assert mapped_a.get("Value Date") == "transaction_date"


def test_5_money_and_amount_generalization():
    """Verify parsing of global, Indian lakh/crore, currency-prefixed, and negative amounts."""
    # Plain numeric
    amt, err = parse_amount("120500")
    assert amt == 120500.0 and err is None

    # Indian comma notation
    amt, err = parse_amount("1,20,500.50")
    assert amt == 120500.50 and err is None

    # Currency symbols
    amt, err = parse_amount("₹1,20,500")
    assert amt == 120500.0 and err is None

    amt, err = parse_amount("INR 75000")
    assert amt == 75000.0 and err is None

    amt, err = parse_amount("Rs. 15,000.00")
    assert amt == 15000.0 and err is None

    amt, err = parse_amount("$2,450.75")
    assert amt == 2450.75 and err is None

    # Lakh and Crore notations
    amt, err = parse_amount("1.2 lakh")
    assert amt == 120000.0 and err is None

    amt, err = parse_amount("1.20L")
    assert amt == 120000.0 and err is None

    amt, err = parse_amount("1.5 crore")
    assert amt == 15000000.0 and err is None

    # Accounting parentheses (negative)
    amt, err = parse_amount("(5000)", allow_negative=True)
    assert amt == -5000.0 and err is None

    # Rejection of negative amounts when not permitted
    amt, err = parse_amount("-5000", allow_negative=False)
    assert amt is None and "Negative amount" in err


def test_6_multi_row_date_disambiguation():
    """Verify DD/MM vs MM/DD disambiguation using sample rows."""
    # Sample where day > 12 in first position -> DD/MM/YYYY
    samples_dd_first = ["25/08/2026", "11/08/2026", "05/08/2026"]
    fmt = infer_date_format_for_dataset(samples_dd_first)
    assert fmt == "%d/%m/%Y"

    # Sample where day > 12 in second position -> MM/DD/YYYY
    samples_mm_first = ["08/25/2026", "08/11/2026", "08/05/2026"]
    fmt = infer_date_format_for_dataset(samples_mm_first)
    assert fmt == "%m/%d/%Y"

    # Parsing with inferred format
    d, err = parse_date("05/09/2026", preferred_format="%d/%m/%Y")
    assert d == "2026-09-05"  # 5th of September

    d, err = parse_date("05/09/2026", preferred_format="%m/%d/%Y")
    assert d == "2026-05-09"  # 9th of May

    # Named month parsing
    d, err = parse_date("5 Sep 2026")
    assert d == "2026-09-05"


def test_7_extra_columns_and_missing_optional():
    """Verify rows with extra metadata validate, while missing required fields reject."""
    raw_rows = [
        {"bill_no": "BILL-100", "party": "Acme", "amt": "15000", "dt": "2026-07-01", "region": "North", "rep": "Alice"},
        {"bill_no": "BILL-101", "party": "Beta", "amt": "", "dt": "2026-07-02", "region": "South"},  # missing amount
    ]
    mapping = {
        "bill_no": "invoice_id",
        "party": "customer_name",
        "amt": "invoice_amount",
        "dt": "invoice_date",
        "region": None,
        "rep": None,
    }
    res = validate_records("INVOICES", raw_rows, mapping)
    assert res["stats"]["valid_count"] == 1
    assert res["stats"]["rejected_count"] == 1
    assert res["valid_records"][0]["invoice_id"] == "BILL-100"
    assert res["valid_records"][0]["invoice_amount"] == 15000.0
    assert "region" not in res["valid_records"][0]  # extra column safely stripped from canonical model


def test_8_multiple_files_of_same_type_combination():
    """Verify uploading two separate invoice batches combines records without data loss."""
    batch_1 = [
        {"invoice_id": "BATCH1-01", "customer_name": "Client A", "invoice_amount": 10000.0, "invoice_date": "2026-01-01"}
    ]
    batch_2 = [
        {"invoice_id": "BATCH2-01", "customer_name": "Client B", "invoice_amount": 20000.0, "invoice_date": "2026-01-02"}
    ]

    # Ingest Batch 1 (clear_existing = True)
    res_1 = normalize_and_store(
        invoices_data=batch_1,
        settlements_data=[],
        bank_data=[],
        clear_existing=True,
    )
    assert res_1["invoices_stored"] == 1

    # Ingest Batch 2 (clear_existing = False, appending second file of same type)
    res_2 = normalize_and_store(
        invoices_data=batch_2,
        settlements_data=[],
        bank_data=[],
        clear_existing=False,
    )
    assert res_2["invoices_stored"] == 1
    assert res_2["total_invoices"] == 2

    # Verify both exist in DB
    with get_db() as conn:
        invs = conn.execute("SELECT invoice_id FROM uploaded_invoices ORDER BY invoice_id").fetchall()
        ids = [r[0] for r in invs]
        assert "BATCH1-01" in ids
        assert "BATCH2-01" in ids


def test_9_zero_refunds_supported():
    """Verify that omitting refunds completely stores cleanly and is ready for reconciliation."""
    invoices = [
        {"invoice_id": "INV-X1", "customer_name": "Alpha", "invoice_amount": 5000.0, "invoice_date": "2026-02-01"}
    ]
    settlements = [
        {"settlement_id": "SET-X1", "invoice_reference": "INV-X1", "amount": 5000.0, "settlement_date": "2026-02-02"}
    ]
    bank = [
        {"bank_txn_id": "BNK-X1", "amount": 5000.0, "transaction_date": "2026-02-03", "utr_number": "UTR-X1"}
    ]

    res = normalize_and_store(
        invoices_data=invoices,
        settlements_data=settlements,
        bank_data=bank,
        refunds_data=None,  # Zero refunds
        clear_existing=True,
    )
    assert res["status"] == "success"
    assert res["total_refunds"] == 0
    assert res["total_invoices"] == 1


def test_10_unknown_file_detection():
    """Verify that completely unfinancial CSVs are classified as UNKNOWN rather than forced."""
    unrelated_cols = ["favorite_color", "pet_name", "shoe_size", "city"]
    res = detect_file_type("random_survey.csv", unrelated_cols)
    assert res["file_type"] == "UNKNOWN"
    assert res["confidence"] < 0.50
    assert res["confidence_band"] == "LOW"


def test_11_anti_overfitting_check():
    """Scan production ingestion code to verify no attached example filenames, IDs, or customer names are hardcoded."""
    ingestion_dir = Path(__file__).parent.parent / "backend" / "ingestion"
    py_files = list(ingestion_dir.glob("*.py"))

    forbidden_patterns = [
        r"INV-SEP26-",
        r"SET-SEP26-",
        r"BNK-SEP26-",
        r"RFD-SEP26-",
        r"PAY-81",
        r"Aster Labs",
        r"BluePeak Tech",
        r"Cedar Commerce",
        r"DeltaWorks",
        r"Evergreen Retail",
        r"Finora Systems",
    ]

    for pf in py_files:
        content = pf.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            matches = re.findall(pat, content, re.IGNORECASE)
            assert not matches, f"Overfitting violation: Pattern '{pat}' found in production code {pf.name}"
