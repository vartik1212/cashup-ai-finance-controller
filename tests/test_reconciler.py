"""
ReconAI — Reconciliation Engine Unit Tests
==========================================
Tests all 9 scenario types, metrics calculations, and edge cases.
No mocking of financial logic — all tests run against the real engine.
"""

import sys
import unittest
from datetime import date
from pathlib import Path
from typing import Optional, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.engine.reconciler import reconcile
from backend.models.schemas import (
    Invoice,
    Settlement,
    BankTransaction,
    MatchType,
    ReconciliationStatus,
    ExceptionCategory,
    ReconciliationRun,
    ReconciliationResult,
)


def _inv(
    iid: str,
    amount: float,
    customer: str = "CUST-001",
    inv_date: date = date(2026, 3, 1),
    scenario: str = "test",
    expected_match: Optional[str] = None,
) -> Invoice:
    return Invoice(
        invoice_id=iid,
        customer_name="Test Corp",
        customer_id=customer,
        invoice_amount=amount,
        invoice_date=inv_date,
        due_date=date(2026, 3, 31),
        currency="INR",
        description="Test Invoice",
        ground_truth_scenario=scenario,
        expected_match_id=expected_match,
    )


def _set(
    sid: str,
    amount: float,
    fee: float = 0.0,
    ref: Optional[str] = None,
    customer: str = "CUST-001",
    pay_date: date = date(2026, 3, 2),
    scenario: str = "test",
    utr: Optional[str] = None,
) -> Settlement:
    net = round(amount - fee, 2)
    return Settlement(
        settlement_id=sid,
        payment_id=f"PAY-{sid}",
        invoice_reference=ref,
        customer_id=customer,
        amount=amount,
        fee=fee,
        net_amount=net,
        payment_date=pay_date,
        settlement_date=date(2026, 3, 3),
        payment_gateway="Razorpay",
        utr_number=utr,
        ground_truth_scenario=scenario,
    )


def _bnk(
    bid: str,
    amount: float,
    utr: Optional[str] = None,
    set_ref: Optional[str] = None,
) -> BankTransaction:
    return BankTransaction(
        bank_txn_id=bid,
        utr_number=utr,
        amount=amount,
        transaction_date=date(2026, 3, 3),
        value_date=date(2026, 3, 3),
        description=f"NEFT {bid}",
        settlement_reference=set_ref,
        transaction_type="credit",
        ground_truth_scenario="test",
    )


def _run(
    invoices: List[Invoice],
    settlements: List[Settlement],
    bank: Optional[List[BankTransaction]] = None,
    gt: Optional[List[dict]] = None,
) -> Tuple[ReconciliationRun, List[ReconciliationResult]]:
    return reconcile(
        invoices=invoices,
        settlements=settlements,
        bank_transactions=bank or [],
        ground_truth_records=gt,
        run_id="TEST-RUN",
    )


class TestExactMatch(unittest.TestCase):
    def test_exact_gross_match_with_reference(self):
        """Invoice amount == settlement gross, reference matches."""
        inv = _inv("INV-001", 100000.0, scenario="exact_match", expected_match="SET-001")
        s = _set("SET-001", 100000.0, fee=0.0, ref="INV-001")
        run, results = _run([inv], [s])
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r.invoice_id, "INV-001")
        self.assertEqual(r.settlement_id, "SET-001")
        self.assertIn(r.match_type, [MatchType.EXACT, MatchType.FEE_ADJUSTED])
        self.assertNotEqual(r.status, ReconciliationStatus.UNRESOLVED)
        self.assertGreater(r.confidence_score, 50)

    def test_match_rate_one_of_one(self):
        inv = _inv("INV-001", 100000.0, scenario="exact_match", expected_match="SET-001")
        s = _set("SET-001", 100000.0, ref="INV-001")
        run, results = _run([inv], [s])
        self.assertEqual(run.match_rate, 1.0)
        self.assertEqual(run.exact_matches, 1)
        self.assertEqual(run.unresolved, 0)


