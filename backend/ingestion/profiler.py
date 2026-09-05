"""
ReconAI — CSV Profiler
======================
Inspects raw financial CSV files and computes schema profiles:
- row count, column names
- sample non-empty values
- null percentages
- detected inferred data types
- duplicate counts
"""

from __future__ import annotations

import csv
import io
import re
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal


MONTH_MAP: Dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

CURRENCY_SYMBOLS = ["₹", "$", "€", "£", "INR", "USD", "EUR", "GBP", "Rs.", "Rs"]


def _clean_string(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def parse_single_date(val: Any) -> Optional[Dict[str, Any]]:
    """
    Safely parses a single value into date/datetime attributes.
    Supports DD-Mon-YYYY, DD-Month-YYYY, YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY,
    DD-MM-YYYY, YYYY/MM/DD, and timestamps.
    Returns None if the value cannot be parsed as a date.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    # Check for time component (e.g. 14:32:00 or 14:32 or 2:30 PM or T14:32:00)
    has_time = bool(re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:\s*[AaPp][Mm])?", s))

    # Strip time part for date structural analysis
    date_part = re.sub(r"[\sT]+\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:\s*[AaPp][Mm])?.*$", "", s).strip()
    if not date_part:
        return None

    # 1. DD-Mon-YYYY or DD-Month-YYYY (e.g. 08-Jul-2026, 21-July-2026, 08/Jul/2026, 08 Jul 2026)
    m_named1 = re.match(r"^(\d{1,2})[\s\-\/]([A-Za-z]{3,9})[\s\-\/](\d{2,4})$", date_part)
    if m_named1:
        day = int(m_named1.group(1))
        mon_str = m_named1.group(2).lower()
        yr = int(m_named1.group(3))
        if (mon_str in MONTH_MAP or mon_str[:3] in MONTH_MAP) and 1 <= day <= 31:
            m_num = MONTH_MAP.get(mon_str, MONTH_MAP.get(mon_str[:3]))
            fmt = "%d-%b-%Y" if "-" in date_part else ("%d/%b/%Y" if "/" in date_part else "%d %b %Y")
            return {
                "is_date": True,
                "is_datetime": has_time,
                "is_ambiguous": False,
                "day_first": True,
                "month_first": False,
                "format": fmt,
                "day": day,
                "month": m_num,
                "year": yr,
            }

    # 1b. Mon-DD-YYYY or Month DD, YYYY (e.g. Jul-08-2026, July 08, 2026)
    m_named2 = re.match(r"^([A-Za-z]{3,9})[\s\-\/](\d{1,2})(?:,)?[\s\-\/](\d{2,4})$", date_part)
    if m_named2:
        mon_str = m_named2.group(1).lower()
        day = int(m_named2.group(2))
        yr = int(m_named2.group(3))
        if (mon_str in MONTH_MAP or mon_str[:3] in MONTH_MAP) and 1 <= day <= 31:
            m_num = MONTH_MAP.get(mon_str, MONTH_MAP.get(mon_str[:3]))
            return {
                "is_date": True,
                "is_datetime": has_time,
                "is_ambiguous": False,
                "day_first": False,
                "month_first": True,
                "format": "%b %d, %Y",
                "day": day,
                "month": m_num,
                "year": yr,
            }

    # 2. ISO format: YYYY-MM-DD or YYYY/MM/DD
    m_iso = re.match(r"^(\d{4})[\-\/](\d{1,2})[\-\/](\d{1,2})$", date_part)
    if m_iso:
        yr = int(m_iso.group(1))
        mon = int(m_iso.group(2))
        day = int(m_iso.group(3))
        if 1 <= mon <= 12 and 1 <= day <= 31 and 1900 <= yr <= 2100:
            fmt = "%Y-%m-%d" if "-" in date_part else "%Y/%m/%d"
            return {
                "is_date": True,
                "is_datetime": has_time,
                "is_ambiguous": False,
                "day_first": False,
                "month_first": False,
                "format": fmt,
                "day": day,
                "month": mon,
                "year": yr,
            }

    # 3. Numeric slashed or hyphenated: DD/MM/YYYY, MM/DD/YYYY, DD-MM-YYYY, etc.
    m_num = re.match(r"^(\d{1,2})[\-\/](\d{1,2})[\-\/](\d{2,4})$", date_part)
    if m_num:
        p1 = int(m_num.group(1))
        p2 = int(m_num.group(2))
        yr = int(m_num.group(3))
        if 1900 <= yr <= 2100 or yr < 100:
            valid_p1_day = (1 <= p1 <= 31 and 1 <= p2 <= 12)
            valid_p2_day = (1 <= p2 <= 31 and 1 <= p1 <= 12)
            if valid_p1_day or valid_p2_day:
                day_first = (p1 > 12 and p2 <= 12)
                month_first = (p2 > 12 and p1 <= 12)
                ambiguous = (p1 <= 12 and p2 <= 12)
                delim = "-" if "-" in date_part else "/"
                fmt = f"%d{delim}%m{delim}%Y" if day_first else (f"%m{delim}%d{delim}%Y" if month_first else f"%d{delim}%m{delim}%Y")
                return {
                    "is_date": True,
                    "is_datetime": has_time,
                    "is_ambiguous": ambiguous,
                    "day_first": day_first,
                    "month_first": month_first,
                    "p1": p1,
                    "p2": p2,
                    "year": yr,
                    "format": fmt,
                }

    return None


def analyze_date_values(sample_values: List[str]) -> Dict[str, Any]:
    """
    Performs multi-sample date inference across non-empty values:
    - Calculates date_parse_success_rate
    - Disambiguates DD/MM vs MM/DD using cross-row dataset context (any day > 12)
    - Determines if values contain timestamps (datetime vs date)
    """
    non_empty = [str(v).strip() for v in sample_values if str(v).strip()]
    if not non_empty:
        return {
            "date_parse_success_rate": 0.0,
            "is_date": False,
            "is_datetime": False,
            "is_ambiguous": False,
            "inferred_format": None,
            "parsed_count": 0,
            "total_count": 0,
        }

    parsed = []
    datetime_count = 0
    has_day_first = False
    has_month_first = False
    has_unambiguous_format = False
    formats_seen = []

    for v in non_empty:
        res = parse_single_date(v)
        if res:
            parsed.append(res)
            if res.get("is_datetime"):
                datetime_count += 1
            if not res.get("is_ambiguous"):
                has_unambiguous_format = True
            if res.get("day_first"):
                has_day_first = True
            if res.get("month_first"):
                has_month_first = True
            if res.get("format") and res.get("format") not in formats_seen:
                formats_seen.append(res.get("format"))

    success_rate = round(len(parsed) / len(non_empty), 2)
    is_date = success_rate >= 0.6
    is_datetime = is_date and (datetime_count / len(parsed) >= 0.5) if parsed else False

    # Ambiguity logic:
    # 1. If column has unambiguous format (e.g. named month '08-Jul-2026' or ISO '2026-07-08') -> unambiguous!
    # 2. If cross-sample evidence has day > 12 -> resolved!
    # 3. If all samples are ambiguous (both parts <= 12) -> ambiguous!
    if has_unambiguous_format:
        is_ambiguous = False
    elif has_day_first and not has_month_first:
        is_ambiguous = False
    elif has_month_first and not has_day_first:
        is_ambiguous = False
    else:
        # All numeric samples had both numbers <= 12, cannot be reliably inferred from dataset
        is_ambiguous = bool(is_date and parsed and all(p.get("is_ambiguous", False) for p in parsed))

    inferred_fmt = formats_seen[0] if formats_seen else None
    if not has_unambiguous_format:
        if has_day_first:
            inferred_fmt = "%d/%m/%Y"
        elif has_month_first:
            inferred_fmt = "%m/%d/%Y"

    return {
        "date_parse_success_rate": success_rate,
        "is_date": is_date,
        "is_datetime": is_datetime,
        "is_ambiguous": is_ambiguous,
        "inferred_format": inferred_fmt,
        "parsed_count": len(parsed),
        "total_count": len(non_empty),
    }


def detect_type(sample_values: List[str]) -> str:
    """Infer semantic/data type from non-empty sample values."""
    if not sample_values:
        return "text"

    clean_samples = [str(v).strip() for v in sample_values if str(v).strip()]
    if not clean_samples:
        return "text"

    # Step 1: Value-based date & timestamp analysis
    date_analysis = analyze_date_values(clean_samples)
    if date_analysis["date_parse_success_rate"] >= 0.6:
        return "datetime" if date_analysis["is_datetime"] else "date"

    # Step 2: Currency & numeric analysis
    num_matches = 0
    curr_matches = 0
    for clean in clean_samples:
        has_curr = any(c in clean for c in CURRENCY_SYMBOLS)
        num_part = clean
        for c in CURRENCY_SYMBOLS:
            num_part = num_part.replace(c, "").strip()
        num_part = num_part.replace(",", "")

        try:
            float(num_part)
            if has_curr:
                curr_matches += 1
            else:
                num_matches += 1
        except ValueError:
            pass

    total = len(clean_samples)
    if (curr_matches + num_matches) / total >= 0.6:
        return "currency" if curr_matches > 0 else "number"

    # Step 3: Identifier pattern (e.g. INV-..., SET-..., alphanumeric codes)
    # Exclude strings that parse as dates so date strings never get misclassified as ID
    id_matches = 0
    for clean in clean_samples:
        if re.match(r"^[A-Za-z0-9_\-\./]{4,30}$", clean) and any(c.isdigit() for c in clean) and any(c.isalpha() for c in clean):
            if not parse_single_date(clean):
                id_matches += 1

    if id_matches / total >= 0.5:
        return "id_string"

    return "text"


def profile_csv(file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Profiles raw CSV bytes:
    - Decodes with fallback encodings (utf-8, utf-8-sig, latin-1)
    - Detects delimiter
    - Calculates rows, nulls, sample data, types, duplicates
    """
    text = ""
    for enc in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            text = file_content.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if not text:
        return {
            "filename": filename,
            "error": "Unable to decode CSV file. Please ensure valid UTF-8 or ASCII encoding.",
            "row_count": 0,
            "columns": [],
        }

    # Detect delimiter
    sample = text[:4096]
    delimiter = ","
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=",\t;|")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader, None)
    except Exception as e:
        return {
            "filename": filename,
            "error": f"Failed to parse CSV header: {str(e)}",
            "row_count": 0,
            "columns": [],
        }

    if not header:
        return {
            "filename": filename,
            "error": "Empty CSV file.",
            "row_count": 0,
            "columns": [],
        }

    # Clean header column names
    clean_cols = [c.strip() for c in header if c.strip()]
    if not clean_cols:
        return {
            "filename": filename,
            "error": "CSV contains no named columns.",
            "row_count": 0,
            "columns": [],
        }

    col_count = len(clean_cols)
    rows_data: List[List[str]] = []
    seen_rows = set()
    duplicate_rows = 0

    for r in reader:
        if not r or all(not cell.strip() for cell in r):
            continue  # skip empty lines
        padded = r + [""] * (col_count - len(r))
        trimmed = tuple(padded[:col_count])
        if trimmed in seen_rows:
            duplicate_rows += 1
        seen_rows.add(trimmed)
        rows_data.append(list(trimmed))

    total_rows = len(rows_data)

    # Column-level profiling
    columns_profile: List[Dict[str, Any]] = []
    for col_idx, col_name in enumerate(clean_cols):
        values = [row[col_idx].strip() for row in rows_data]
        non_empty = [v for v in values if v]
        null_count = total_rows - len(non_empty)
        null_pct = round((null_count / total_rows) * 100, 1) if total_rows > 0 else 0.0

        # Collect up to 10 unique sample non-empty values for preview & type detection
        unique_samples = []
        for v in non_empty:
            if v not in unique_samples:
                unique_samples.append(v)
            if len(unique_samples) >= 10:
                break

        # Multi-sample date analysis across non-empty values (up to 50)
        sample_batch = non_empty[:50] if non_empty else unique_samples
        date_analysis = analyze_date_values(sample_batch)
        detected_t = detect_type(unique_samples if unique_samples else sample_batch)

        columns_profile.append({
            "column_name": col_name,
            "index": col_idx,
            "null_count": null_count,
            "null_percentage": null_pct,
            "sample_values": unique_samples[:5],
            "detected_type": detected_t,
            "date_parse_success_rate": date_analysis["date_parse_success_rate"],
            "is_date_ambiguous": date_analysis["is_ambiguous"],
            "inferred_date_format": date_analysis["inferred_format"],
        })

    # Top 5 preview rows
    preview_rows = []
    for row in rows_data[:5]:
        preview_rows.append({clean_cols[i]: row[i] for i in range(col_count)})

    return {
        "filename": filename,
        "row_count": total_rows,
        "column_count": col_count,
        "columns": columns_profile,
        "duplicate_rows": duplicate_rows,
        "preview_rows": preview_rows,
        "delimiter": delimiter,
    }
