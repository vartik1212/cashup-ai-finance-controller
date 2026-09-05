"""
ReconAI — Realistic Synthetic Data Generator
============================================
Generates 120 realistic Indian business invoice cases with corresponding
settlements and bank transactions.

Target Ground Truth Distribution (Total = 120):
- 60 EXACT_MATCH
- 15 FEE_ADJUSTED_MATCH
- 10 DELAYED_SETTLEMENT
-  8 PARTIAL_PAYMENT
-  6 REFUND
-  5 DUPLICATE
-  5 AMOUNT_MISMATCH
-  5 MISSING_SETTLEMENT
-  6 AMBIGUOUS_MATCH

Amounts adhere to realistic Indian business payment values:
- Most transactions: ₹5,000 – ₹2,00,000
- Some larger B2B transactions: ₹2,00,000 – ₹8,00,000
- Small number of enterprise tranches: ₹8,00,000 – ₹15,00,000
- Decimal-safe financial values.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import List, Tuple

# Seed for deterministic reproducibility
random.seed(42)

OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Realistic Indian Business Reference Data (SMBs, SaaS, Retail, B2B)
# ---------------------------------------------------------------------------

COMPANIES = [
    ("BrightCart Retail", "CUST-BCR-001", "27AABCB1122C1Z1"),
    ("Nova Foods", "CUST-NVF-002", "29AABCN3344D1Z2"),
    ("Aster Labs", "CUST-AST-003", "27AABCA5566E1Z3"),
    ("UrbanNest", "CUST-URN-004", "24AABCU7788F1Z4"),
    ("Orbit Systems", "CUST-ORB-005", "29AABCO9900G1Z5"),
    ("GreenLeaf Supplies", "CUST-GLS-006", "27AABCG1234H1Z6"),
    ("Vertex Consulting", "CUST-VTX-007", "09AABCV5678J1Z7"),
    ("PixelWorks", "CUST-PXW-008", "27AABCP9012K1Z8"),
    ("NorthStar Traders", "CUST-NST-009", "19AABCN3456L1Z9"),
    ("BluePeak Technologies", "CUST-BPT-010", "36AABCB7890M1ZA"),
    ("Zenith Logistics", "CUST-ZNL-011", "27AABCZ2345N1ZB"),
    ("CloudPulse Software", "CUST-CPS-012", "29AABCC6789P1ZC"),
    ("Quantum Electronics", "CUST-QEL-013", "24AABCQ0123Q1ZD"),
    ("Primal Organics", "CUST-PRO-014", "27AABCP4567R1ZE"),
    ("Nexus Infotech", "CUST-NXI-015", "36AABCN8901S1ZF"),
    ("Apex Global Solutions", "CUST-AGS-016", "27AABCA2345T1ZG"),
    ("SilverLine Express", "CUST-SLX-017", "27AABCS6789U1ZH"),
    ("Horizon Media Labs", "CUST-HML-018", "09AABCH0123V1ZJ"),
    ("Beacon BioTech", "CUST-BBT-019", "24AABCB4567W1ZK"),
    ("Synergy Workspace", "CUST-SYW-020", "27AABCS8901X1ZL"),
    ("Indus Craftworks", "CUST-ICW-021", "29AABCI2345Y1ZM"),
    ("Vanguard Security", "CUST-VGS-022", "27AABCV6789Z1ZN"),
    ("Pinnacle Pharma", "CUST-PNP-023", "36AABCP0123A1ZP"),
    ("Alpha Matrix Telecom", "CUST-AMT-024", "27AABCA4567B1ZQ"),
]

GATEWAYS = ["Razorpay", "PayU", "Cashfree", "Paytm", "CCAvenue"]

DESCRIPTIONS = [
    "SaaS Subscription - Growth Tier",
    "IT Infrastructure Services",
    "Quarterly Maintenance Contract",
    "Cloud Hosting & Compute Credits",
    "Digital Performance Marketing",
    "Technical Consulting Retainer",
    "Data Analytics Platform Access",
    "Security & Vulnerability Assessment",
    "Warehouse Inventory Ingestion",
    "Hardware Component Supply Tranche",
    "Freight Forwarding & Transit Fee",
    "Professional Audit & Advisory",
]

SCENARIO_CONFIG = {
    "exact_match": 60,
    "fee_adjusted": 15,
    "delayed_settlement": 10,
    "partial_payment": 8,
    "refund": 6,
    "duplicate_payment": 5,
    "amount_mismatch": 5,
    "missing_settlement": 5,
    "ambiguous_match": 6,
}

assert sum(SCENARIO_CONFIG.values()) == 120, "Total scenarios must equal 120"


def _realistic_amount(tier: str = "auto") -> float:
    """
    Generates realistic Indian B2B / SMB payment amounts:
    - ~75% ₹5,000 – ₹2,00,000 (SMB / Retail / SaaS)
    - ~20% ₹2,00,000 – ₹8,00,000 (Mid-market B2B)
    - ~5%  ₹8,00,000 – ₹15,00,000 (Large enterprise tranches)
    """
    if tier == "auto":
        p = random.random()
        if p < 0.75:
            tier = "small"
        elif p < 0.95:
            tier = "medium"
        else:
            tier = "large"

    if tier == "small":
        # ₹5,000 - ₹2,00,000 (multiples of 500 or 1000)
        base = random.randint(10, 400) * 500
    elif tier == "medium":
        # ₹2,00,000 - ₹8,00,000 (multiples of 2,500)
        base = random.randint(80, 320) * 2500
    else:
        # ₹8,00,000 - ₹15,00,000 (multiples of 10,000)
        base = random.randint(80, 150) * 10000

    return float(Decimal(str(base)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _gateway_fee_calc(amount: float, gateway: str) -> Tuple[float, float]:
    """
    Deterministic gateway fee calculation:
    rate (1.5% - 2.1%) + 18% GST on fee.
    Returns (total_fee, net_amount).
    """
    rates = {
        "Razorpay": Decimal("0.0200"),
        "PayU": Decimal("0.0175"),
        "Cashfree": Decimal("0.0190"),
        "Paytm": Decimal("0.0150"),
        "CCAvenue": Decimal("0.0210"),
    }
    rate = rates.get(gateway, Decimal("0.0200"))
    dec_amount = Decimal(str(amount))
    fee_base = (dec_amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    gst = (fee_base * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_fee = fee_base + gst
    net_amount = (dec_amount - total_fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(total_fee), float(net_amount)


def _utr() -> str:
    return f"UTR{random.randint(100000000000, 999999999999)}"


def _base_date() -> date:
    month = random.randint(1, 4)
    day = random.randint(1, 28)
    return date(2026, month, day)


def generate_datasets() -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    invoices: List[dict] = []
    settlements: List[dict] = []
    bank_transactions: List[dict] = []
    ground_truth: List[dict] = []

    inv_counter = 1
    set_counter = 1
    pay_counter = 1
    bnk_counter = 1

    def inv_id() -> str:
        nonlocal inv_counter
        iid = f"INV-2026-{inv_counter:04d}"
        inv_counter += 1
        return iid

    def set_id() -> str:
        nonlocal set_counter
        sid = f"SET-2026-{set_counter:04d}"
        set_counter += 1
        return sid

    def pay_id() -> str:
        nonlocal pay_counter
        pid = f"PAY-2026-{pay_counter:04d}"
        pay_counter += 1
        return pid

    def bnk_id() -> str:
        nonlocal bnk_counter
        bid = f"BNK-2026-{bnk_counter:04d}"
        bnk_counter += 1
        return bid

    def pick_company(idx: int):
        return COMPANIES[idx % len(COMPANIES)]

    # ------------------------------------------------------------------
    # 1. EXACT MATCHES (60)
    # Genuinely clean: Gross = Invoice, Fee = 0, Net = Gross = Bank
    # ------------------------------------------------------------------
    for i in range(SCENARIO_CONFIG["exact_match"]):
        company = pick_company(i)
        iid = inv_id()
        amount = _realistic_amount()
        inv_date = _base_date()
        gateway = random.choice(GATEWAYS)
        sid = set_id()
        pid = pay_id()
        utr = _utr()
        pay_date = inv_date + timedelta(days=random.randint(0, 2))
        set_date = pay_date + timedelta(days=random.randint(1, 2))
        bid = bnk_id()

        invoices.append({
            "invoice_id": iid,
            "customer_name": company[0],
            "customer_id": company[1],
            "invoice_amount": amount,
            "invoice_date": inv_date.isoformat(),
            "due_date": (inv_date + timedelta(days=30)).isoformat(),
            "currency": "INR",
            "description": random.choice(DESCRIPTIONS),
            "gstin": company[2],
            "ground_truth_scenario": "exact_match",
            "expected_match_id": sid,
        })
        settlements.append({
            "settlement_id": sid,
            "payment_id": pid,
            "invoice_reference": iid,
            "customer_id": company[1],
            "amount": amount,
            "fee": 0.0,
            "net_amount": amount,
            "payment_date": pay_date.isoformat(),
            "settlement_date": set_date.isoformat(),
            "payment_gateway": gateway,
            "utr_number": utr,
            "remarks": "Payment received in full",
            "ground_truth_invoice_id": iid,
            "ground_truth_scenario": "exact_match",
        })
        bank_transactions.append({
            "bank_txn_id": bid,
            "utr_number": utr,
            "amount": amount,
            "transaction_date": set_date.isoformat(),
            "value_date": set_date.isoformat(),
            "description": f"NEFT {gateway} SETTLEMENT {iid}",
            "bank_reference": utr,
            "settlement_reference": sid,
            "transaction_type": "credit",
            "balance": None,
            "ground_truth_settlement_id": sid,
            "ground_truth_scenario": "exact_match",
        })
        ground_truth.append({
            "invoice_id": iid,
            "settlement_id": sid,
            "bank_txn_id": bid,
            "scenario": "exact_match",
            "expected_status": "Exact Match",
        })

    # ------------------------------------------------------------------
    # 2. FEE-ADJUSTED MATCHES (15)
    # Gross matches invoice, real gateway fee (>0) + GST deducted
    # ------------------------------------------------------------------
    for i in range(SCENARIO_CONFIG["fee_adjusted"]):
        company = pick_company(60 + i)
        iid = inv_id()
        amount = _realistic_amount()
        inv_date = _base_date()
        gateway = random.choice(GATEWAYS)
        fee, net_amount = _gateway_fee_calc(amount, gateway)
        sid = set_id()
        pid = pay_id()
        utr = _utr()
        pay_date = inv_date + timedelta(days=random.randint(0, 2))
        set_date = pay_date + timedelta(days=random.randint(1, 2))
        bid = bnk_id()

        invoices.append({
            "invoice_id": iid,
            "customer_name": company[0],
            "customer_id": company[1],
            "invoice_amount": amount,
            "invoice_date": inv_date.isoformat(),
            "due_date": (inv_date + timedelta(days=30)).isoformat(),
            "currency": "INR",
            "description": random.choice(DESCRIPTIONS),
            "gstin": company[2],
            "ground_truth_scenario": "fee_adjusted",
            "expected_match_id": sid,
        })
        settlements.append({
            "settlement_id": sid,
            "payment_id": pid,
            "invoice_reference": iid,
            "customer_id": company[1],
            "amount": amount,
            "fee": fee,
            "net_amount": net_amount,
            "payment_date": pay_date.isoformat(),
            "settlement_date": set_date.isoformat(),
            "payment_gateway": gateway,
            "utr_number": utr,
            "remarks": f"MDR Fee {gateway} 2% + GST deduction",
            "ground_truth_invoice_id": iid,
            "ground_truth_scenario": "fee_adjusted",
        })
        bank_transactions.append({
            "bank_txn_id": bid,
            "utr_number": utr,
            "amount": net_amount,
            "transaction_date": set_date.isoformat(),
            "value_date": set_date.isoformat(),
            "description": f"RTGS {gateway} NET SETTLEMENT {iid}",
            "bank_reference": utr,
            "settlement_reference": sid,
            "transaction_type": "credit",
            "balance": None,
            "ground_truth_settlement_id": sid,
            "ground_truth_scenario": "fee_adjusted",
        })
        ground_truth.append({
            "invoice_id": iid,
            "settlement_id": sid,
            "bank_txn_id": bid,
            "scenario": "fee_adjusted",
            "expected_status": "Fee Match",
        })

    # ------------------------------------------------------------------
    # 3. DELAYED SETTLEMENT (10)
    # References match, amount clean, but payment received > 5 days SLA
    # ------------------------------------------------------------------
    for i in range(SCENARIO_CONFIG["delayed_settlement"]):
        company = pick_company(75 + i)
        iid = inv_id()
        amount = _realistic_amount()
        inv_date = _base_date()
        gateway = random.choice(GATEWAYS)
        delay_days = random.randint(8, 20)  # Beyond SLA (5 days)
        pay_date = inv_date + timedelta(days=delay_days)
        set_date = pay_date + timedelta(days=random.randint(1, 2))
        sid = set_id()
        pid = pay_id()
        utr = _utr()
        bid = bnk_id()

        invoices.append({
            "invoice_id": iid,
            "customer_name": company[0],
            "customer_id": company[1],
            "invoice_amount": amount,
            "invoice_date": inv_date.isoformat(),
            "due_date": (inv_date + timedelta(days=30)).isoformat(),
            "currency": "INR",
            "description": random.choice(DESCRIPTIONS),
            "gstin": company[2],
            "ground_truth_scenario": "delayed_settlement",
            "expected_match_id": sid,
        })
        settlements.append({
            "settlement_id": sid,
            "payment_id": pid,
            "invoice_reference": iid,
            "customer_id": company[1],
            "amount": amount,
            "fee": 0.0,
            "net_amount": amount,
            "payment_date": pay_date.isoformat(),
            "settlement_date": set_date.isoformat(),
            "payment_gateway": gateway,
            "utr_number": utr,
            "remarks": f"Late remittance received after {delay_days} days",
            "ground_truth_invoice_id": iid,
            "ground_truth_scenario": "delayed_settlement",
        })
        bank_transactions.append({
            "bank_txn_id": bid,
            "utr_number": utr,
            "amount": amount,
            "transaction_date": set_date.isoformat(),
            "value_date": set_date.isoformat(),
            "description": f"NEFT DELAYED CR {iid}",
            "bank_reference": utr,
            "settlement_reference": sid,
            "transaction_type": "credit",
            "balance": None,
            "ground_truth_settlement_id": sid,
            "ground_truth_scenario": "delayed_settlement",
        })
        ground_truth.append({
            "invoice_id": iid,
            "settlement_id": sid,
            "bank_txn_id": bid,
            "scenario": "delayed_settlement",
            "expected_status": "Probable Match",
        })

    # ------------------------------------------------------------------
    # 4. PARTIAL PAYMENT (8)
    # Legitimate tranche received (30% – 70% of invoice amount)
    # ------------------------------------------------------------------
    for i in range(SCENARIO_CONFIG["partial_payment"]):
        company = pick_company(85 + i)
        iid = inv_id()
        full_amount = _realistic_amount()
        ratio = random.choice([0.30, 0.40, 0.50, 0.60, 0.70])
        partial_gross = float(
            (Decimal(str(full_amount)) * Decimal(str(ratio))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        inv_date = _base_date()
        gateway = random.choice(GATEWAYS)
        sid = set_id()
        pid = pay_id()
        utr = _utr()
        pay_date = inv_date + timedelta(days=random.randint(1, 3))
        set_date = pay_date + timedelta(days=1)
        bid = bnk_id()

        invoices.append({
            "invoice_id": iid,
            "customer_name": company[0],
            "customer_id": company[1],
            "invoice_amount": full_amount,
            "invoice_date": inv_date.isoformat(),
            "due_date": (inv_date + timedelta(days=30)).isoformat(),
            "currency": "INR",
            "description": random.choice(DESCRIPTIONS),
            "gstin": company[2],
            "ground_truth_scenario": "partial_payment",
            "expected_match_id": sid,
        })
        settlements.append({
            "settlement_id": sid,
            "payment_id": pid,
            "invoice_reference": iid,
            "customer_id": company[1],
            "amount": partial_gross,
            "fee": 0.0,
            "net_amount": partial_gross,
            "payment_date": pay_date.isoformat(),
            "settlement_date": set_date.isoformat(),
            "payment_gateway": gateway,
            "utr_number": utr,
            "remarks": f"Partial installment 1 ({int(ratio*100)}%) for invoice {iid}",
            "ground_truth_invoice_id": iid,
            "ground_truth_scenario": "partial_payment",
        })
        bank_transactions.append({
            "bank_txn_id": bid,
            "utr_number": utr,
            "amount": partial_gross,
            "transaction_date": set_date.isoformat(),
            "value_date": set_date.isoformat(),
            "description": f"CMS PARTIAL SETTLEMENT {iid}",
            "bank_reference": utr,
            "settlement_reference": sid,
            "transaction_type": "credit",
            "balance": None,
            "ground_truth_settlement_id": sid,
            "ground_truth_scenario": "partial_payment",
        })
        ground_truth.append({
            "invoice_id": iid,
            "settlement_id": sid,
            "bank_txn_id": bid,
            "scenario": "partial_payment",
            "expected_status": "Human Review",
        })

    # ------------------------------------------------------------------
    # 5. REFUND DISCREPANCY (6)
    # Remarks explicitly indicate refund / return deduction
    # ------------------------------------------------------------------
    for i in range(SCENARIO_CONFIG["refund"]):
        company = pick_company(93 + i)
        iid = inv_id()
        full_amount = _realistic_amount()
        refund_ratio = random.choice([0.15, 0.20, 0.25, 0.30])
        refund_deduction = float(
            (Decimal(str(full_amount)) * Decimal(str(refund_ratio))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        net_after_refund = float(
            (Decimal(str(full_amount)) - Decimal(str(refund_deduction))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        inv_date = _base_date()
        gateway = random.choice(GATEWAYS)
        sid = set_id()
        pid = pay_id()
        utr = _utr()
        pay_date = inv_date + timedelta(days=random.randint(1, 3))
        set_date = pay_date + timedelta(days=1)
        bid = bnk_id()

        invoices.append({
            "invoice_id": iid,
            "customer_name": company[0],
            "customer_id": company[1],
            "invoice_amount": full_amount,
            "invoice_date": inv_date.isoformat(),
            "due_date": (inv_date + timedelta(days=30)).isoformat(),
            "currency": "INR",
            "description": random.choice(DESCRIPTIONS),
            "gstin": company[2],
            "ground_truth_scenario": "refund",
            "expected_match_id": sid,
        })
        settlements.append({
            "settlement_id": sid,
            "payment_id": pid,
            "invoice_reference": iid,
            "customer_id": company[1],
            "amount": net_after_refund,
            "fee": 0.0,
            "net_amount": net_after_refund,
            "payment_date": pay_date.isoformat(),
            "settlement_date": set_date.isoformat(),
            "payment_gateway": gateway,
            "utr_number": utr,
            "remarks": f"Refund adjustment deduction ₹{refund_deduction:,.2f} applied",
            "ground_truth_invoice_id": iid,
            "ground_truth_scenario": "refund",
        })
        bank_transactions.append({
            "bank_txn_id": bid,
            "utr_number": utr,
            "amount": net_after_refund,
            "transaction_date": set_date.isoformat(),
            "value_date": set_date.isoformat(),
            "description": f"NEFT NET REFUND ADJ {iid}",
            "bank_reference": utr,
            "settlement_reference": sid,
            "transaction_type": "credit",
            "balance": None,
            "ground_truth_settlement_id": sid,
            "ground_truth_scenario": "refund",
        })
        ground_truth.append({
            "invoice_id": iid,
            "settlement_id": sid,
            "bank_txn_id": bid,
            "scenario": "refund",
            "expected_status": "Human Review",
        })

    # ------------------------------------------------------------------
    # 6. DUPLICATE PAYMENT (5)
    # 2 settlements citing the exact same invoice reference
    # ------------------------------------------------------------------
    for i in range(SCENARIO_CONFIG["duplicate_payment"]):
        company = pick_company(99 + i)
        iid = inv_id()
        amount = _realistic_amount()
        inv_date = _base_date()
        gateway = random.choice(GATEWAYS)
        sid1 = set_id()
        sid2 = set_id()
        pid1 = pay_id()
        pid2 = pay_id()
        utr1 = _utr()
        utr2 = _utr()
        pay_date = inv_date + timedelta(days=1)
        set_date = pay_date + timedelta(days=1)
        bid1 = bnk_id()
        bid2 = bnk_id()

        invoices.append({
            "invoice_id": iid,
            "customer_name": company[0],
            "customer_id": company[1],
            "invoice_amount": amount,
            "invoice_date": inv_date.isoformat(),
            "due_date": (inv_date + timedelta(days=30)).isoformat(),
            "currency": "INR",
            "description": random.choice(DESCRIPTIONS),
            "gstin": company[2],
            "ground_truth_scenario": "duplicate_payment",
            "expected_match_id": sid1,
        })
        # Primary settlement
        settlements.append({
            "settlement_id": sid1,
            "payment_id": pid1,
            "invoice_reference": iid,
            "customer_id": company[1],
            "amount": amount,
            "fee": 0.0,
            "net_amount": amount,
            "payment_date": pay_date.isoformat(),
            "settlement_date": set_date.isoformat(),
            "payment_gateway": gateway,
            "utr_number": utr1,
            "remarks": "Primary settlement credit",
            "ground_truth_invoice_id": iid,
            "ground_truth_scenario": "duplicate_payment",
        })
        # Redundant duplicate settlement
        settlements.append({
            "settlement_id": sid2,
            "payment_id": pid2,
            "invoice_reference": iid,
            "customer_id": company[1],
            "amount": amount,
            "fee": 0.0,
            "net_amount": amount,
            "payment_date": pay_date.isoformat(),
            "settlement_date": set_date.isoformat(),
            "payment_gateway": gateway,
            "utr_number": utr2,
            "remarks": "Redundant second payment credit (duplicate)",
            "ground_truth_invoice_id": iid,
            "ground_truth_scenario": "duplicate_payment",
        })
        bank_transactions.append({
            "bank_txn_id": bid1,
            "utr_number": utr1,
            "amount": amount,
            "transaction_date": set_date.isoformat(),
            "value_date": set_date.isoformat(),
            "description": f"NEFT {gateway} {iid}",
            "bank_reference": utr1,
            "settlement_reference": sid1,
            "transaction_type": "credit",
            "balance": None,
            "ground_truth_settlement_id": sid1,
            "ground_truth_scenario": "duplicate_payment",
        })
        bank_transactions.append({
            "bank_txn_id": bid2,
            "utr_number": utr2,
            "amount": amount,
            "transaction_date": set_date.isoformat(),
            "value_date": set_date.isoformat(),
            "description": f"NEFT {gateway} {iid} DUP",
            "bank_reference": utr2,
            "settlement_reference": sid2,
            "transaction_type": "credit",
            "balance": None,
            "ground_truth_settlement_id": sid2,
            "ground_truth_scenario": "duplicate_payment",
        })
        ground_truth.append({
            "invoice_id": iid,
            "settlement_id": sid1,
            "bank_txn_id": bid1,
            "scenario": "duplicate_payment",
            "expected_status": "Human Review",
        })

    # ------------------------------------------------------------------
    # 7. AMOUNT MISMATCH (5)
    # Direct reference matches, but gross amount has an unexplained variance
    # ------------------------------------------------------------------
    for i in range(SCENARIO_CONFIG["amount_mismatch"]):
        company = pick_company(104 + i)
        iid = inv_id()
        inv_amt = _realistic_amount()
        # Variance of ~7.5% (neither a valid MDR fee nor a partial payment)
        var_pct = Decimal("0.075")
        s_gross = float(
            (Decimal(str(inv_amt)) * (Decimal("1") - var_pct)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        inv_date = _base_date()
        gateway = random.choice(GATEWAYS)
        sid = set_id()
        pid = pay_id()
        utr = _utr()
        pay_date = inv_date + timedelta(days=random.randint(1, 3))
        set_date = pay_date + timedelta(days=1)
        bid = bnk_id()

        invoices.append({
            "invoice_id": iid,
            "customer_name": company[0],
            "customer_id": company[1],
            "invoice_amount": inv_amt,
            "invoice_date": inv_date.isoformat(),
            "due_date": (inv_date + timedelta(days=30)).isoformat(),
            "currency": "INR",
            "description": random.choice(DESCRIPTIONS),
            "gstin": company[2],
            "ground_truth_scenario": "amount_mismatch",
            "expected_match_id": sid,
        })
        settlements.append({
            "settlement_id": sid,
            "payment_id": pid,
            "invoice_reference": iid,
            "customer_id": company[1],
            "amount": s_gross,
            "fee": 0.0,
            "net_amount": s_gross,
            "payment_date": pay_date.isoformat(),
            "settlement_date": set_date.isoformat(),
            "payment_gateway": gateway,
            "utr_number": utr,
            "remarks": "Standard payout - unexplained discrepancy",
            "ground_truth_invoice_id": iid,
            "ground_truth_scenario": "amount_mismatch",
        })
        bank_transactions.append({
            "bank_txn_id": bid,
            "utr_number": utr,
            "amount": s_gross,
            "transaction_date": set_date.isoformat(),
            "value_date": set_date.isoformat(),
            "description": f"NEFT MISMATCH {iid}",
            "bank_reference": utr,
            "settlement_reference": sid,
            "transaction_type": "credit",
            "balance": None,
            "ground_truth_settlement_id": sid,
            "ground_truth_scenario": "amount_mismatch",
        })
        ground_truth.append({
            "invoice_id": iid,
            "settlement_id": sid,
            "bank_txn_id": bid,
            "scenario": "amount_mismatch",
            "expected_status": "Human Review",
        })

    # ------------------------------------------------------------------
    # 8. MISSING SETTLEMENT (5)
    # Invoice exists, but NO settlement or bank record ever arrived
    # ------------------------------------------------------------------
    for i in range(SCENARIO_CONFIG["missing_settlement"]):
        company = pick_company(109 + i)
        iid = inv_id()
        amount = _realistic_amount()
        inv_date = _base_date()

        invoices.append({
            "invoice_id": iid,
            "customer_name": company[0],
            "customer_id": company[1],
            "invoice_amount": amount,
            "invoice_date": inv_date.isoformat(),
            "due_date": (inv_date + timedelta(days=30)).isoformat(),
            "currency": "INR",
            "description": random.choice(DESCRIPTIONS),
            "gstin": company[2],
            "ground_truth_scenario": "missing_settlement",
            "expected_match_id": None,
        })
        ground_truth.append({
            "invoice_id": iid,
            "settlement_id": None,
            "bank_txn_id": None,
            "scenario": "missing_settlement",
            "expected_status": "Unresolved",
        })

    # ------------------------------------------------------------------
    # 9. AMBIGUOUS MATCH (6)
    # Customer matches, amount is similar (within 2-4%), but reference is missing
    # ------------------------------------------------------------------
    for i in range(SCENARIO_CONFIG["ambiguous_match"]):
        company = pick_company(114 + i)
        iid = inv_id()
        amount = _realistic_amount()
        # Small variance 2%
        var_pct = Decimal("0.02")
        s_amt = float(
            (Decimal(str(amount)) * (Decimal("1") - var_pct)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        )
        inv_date = _base_date()
        gateway = random.choice(GATEWAYS)
        sid = set_id()
        pid = pay_id()
        utr = _utr()
        pay_date = inv_date + timedelta(days=random.randint(1, 3))
        set_date = pay_date + timedelta(days=1)
        bid = bnk_id()

        invoices.append({
            "invoice_id": iid,
            "customer_name": company[0],
            "customer_id": company[1],
            "invoice_amount": amount,
            "invoice_date": inv_date.isoformat(),
            "due_date": (inv_date + timedelta(days=30)).isoformat(),
            "currency": "INR",
            "description": random.choice(DESCRIPTIONS),
            "gstin": company[2],
            "ground_truth_scenario": "ambiguous_match",
            "expected_match_id": sid,
        })
        settlements.append({
            "settlement_id": sid,
            "payment_id": pid,
            "invoice_reference": "",  # Missing invoice reference!
            "customer_id": company[1],
            "amount": s_amt,
            "fee": 0.0,
            "net_amount": s_amt,
            "payment_date": pay_date.isoformat(),
            "settlement_date": set_date.isoformat(),
            "payment_gateway": gateway,
            "utr_number": utr,
            "remarks": "Remittance without invoice identifier",
            "ground_truth_invoice_id": iid,
            "ground_truth_scenario": "ambiguous_match",
        })
        bank_transactions.append({
            "bank_txn_id": bid,
            "utr_number": utr,
            "amount": s_amt,
            "transaction_date": set_date.isoformat(),
            "value_date": set_date.isoformat(),
            "description": f"NEFT AMBIGUOUS {company[1]}",
            "bank_reference": utr,
            "settlement_reference": sid,
            "transaction_type": "credit",
            "balance": None,
            "ground_truth_settlement_id": sid,
            "ground_truth_scenario": "ambiguous_match",
        })
        ground_truth.append({
            "invoice_id": iid,
            "settlement_id": sid,
            "bank_txn_id": bid,
            "scenario": "ambiguous_match",
            "expected_status": "Human Review",
        })

    return invoices, settlements, bank_transactions, ground_truth


def save_datasets() -> None:
    invs, sets, bnks, gt = generate_datasets()

    with open(OUTPUT_DIR / "invoices.json", "w", encoding="utf-8") as f:
        json.dump(invs, f, indent=2)

    with open(OUTPUT_DIR / "settlements.json", "w", encoding="utf-8") as f:
        json.dump(sets, f, indent=2)

    with open(OUTPUT_DIR / "bank_transactions.json", "w", encoding="utf-8") as f:
        json.dump(bnks, f, indent=2)

    with open(OUTPUT_DIR / "ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(gt, f, indent=2)

    # Also export CSVs
    if invs:
        with open(OUTPUT_DIR / "invoices.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=invs[0].keys())
            writer.writeheader()
            writer.writerows(invs)

    if sets:
        with open(OUTPUT_DIR / "settlements.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=sets[0].keys())
            writer.writeheader()
            writer.writerows(sets)

    if bnks:
        with open(OUTPUT_DIR / "bank_transactions.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=bnks[0].keys())
            writer.writeheader()
            writer.writerows(bnks)

    print(f"Generated realistic dataset in {OUTPUT_DIR}:")
    print(f"  Invoices:           {len(invs)}")
    print(f"  Settlements:        {len(sets)}")
    print(f"  Bank Transactions:  {len(bnks)}")
    print(f"  Ground Truth:       {len(gt)}")


if __name__ == "__main__":
    save_datasets()