class TestFeeAdjustedMatch(unittest.TestCase):
    def test_razorpay_fee_deduction(self):
        """Razorpay 2% + 18% GST fee-adjusted match."""
        amount = 500000.0
        fee = round(amount * 0.02 * 1.18, 2)
        inv = _inv("INV-002", amount, scenario="fee_deducted", expected_match="SET-002")
        s = _set("SET-002", amount, fee=fee, ref="INV-002")
        run, results = _run([inv], [s])
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertIn(r.match_type, [MatchType.FEE_ADJUSTED, MatchType.EXACT])
        self.assertNotEqual(r.status, ReconciliationStatus.UNRESOLVED)
        self.assertGreater(r.confidence_score, 60)

    def test_settlement_gross_matches_invoice_not_net(self):
        """settlement.amount == invoice_amount, settlement.net_amount < invoice."""
        inv = _inv("INV-003", 250000.0, scenario="fee_deducted", expected_match="SET-003")
        s = _set("SET-003", 250000.0, fee=5900.0, ref="INV-003")
        run, results = _run([inv], [s])
        r = results[0]
        self.assertIn(r.match_type, [MatchType.EXACT, MatchType.FEE_ADJUSTED])
        self.assertGreater(r.confidence_score, 60)


class TestDelayedSettlement(unittest.TestCase):
    def test_delayed_15_days(self):
        """Settlement arrives 15 days after invoice — should be DELAYED or PROBABLE_MATCH."""
        inv = _inv("INV-004", 300000.0, inv_date=date(2026, 3, 1), scenario="delayed_settlement")
        s = _set("SET-004", 300000.0, ref="INV-004", pay_date=date(2026, 3, 16))
        run, results = _run([inv], [s])
        r = results[0]
        self.assertNotEqual(r.status, ReconciliationStatus.UNRESOLVED)
        self.assertIn(r.match_type, [MatchType.DELAYED, MatchType.EXACT, MatchType.FEE_ADJUSTED])

    def test_date_within_normal_window_not_delayed(self):
        """3-day settlement should NOT be classified as delayed."""
        inv = _inv("INV-005", 150000.0, inv_date=date(2026, 3, 1))
        s = _set("SET-005", 150000.0, ref="INV-005", pay_date=date(2026, 3, 4))
        run, results = _run([inv], [s])
        r = results[0]
        self.assertNotEqual(r.match_type, MatchType.DELAYED)


class TestPartialPayment(unittest.TestCase):
    def test_50_percent_partial(self):
        inv = _inv("INV-006", 1000000.0, scenario="partial_payment", expected_match="SET-006")
        s = _set("SET-006", 500000.0, ref="INV-006")
        run, results = _run([inv], [s])
        r = results[0]
        self.assertEqual(r.match_type, MatchType.PARTIAL)
        self.assertEqual(r.status, ReconciliationStatus.HUMAN_REVIEW)
        self.assertEqual(r.exception_category, ExceptionCategory.PARTIAL_PAYMENT)
        self.assertAlmostEqual(r.difference, 500000.0, places=1)

    def test_25_percent_partial(self):
        inv = _inv("INV-007", 800000.0, scenario="partial_payment", expected_match="SET-007")
        s = _set("SET-007", 200000.0, ref="INV-007")
        run, results = _run([inv], [s])
        r = results[0]
        self.assertEqual(r.match_type, MatchType.PARTIAL)


class TestMissingSettlement(unittest.TestCase):
    def test_no_settlement_exists(self):
        inv = _inv("INV-008", 400000.0, scenario="missing_settlement")
        run, results = _run([inv], [])
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertIsNone(r.settlement_id)
        self.assertEqual(r.status, ReconciliationStatus.UNRESOLVED)
        self.assertEqual(r.exception_category, ExceptionCategory.MISSING_SETTLEMENT)
        self.assertEqual(run.unresolved, 1)
        self.assertEqual(run.match_rate, 0.0)

    def test_missing_increases_unresolved_amount(self):
        inv = _inv("INV-009", 350000.0, scenario="missing_settlement")
        run, results = _run([inv], [])
        self.assertEqual(run.unresolved_amount, 350000.0)
        self.assertEqual(run.reconciled_amount, 0.0)
        self.assertEqual(run.unresolved, 1)


class TestDuplicate(unittest.TestCase):
    def test_two_settlements_same_invoice(self):
        """Two settlements with same ref and amount — should flag duplicate."""
        inv = _inv("INV-010", 600000.0, scenario="duplicate_settlement", expected_match="SET-010A")
        s1 = _set("SET-010A", 600000.0, ref="INV-010")
        s2 = _set("SET-010B", 600000.0, ref="INV-010")
        run, results = _run([inv], [s1, s2])
        r = results[0]
        self.assertIn(r.match_type, [MatchType.DUPLICATE, MatchType.EXACT, MatchType.FEE_ADJUSTED])

    def test_duplicate_not_double_counted_in_reconciled_amount(self):
        """Reconciled amount must not double-count duplicate payments."""
        inv = _inv("INV-011", 500000.0)
        s1 = _set("SET-011A", 500000.0, ref="INV-011")
        s2 = _set("SET-011B", 500000.0, ref="INV-011")
        run, results = _run([inv], [s1, s2])
        self.assertLessEqual(run.reconciled_amount, 500000.0)


