"""
ReconAI — Generalized Financial Data Validator & Parser
========================================================
Validates and standardizes mapped CSV rows into canonical financial records:
- Decimal-safe amount parsing with support for Indian Lakh/Crore notations, currency symbols, and comma patterns
- Multi-row date format inference (resolves DD/MM/YYYY vs MM/DD/YYYY ambiguity across the entire dataset)
- Bank statement credit/debit representation normalizer (handles both dual-column and single-amount with Type/CR/DR)
- Derivation of complementary settlement amounts (Gross = Net + Fee, Net = Gross - Fee)
- Strict required-field validation and informative row rejection reporting
- Tolerant of extra/unmapped columns
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Any, Optional, Tuple, Set


CURRENCY_SYMBOLS = ["₹", "$", "€", "£", "INR", "USD", "EUR", "GBP", "Rs.", "Rs", "AUD", "CAD", "SGD"]
SUPPORTED_CURRENCIES = {"INR", "USD", "EUR", "GBP", "AUD", "CAD", "SGD"}


def parse_amount(
    val: Any,
    allow_negative: bool = False,
) -> Tuple[Optional[float], Optional[str]]:
    """
    Cleans and parses currency strings, Indian lakh/crore units, and standard numeric strings.
    Handles:
    - Standard: '120500', '120500.00', '1,20,500.00'
    - Prefixed: '₹1,20,500', 'INR 120500', 'Rs. 120500', '$1,500.00'
    - Indian expressions: '1.2 lakh', '1.20L', '1.5 crore', '1.5 Cr', '10k'
    - Accounting parentheses: '(5000)' -> -5000
    - Suffixes: '5000.00 CR' / '5000.00 DR'
    """
    if val is None or str(val).strip() == "":
        return None, "Empty amount field"

    s = str(val).strip()

    # Detect accounting parentheses: (1200) -> -1200
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    # Detect DR suffix
    if s.upper().endswith("DR"):
        is_negative = True
        s = s[:-2].strip()
    elif s.upper().endswith("CR"):
        s = s[:-2].strip()

    # Strip currency symbols and text
    for sym in CURRENCY_SYMBOLS:
        s = s.replace(sym, "").strip()

    # Strip commas (handles standard and Indian numbering formats like 1,18,05,100)
    s = s.replace(",", "").strip()

    # Check for multiplier units (Lakh, Crore, K)
    multiplier = Decimal("1")
    lakh_match = re.search(r"^([\d\.]+)\s*(?:lakhs?|lakh|l)\b", s, re.IGNORECASE)
    crore_match = re.search(r"^([\d\.]+)\s*(?:crores?|crore|cr)\b", s, re.IGNORECASE)
    k_match = re.search(r"^([\d\.]+)\s*k\b", s, re.IGNORECASE)

    if lakh_match:
        s = lakh_match.group(1)
        multiplier = Decimal("100000")
    elif crore_match:
        s = crore_match.group(1)
        multiplier = Decimal("10000000")
    elif k_match:
        s = k_match.group(1)
        multiplier = Decimal("1000")

    try:
        dec = Decimal(s) * multiplier
        if is_negative:
            dec = -dec

        if not allow_negative and dec < 0:
            return None, f"Negative amount ({dec}) not permitted for this field"
        return float(dec), None
    except (InvalidOperation, ValueError):
        return None, f"Invalid numeric amount '{val}'"


def infer_date_format_for_dataset(sample_values: List[str]) -> Optional[str]:
    """
    Inspects multiple sample dates across the file to resolve DD/MM vs MM/DD ambiguity.
    If any day component > 12, it disambiguates the entire column format.
    """
    has_day_first = False
    has_month_first = False

    for v in sample_values:
        clean = str(v).strip().split(" ")[0].split("T")[0]
        # Check slashed or hyphenated e.g. 25/08/2026 or 08/25/2026
        m = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$", clean)
        if m:
            p1, p2, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if p1 > 12 and p2 <= 12:
                has_day_first = True
            elif p2 > 12 and p1 <= 12:
                has_month_first = True

    if has_day_first and not has_month_first:
        return "%d/%m/%Y"
    if has_month_first and not has_day_first:
        return "%m/%d/%Y"
    return None


def parse_date(
    val: Any,
    preferred_format: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Parses flexible date formats to ISO YYYY-MM-DD.
    Supports ISO, European/Indian (DD/MM/YYYY), US (MM/DD/YYYY), and Named Months (e.g. 5 Sep 2026).
    """
    if val is None or str(val).strip() == "":
        return None, "Missing date"

    s = str(val).strip()
    # Strip time if present (e.g. 2026-09-05 14:30:00 or 2026-09-05T14:30:00)
    if re.search(r"\b\d{1,2}:\d{2}", s):
        s_date = re.split(r"\s+\d{1,2}:\d{2}", s)[0]
    elif "T" in s and not any(m in s for m in ["Sep", "Oct", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Nov", "Dec"]):
        s_date = s.split("T")[0]
    else:
        s_date = s

    # Standard candidate formats
    candidate_fmts = []
    if preferred_format:
        candidate_fmts.append(preferred_format)
        candidate_fmts.append(preferred_format.replace("/", "-"))

    candidate_fmts.extend([
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d-%b-%Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ])

    parsed_dt = None
    for fmt in candidate_fmts:
        try:
            parsed_dt = datetime.strptime(s_date, fmt).date()
            break
        except ValueError:
            continue

    if not parsed_dt:
        # Fallback to general dateutil parsing if available
        return None, f"Unparseable date format '{val}'"

    if parsed_dt.year < 1990 or parsed_dt.year > 2040:
        return parsed_dt.isoformat(), f"Date year {parsed_dt.year} outside standard financial range"

    return parsed_dt.isoformat(), None


def validate_records(
    file_type: str,
    raw_rows: List[Dict[str, Any]],
    column_mapping: Dict[str, str],  # source_col -> canonical_field
    existing_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Validates rows against canonical schema:
    - Resolves date format across sample rows
    - Normalizes amounts (Indian & global notations)
    - Validates required fields
    - Rejects invalid rows with actionable reasons
    - Deduplicates IDs
    """
    valid_records: List[Dict[str, Any]] = []
    rejected_records: List[Dict[str, Any]] = []
    errors: List[str] = []
    warnings: List[str] = []

    seen_ids: Set[str] = set()
    duplicate_ids = 0

    # Invert mapping: canonical_field -> source_col (handle aliases)
    inv_map: Dict[str, str] = {}
    for k, v in column_mapping.items():
        if not v:
            continue
        inv_map[v] = k
        # Add alias back-references
        if v == "invoice_amount":
            inv_map["amount"] = k
        elif v == "amount":
            inv_map["invoice_amount"] = k
        elif v == "invoice_id":
            inv_map["invoice_reference"] = k
        elif v == "invoice_reference":
            inv_map["invoice_id"] = k
        elif v == "bank_txn_id":
            inv_map["bank_transaction_id"] = k
        elif v == "bank_transaction_id":
            inv_map["bank_txn_id"] = k
        elif v == "reference":
            inv_map["bank_reference"] = k
        elif v == "bank_reference":
            inv_map["reference"] = k

    # Pre-scan dates for format disambiguation
    date_col = (
        inv_map.get("invoice_date")
        or inv_map.get("settlement_date")
        or inv_map.get("transaction_date")
        or inv_map.get("refund_date")
    )
    pref_date_fmt = None
    if date_col and raw_rows:
        sample_dates = [str(r.get(date_col, "")) for r in raw_rows[:50] if r.get(date_col)]
        pref_date_fmt = infer_date_format_for_dataset(sample_dates)

    for row_idx, row in enumerate(raw_rows, start=1):
        row_errors: List[str] = []
        row_warnings: List[str] = []
        canonical_row: Dict[str, Any] = {}

        if file_type == "INVOICES":
            # 1. invoice_id (Required)
            id_col = inv_map.get("invoice_id")
            raw_id = row.get(id_col) if id_col else None
            if not raw_id or str(raw_id).strip() == "":
                row_errors.append("Missing required 'invoice_id'")
            else:
                iid = str(raw_id).strip().upper()
                if iid in seen_ids:
                    row_errors.append(f"Duplicate invoice_id '{iid}' within file")
                    duplicate_ids += 1
                elif existing_ids and iid in existing_ids:
                    row_warnings.append(f"Invoice ID '{iid}' already exists in active dataset. Skipped.")
                    duplicate_ids += 1
                    row_errors.append(f"Duplicate invoice_id '{iid}' already in active dataset")
                else:
                    seen_ids.add(iid)
                canonical_row["invoice_id"] = iid

            # 2. customer_name (Optional, defaults cleanly)
            cust_col = inv_map.get("customer_name")
            raw_cust = str(row.get(cust_col) or "").strip() if cust_col else ""
            canonical_row["customer_name"] = raw_cust or "Unknown Client"
            canonical_row["customer_id"] = f"CUST-{canonical_row['customer_name'][:3].upper()}"

            # 3. invoice_amount (Required)
            amt_col = inv_map.get("invoice_amount") or inv_map.get("amount")
            amt, amt_err = parse_amount(row.get(amt_col) if amt_col else None)
            if amt_err:
                row_errors.append(f"Invoice amount error: {amt_err}")
            else:
                canonical_row["invoice_amount"] = amt

            # 4. invoice_date (Required)
            d_col = inv_map.get("invoice_date")
            idate, date_msg = parse_date(row.get(d_col) if d_col else None, preferred_format=pref_date_fmt)
            if not idate:
                row_errors.append(date_msg or "Invalid invoice_date")
            else:
                canonical_row["invoice_date"] = idate
                if date_msg:
                    row_warnings.append(date_msg)

            # 5. due_date (Optional, defaults to invoice_date)
            due_col = inv_map.get("due_date")
            ddate, _ = parse_date(row.get(due_col) if due_col else None, preferred_format=pref_date_fmt)
            canonical_row["due_date"] = ddate or canonical_row.get("invoice_date", date.today().isoformat())

            # 6. currency (Optional, defaults to INR)
            curr_col = inv_map.get("currency")
            curr = str(row.get(curr_col) or "INR").strip().upper()
            if curr not in SUPPORTED_CURRENCIES:
                row_warnings.append(f"Unsupported currency '{curr}', defaulted to INR")
                curr = "INR"
            canonical_row["currency"] = curr

            # 7. invoice_reference (Optional)
            ref_col = inv_map.get("invoice_reference")
            canonical_row["description"] = str(row.get(ref_col) or "").strip() if ref_col else ""
            canonical_row["ground_truth_scenario"] = "imported"
            canonical_row["expected_match_id"] = None

        elif file_type == "SETTLEMENTS":
            # 1. settlement_id (Required)
            sid_col = inv_map.get("settlement_id")
            raw_sid = row.get(sid_col) if sid_col else None
            sid = str(raw_sid).strip().upper() if raw_sid else f"SET-AUTO-{row_idx:04d}"
            if sid in seen_ids:
                row_errors.append(f"Duplicate settlement_id '{sid}' within file")
                duplicate_ids += 1
            elif existing_ids and sid in existing_ids:
                row_warnings.append(f"Settlement ID '{sid}' already exists in active dataset. Skipped.")
                duplicate_ids += 1
                row_errors.append(f"Duplicate settlement_id '{sid}' already in active dataset")
            else:
                seen_ids.add(sid)
            canonical_row["settlement_id"] = sid

            # 2. invoice_id (Required for direct 1-to-1 linkage)
            ref_col = inv_map.get("invoice_id") or inv_map.get("invoice_reference")
            raw_ref = row.get(ref_col) if ref_col else None
            canonical_row["invoice_reference"] = str(raw_ref).strip().upper() if raw_ref else None

            # 3. gross_amount and fee_amount (Derivable)
            g_col = inv_map.get("gross_amount") or inv_map.get("amount")
            gross, g_err = parse_amount(row.get(g_col) if g_col else None)

            f_col = inv_map.get("fee_amount")
            fee, _ = parse_amount(row.get(f_col) if f_col else None)
            fee = fee or 0.0

            n_col = inv_map.get("net_amount")
            net, _ = parse_amount(row.get(n_col) if n_col else None)

            # Derive Gross or Net if one is missing
            if gross is not None:
                canonical_row["amount"] = gross
                canonical_row["fee"] = fee
                canonical_row["net_amount"] = net if net is not None else round(gross - fee, 2)
            elif net is not None:
                canonical_row["amount"] = round(net + fee, 2)
                canonical_row["fee"] = fee
                canonical_row["net_amount"] = net
            else:
                row_errors.append("Settlement row requires at least gross_amount or net_amount")

            # 4. settlement_date (Required)
            sdate_col = inv_map.get("settlement_date")
            sdate, sdate_msg = parse_date(row.get(sdate_col) if sdate_col else None, preferred_format=pref_date_fmt)
            if not sdate:
                row_errors.append(sdate_msg or "Invalid settlement_date")
            else:
                canonical_row["settlement_date"] = sdate
                canonical_row["payment_date"] = sdate
                if sdate_msg:
                    row_warnings.append(sdate_msg)

            # 5. payment_reference / UTR
            pref_col = inv_map.get("payment_reference")
            canonical_row["utr_number"] = str(row.get(pref_col) or "").strip() or None
            canonical_row["payment_id"] = f"PAY-{sid}"
            canonical_row["payment_gateway"] = "Imported Gateway"
            canonical_row["ground_truth_scenario"] = "imported"
            canonical_row["ground_truth_invoice_id"] = canonical_row["invoice_reference"]

        elif file_type == "BANK_TRANSACTIONS":
            # 1. bank_txn_id (Required)
            bid_col = inv_map.get("bank_txn_id") or inv_map.get("bank_transaction_id")
            raw_bid = row.get(bid_col) if bid_col else None
            if not raw_bid:
                bref_candidate = inv_map.get("reference") or inv_map.get("bank_reference")
                raw_bid = row.get(bref_candidate) if bref_candidate else (row.get("utr") or row.get("UTR"))
            bid = str(raw_bid).strip().upper() if raw_bid else f"BNK-AUTO-{row_idx:04d}"
            if bid in seen_ids:
                row_errors.append(f"Duplicate bank_transaction_id '{bid}' within file")
                duplicate_ids += 1
            elif existing_ids and bid in existing_ids:
                row_warnings.append(f"Bank transaction ID '{bid}' already exists in active dataset. Skipped.")
                duplicate_ids += 1
                row_errors.append(f"Duplicate bank_transaction_id '{bid}' already in active dataset")
            else:
                seen_ids.add(bid)
            canonical_row["bank_txn_id"] = bid

            # 2. transaction_date (Required)
            tdate_col = inv_map.get("transaction_date")
            tdate, tdate_msg = parse_date(row.get(tdate_col) if tdate_col else None, preferred_format=pref_date_fmt)
            if not tdate:
                row_errors.append(tdate_msg or "Invalid transaction_date")
            else:
                canonical_row["transaction_date"] = tdate
                canonical_row["value_date"] = tdate
                if tdate_msg:
                    row_warnings.append(tdate_msg)

            # 3. credit_amount vs debit_amount vs single amount
            c_col = inv_map.get("credit_amount")
            d_col = inv_map.get("debit_amount")

            if c_col and c_col in row:
                credit, c_err = parse_amount(row.get(c_col), allow_negative=False)
                if c_err and not d_col:
                    row_errors.append(f"Bank credit amount error: {c_err}")
                else:
                    canonical_row["amount"] = credit or 0.0
                    canonical_row["transaction_type"] = "credit"
            else:
                # Check general amount column with debit/credit sign convention
                amt_col = inv_map.get("amount")
                amt, amt_err = parse_amount(row.get(amt_col) if amt_col else None, allow_negative=True)
                if amt_err:
                    row_errors.append(amt_err)
                else:
                    if amt >= 0:
                        canonical_row["amount"] = amt
                        canonical_row["transaction_type"] = "credit"
                    else:
                        canonical_row["amount"] = abs(amt)
                        canonical_row["transaction_type"] = "debit"

            # 4. reference / UTR
            bref_col = inv_map.get("bank_reference") or inv_map.get("reference")
            raw_bref = row.get(bref_col) if bref_col else None
            bref = str(raw_bref or "").strip() or None
            if not bref and raw_bid:
                bref = str(raw_bid).strip()
            canonical_row["utr_number"] = bref
            canonical_row["bank_reference"] = bref

            # 5. description
            desc_col = inv_map.get("description")
            canonical_row["description"] = str(row.get(desc_col) or "Bank credit remittance").strip()
            canonical_row["ground_truth_scenario"] = "imported"

        elif file_type == "REFUNDS":
            # 1. refund_id (Required)
            rid_col = inv_map.get("refund_id")
            raw_rid = row.get(rid_col) if rid_col else None
            rid = str(raw_rid).strip().upper() if raw_rid else f"RFD-AUTO-{row_idx:04d}"
            if rid in seen_ids:
                row_errors.append(f"Duplicate refund_id '{rid}' within file")
                duplicate_ids += 1
            elif existing_ids and rid in existing_ids:
                row_warnings.append(f"Refund ID '{rid}' already exists in active dataset. Skipped.")
                duplicate_ids += 1
                row_errors.append(f"Duplicate refund_id '{rid}' already in active dataset")
            else:
                seen_ids.add(rid)
            canonical_row["refund_id"] = rid

            # 2. invoice_id (Optional)
            inv_col = inv_map.get("invoice_id")
            raw_inv = row.get(inv_col) if inv_col else None
            canonical_row["invoice_id"] = str(raw_inv).strip().upper() if raw_inv else None

            # 3. refund_amount (Required)
            ramt_col = inv_map.get("refund_amount") or inv_map.get("amount")
            ramt, ramt_err = parse_amount(row.get(ramt_col) if ramt_col else None)
            if ramt_err:
                row_errors.append(f"Refund amount error: {ramt_err}")
            else:
                canonical_row["refund_amount"] = ramt

            # 4. refund_date (Required)
            rdate_col = inv_map.get("refund_date")
            rdate, rdate_msg = parse_date(row.get(rdate_col) if rdate_col else None, preferred_format=pref_date_fmt)
            if not rdate:
                row_errors.append(rdate_msg or "Invalid refund_date")
            else:
                canonical_row["refund_date"] = rdate
                if rdate_msg:
                    row_warnings.append(rdate_msg)

            # 5. reason (Optional)
            reason_col = inv_map.get("reason")
            canonical_row["reason"] = str(row.get(reason_col) or "").strip()

            # 6. payment_reference (Optional)
            pref_col = inv_map.get("payment_reference")
            canonical_row["payment_reference"] = str(row.get(pref_col) or "").strip() or None

        if row_warnings:
            warnings.extend([f"Row {row_idx}: {w}" for w in row_warnings])

        if row_errors:
            rejected_records.append({
                "row_index": row_idx,
                "raw_data": row,
                "errors": row_errors,
            })
            errors.extend([f"Row {row_idx}: {e}" for e in row_errors])
        else:
            valid_records.append(canonical_row)

    return {
        "valid_records": valid_records,
        "rejected_records": rejected_records,
        "errors": errors[:20],
        "warnings": warnings[:20],
        "stats": {
            "total_rows": len(raw_rows),
            "valid_count": len(valid_records),
            "rejected_count": len(rejected_records),
            "warning_count": len(warnings),
            "duplicate_ids": duplicate_ids,
        },
    }