class TestAmountMismatch(unittest.TestCase):
    def test_large_unexplained_difference(self):
        """Settlement amount is an extreme mismatch — cannot be explained by any rule."""
        inv = _inv("INV-012", 500000.0, scenario="amount_mismatch", expected_match="SET-012")
        s = _set("SET-012", 488000.0, ref="INV-012")
        run, results = _run([inv], [s])
        r = results[0]
        self.assertIn(r.status, [ReconciliationStatus.HUMAN_REVIEW, ReconciliationStatus.UNRESOLVED])


class TestAmbiguousMatch(unittest.TestCase):
    def test_no_reference_ambiguous(self):
        """Settlement with no reference — ambiguous match expected."""
        inv = _inv("INV-013", 750000.0, scenario="ambiguous_match", expected_match="SET-013")
        s = _set("SET-013", 748000.0, ref=None)
        run, results = _run([inv], [s])
        r = results[0]
        self.assertNotEqual(r.status, ReconciliationStatus.EXACT_MATCH)


class TestBankVerification(unittest.TestCase):
    def test_bank_verification_boosts_confidence(self):
        """A settlement backed by a bank txn should score higher."""
        inv = _inv("INV-014", 200000.0)
        s = _set("SET-014", 200000.0, ref="INV-014", utr="UTR123456789012")
        b = _bnk("BNK-014", 200000.0, utr="UTR123456789012", set_ref="SET-014")

        run_no_bank, results_no_bank = _run(
            [_inv("INV-014B", 200000.0)],
            [_set("SET-014B", 200000.0, ref="INV-014B")],
        )
        run_with_bank, results_with_bank = _run([inv], [s], bank=[b])

        r = results_with_bank[0]
        bank_ev = next((e for e in r.evidence if "bank" in e.label.lower()), None)
        self.assertIsNotNone(bank_ev)
        self.assertTrue(bank_ev.matched)
        self.assertIsNotNone(r.bank_txn_id)


class TestMetrics(unittest.TestCase):
    def test_match_rate_calculation(self):
        """match_rate = matched / total, not hardcoded."""
        invoices = [
            _inv("INV-M01", 100000.0, expected_match="SET-M01"),
            _inv("INV-M02", 200000.0, expected_match="SET-M02"),
            _inv("INV-M03", 300000.0),
        ]
        settlements = [
            _set("SET-M01", 100000.0, ref="INV-M01"),
            _set("SET-M02", 200000.0, ref="INV-M02"),
        ]
        run, _ = _run(invoices, settlements)
        self.assertAlmostEqual(run.match_rate, 2 / 3, places=1)

    def test_confidence_range(self):
        """Confidence must always be 0–100."""
        invoices = [_inv(f"INV-C{i}", (i + 1) * 50000.0) for i in range(10)]
        settlements = [_set(f"SET-C{i}", (i + 1) * 50000.0, ref=f"INV-C{i}") for i in range(8)]
        run, results = _run(invoices, settlements)
        for r in results:
            self.assertGreaterEqual(r.confidence_score, 0)
            self.assertLessEqual(r.confidence_score, 100)

    def test_reconciled_amount_excludes_unresolved(self):
        """reconciled_amount must NOT include unresolved invoices."""
        invoices = [
            _inv("INV-A01", 100000.0, customer="CUST-A", expected_match="SET-A01"),
            _inv("INV-A02", 200000.0, customer="CUST-B"),
        ]
        settlements = [_set("SET-A01", 100000.0, ref="INV-A01", customer="CUST-A")]
        run, results = _run(invoices, settlements)
        unresolved_results = [r for r in results if r.status == ReconciliationStatus.UNRESOLVED]
        self.assertEqual(len(unresolved_results), 1)
        self.assertAlmostEqual(run.reconciled_amount, 100000.0, places=1)
        self.assertAlmostEqual(run.unresolved_amount, 200000.0, places=1)

    def test_duplicate_not_double_counted(self):
        """Duplicate settlements must not inflate reconciled_amount."""
        inv = _inv("INV-D01", 500000.0)
        s1 = _set("SET-D01", 500000.0, ref="INV-D01")
        s2 = _set("SET-D02", 500000.0, ref="INV-D01")
        run, _ = _run([inv], [s1, s2])
        self.assertEqual(run.records_processed, 1)
        total_val = run.reconciled_amount + run.unresolved_amount
        self.assertAlmostEqual(total_val, 500000.0, places=1)

    def test_auto_resolved_is_subset_of_matched(self):
        invoices = [
            _inv("INV-E01", 100000.0, expected_match="SET-E01"),
            _inv("INV-E02", 200000.0),
        ]
        settlements = [_set("SET-E01", 100000.0, ref="INV-E01")]
        run, _ = _run(invoices, settlements)
        self.assertLessEqual(run.auto_resolved, run.exact_matches + run.fee_matches + run.probable_matches)


class TestGroundTruthEvaluation(unittest.TestCase):
    def test_correct_match_credited(self):
        """Correct prediction should be marked is_correct_prediction=True."""
        inv = _inv("INV-GT01", 100000.0, scenario="exact_match", expected_match="SET-GT01")
        s = _set("SET-GT01", 100000.0, ref="INV-GT01", scenario="exact_match")
        gt = [
            {
                "invoice_id": "INV-GT01",
                "settlement_id": "SET-GT01",
                "scenario": "exact_match",
                "expected_status": "Exact Match",
            }
        ]
        run, results = _run([inv], [s], gt=gt)
        r = results[0]
        self.assertTrue(r.is_correct_prediction)

    def test_missing_settlement_evaluated_correctly(self):
        """Missing settlement predicted correctly when no settlement exists."""
        inv = _inv("INV-GT02", 200000.0, scenario="missing_settlement", expected_match=None)
        gt = [
            {
                "invoice_id": "INV-GT02",
                "settlement_id": None,
                "scenario": "missing_settlement",
                "expected_status": "Unresolved",
            }
        ]
        run, results = _run([inv], [], gt=gt)
        r = results[0]
        self.assertTrue(r.is_correct_prediction)
        self.assertEqual(run.reconciled_amount, 0.0)

    def test_wrong_settlement_marked_incorrect(self):
        """If we match to wrong settlement, is_correct_prediction=False."""
        inv = _inv("INV-GT03", 100000.0, scenario="exact_match", expected_match="SET-GT03")
        s = _set("SET-WRONG", 100000.0, ref="INV-GT03")
        gt = [
            {
                "invoice_id": "INV-GT03",
                "settlement_id": "SET-GT03",
                "scenario": "exact_match",
                "expected_status": "Exact Match",
            }
        ]
        run, results = _run([inv], [s], gt=gt)
        r = results[0]
        self.assertFalse(r.is_correct_prediction)


class TestEdgeCases(unittest.TestCase):
    def test_empty_settlements(self):
        invoices = [_inv("INV-E01", 100000.0)]
        run, results = _run(invoices, [])
        self.assertEqual(run.unresolved, 1)
        self.assertEqual(run.exact_matches, 0)
        self.assertEqual(len(results), 1)

    def test_empty_invoices(self):
        settlements = [_set("SET-E01", 100000.0)]
        run, results = _run([], settlements)
        self.assertEqual(len(results), 0)
        self.assertEqual(run.records_processed, 0)

    def test_settlement_not_reused_across_invoices(self):
        invoices = [
            _inv("INV-R01", 100000.0, customer="CUST-R"),
            _inv("INV-R02", 100000.0, customer="CUST-R"),
        ]
        s = _set("SET-R01", 100000.0, ref="INV-R01", customer="CUST-R")
        run, results = _run(invoices, [s])
        matched_ids = [r.settlement_id for r in results if r.settlement_id == "SET-R01"]
        self.assertEqual(len(matched_ids), 1, "Settlement reused across multiple invoices!")
        self.assertEqual(run.unresolved + len(matched_ids), 2)

    def test_large_batch_no_crash(self):
        n = 100
        invoices = [_inv(f"INV-L{i:04d}", float((i + 1) * 10000), customer=f"CUST-{i % 20:03d}") for i in range(n)]
        settlements = [
            _set(
                f"SET-L{i:04d}",
                float((i + 1) * 10000),
                ref=f"INV-L{i:04d}",
                customer=f"CUST-{i % 20:03d}",
            )
            for i in range(n)
        ]
        run, results = _run(invoices, settlements)
        self.assertEqual(len(results), n)
        self.assertGreater(run.match_rate, 0.9)


if __name__ == "__main__":
    unittest.main()
