"""
ReconAI — Benchmark Dataset Offline Evaluation
=============================================
Evaluates the latest benchmark reconciliation run against data/ground_truth.json
without altering production reconciliation logic.
"""

import json
import sqlite3
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
GT_PATH = BASE_DIR / "data" / "ground_truth.json"
DB_PATH = BASE_DIR / "data" / "reconai.db"


def evaluate_benchmark():
    with open(GT_PATH, "r", encoding="utf-8") as f:
        gt_list = json.load(f)

    gt_by_id = {r["invoice_id"]: r for r in gt_list}
    total_eligible = len(gt_by_id)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    latest_run = c.execute(
        "SELECT * FROM reconciliation_runs WHERE dataset_source = 'benchmark' "
        "ORDER BY created_at DESC LIMIT 1"
    ).fetchone()

    if not latest_run:
        raise RuntimeError("No benchmark reconciliation run found.")

    run_id = latest_run["run_id"]
    results = c.execute(
        "SELECT * FROM reconciliation_results WHERE run_id = ? ORDER BY invoice_id",
        (run_id,),
    ).fetchall()

    # Map engine status/match_type/exception_category to canonical categories
    # Canonical categories:
    # Exact Match, Fee Adjusted, Delayed Settlement, Partial Payment, Duplicate,
    # Refund Discrepancy, Amount Mismatch, Missing Settlement, Ambiguous Match

    def get_canonical_expected(gt_scenario: str) -> str:
        s = gt_scenario.lower().replace("-", "_").replace(" ", "_")
        mapping = {
            "exact_match": "Exact Match",
            "fee_adjusted": "Fee Adjusted",
            "delayed_settlement": "Delayed Settlement",
            "partial_payment": "Partial Payment",
            "duplicate_payment": "Duplicate",
            "duplicate": "Duplicate",
            "refund": "Refund Discrepancy",
            "refund_discrepancy": "Refund Discrepancy",
            "amount_mismatch": "Amount Mismatch",
            "missing_settlement": "Missing Settlement",
            "ambiguous_match": "Ambiguous Match",
        }
        return mapping.get(s, gt_scenario)

    def get_canonical_predicted(res: sqlite3.Row) -> str:
        mt = res["match_type"]
        exc = res["exception_category"]
        status = res["status"]

        if exc == "Duplicate" or mt == "duplicate":
            return "Duplicate"
        if exc == "Partial Payment" or mt == "partial_payment":
            return "Partial Payment"
        if exc == "Refund Discrepancy" or exc == "Refund" or mt == "refund":
            return "Refund Discrepancy"
        if exc == "Amount Mismatch" or mt == "amount_mismatch":
            return "Amount Mismatch"
        if exc == "Missing Settlement" or (mt == "unresolved" and not res["settlement_id"]):
            return "Missing Settlement"
        if exc == "Ambiguous Match" or mt == "ambiguous_match":
            return "Ambiguous Match"
        if mt == "delayed_settlement":
            return "Delayed Settlement"
        if mt == "fee_adjusted":
            return "Fee Adjusted"
        if mt == "exact_match":
            return "Exact Match"
        if status == "Unresolved":
            return "Missing Settlement"
        return status or "Unknown"

    categories = [
        "Exact Match",
        "Fee Adjusted",
        "Delayed Settlement",
        "Partial Payment",
        "Duplicate",
        "Refund Discrepancy",
        "Amount Mismatch",
        "Missing Settlement",
        "Ambiguous Match",
    ]

    cat_stats = {cat: {"total": 0, "correct": 0, "wrong": 0, "predicted_categories": defaultdict(int)} for cat in categories}
    misclassified = []

    # Reconciled vs Exception definitions:
    # Reconciled in GT: Exact Match, Fee Adjusted, Delayed Settlement (85 cases)
    # Exception in GT: Partial Payment, Duplicate, Refund Discrepancy, Amount Mismatch, Missing Settlement, Ambiguous Match (35 cases)
    RECONCILED_CATS = {"Exact Match", "Fee Adjusted", "Delayed Settlement"}
    EXCEPTION_CATS = {"Partial Payment", "Duplicate", "Refund Discrepancy", "Amount Mismatch", "Missing Settlement", "Ambiguous Match"}

    correctly_reconciled = 0      # TP (GT Reconciled & Pred Reconciled & correct settlement)
    incorrectly_reconciled = 0    # FP (GT Exception but Pred Reconciled) or wrong match
    correctly_identified_exceptions = 0  # TN (GT Exception & Pred Exception)
    missed_exceptions = 0         # FN (GT Exception but Pred Reconciled)
    false_positive_exceptions = 0 # (GT Reconciled but Pred marked as Exception)

    correct_classifications = 0
    incorrect_classifications = 0

    auto_verified_total = 0
    true_auto_verified = 0
    false_auto_verified = 0
    false_auto_verified_records = []

    for r in results:
        inv_id = r["invoice_id"]
        gt = gt_by_id.get(inv_id)
        if not gt:
            continue

        exp_cat = get_canonical_expected(gt.get("scenario", ""))
        pred_cat = get_canonical_predicted(r)

        cat_stats[exp_cat]["total"] += 1
        cat_stats[exp_cat]["predicted_categories"][pred_cat] += 1

        is_correct_classification = (exp_cat == pred_cat)
        # Also check settlement match ID if applicable
        gt_settlement = gt.get("settlement_id")
        pred_settlement = r["settlement_id"]

        is_reconciled_gt = exp_cat in RECONCILED_CATS
        is_reconciled_pred = pred_cat in RECONCILED_CATS

        # Reconciled tracking
        if is_reconciled_gt:
            if is_reconciled_pred:
                # Check settlement match accuracy
                if gt_settlement and pred_settlement and gt_settlement == pred_settlement:
                    correctly_reconciled += 1
                elif not gt_settlement and not pred_settlement:
                    correctly_reconciled += 1
                else:
                    incorrectly_reconciled += 1
            else:
                false_positive_exceptions += 1
        else:
            # Exception in GT
            if not is_reconciled_pred:
                correctly_identified_exceptions += 1
            else:
                missed_exceptions += 1
                incorrectly_reconciled += 1

        # Auto-verified tracking:
        # ReconAI auto-verifies exact_match, fee_adjusted, and verified delayed settlements (status != Human Review & status != Unresolved)
        is_auto_verified = (r["status"] in ["Exact Match", "Fee Match", "Probable Match"])
        if is_auto_verified:
            auto_verified_total += 1
            # A valid auto-verification must be truly in RECONCILED_CATS and have correct settlement
            if is_reconciled_gt and (gt_settlement == pred_settlement):
                true_auto_verified += 1
            else:
                false_auto_verified += 1
                false_auto_verified_records.append(r)

        if is_correct_classification:
            correct_classifications += 1
            cat_stats[exp_cat]["correct"] += 1
        else:
            incorrect_classifications += 1
            cat_stats[exp_cat]["wrong"] += 1
            misclassified.append({
                "invoice_id": inv_id,
                "expected_category": exp_cat,
                "predicted_category": pred_cat,
                "confidence": r["confidence_score"],
                "status": r["status"],
                "reason_evidence": r["evidence_json"],
                "is_auto_verified": is_auto_verified,
            })

    # Calculations
    # Match Precision = correctly reconciled / total predicted reconciled
    total_pred_reconciled = correctly_reconciled + incorrectly_reconciled
    match_precision = correctly_reconciled / total_pred_reconciled if total_pred_reconciled > 0 else 0.0

    # Match Recall = correctly reconciled / total ground truth reconciled
    total_gt_reconciled = correctly_reconciled + false_positive_exceptions
    match_recall = correctly_reconciled / total_gt_reconciled if total_gt_reconciled > 0 else 0.0

    classification_accuracy = correct_classifications / total_eligible if total_eligible > 0 else 0.0

    auto_verified_precision = true_auto_verified / auto_verified_total if auto_verified_total > 0 else 0.0

    overall_reconciliation_accuracy = (correctly_reconciled + correctly_identified_exceptions) / total_eligible if total_eligible > 0 else 0.0

    return {
        "run_id": run_id,
        "dataset_name": "Benchmark Synthetic Dataset",
        "total_eligible": total_eligible,
        "correctly_reconciled": correctly_reconciled,
        "incorrectly_reconciled": incorrectly_reconciled,
        "correctly_identified_exceptions": correctly_identified_exceptions,
        "missed_exceptions": missed_exceptions,
        "false_positive_exceptions": false_positive_exceptions,
        "match_precision": match_precision,
        "match_recall": match_recall,
        "classification_accuracy": classification_accuracy,
        "auto_verified_precision": auto_verified_precision,
        "overall_reconciliation_accuracy": overall_reconciliation_accuracy,
        "auto_verified_total": auto_verified_total,
        "true_auto_verified": true_auto_verified,
        "false_auto_verified": false_auto_verified,
        "false_auto_verified_records": false_auto_verified_records,
        "cat_stats": cat_stats,
        "misclassified": misclassified,
        "open_exceptions": latest_run["open_exception_count"],
    }


if __name__ == "__main__":
    report = evaluate_benchmark()
    print("=" * 80)
    print(f"BENCHMARK EVALUATION DETAILED ANALYSIS (Run: {report['run_id']})")
    print("=" * 80)
    print(f"1. Total eligible invoice records: {report['total_eligible']}")
    print(f"2. Correctly reconciled records: {report['correctly_reconciled']}")
    print(f"3. Incorrectly reconciled records: {report['incorrectly_reconciled']}")
    print(f"4. Correctly identified exceptions: {report['correctly_identified_exceptions']}")
    print(f"5. Missed exceptions: {report['missed_exceptions']}")
    print(f"6. False-positive exceptions: {report['false_positive_exceptions']}")
    print("-" * 80)
    print(f"Match Precision: {report['match_precision']:.4f} ({report['match_precision']:.2%})")
    print(f"Match Recall: {report['match_recall']:.4f} ({report['match_recall']:.2%})")
    print(f"Classification Accuracy: {report['classification_accuracy']:.4f} ({report['classification_accuracy']:.2%})")
    print(f"Auto-Verified Precision: {report['auto_verified_precision']:.4f} ({report['auto_verified_precision']:.2%})")
    print(f"Overall Reconciliation Accuracy: {report['overall_reconciliation_accuracy']:.4f} ({report['overall_reconciliation_accuracy']:.2%})")
    print(f"Incorrect Auto-Verifications: {report['false_auto_verified']}")
    print(f"Misclassified Records: {len(report['misclassified'])}")
    print(f"Open Exceptions: {report['open_exceptions']}")

    print("\n" + "=" * 80)
    print("PER-CATEGORY COMPARISON")
    print("=" * 80)
    print(f"{'Expected Category':<22} | {'Predicted Category':<22} | {'Count Correct':<14} | {'Count Wrong'}")
    print("-" * 80)
    for cat, data in report["cat_stats"].items():
        preds_summary = ", ".join([f"{k} ({v})" for k, v in data["predicted_categories"].items() if k != cat]) or cat
        print(f"{cat:<22} | {preds_summary:<22} | {data['correct']:<14} | {data['wrong']}")

    print("\n" + "=" * 80)
    print("MISCLASSIFIED INVOICES")
    print("=" * 80)
    if not report["misclassified"]:
        print("None! All 120 benchmark records were classified with 100% precision.")
    else:
        for m in report["misclassified"]:
            print(f"invoice_id: {m['invoice_id']}")
            print(f"expected_category: {m['expected_category']}")
            print(f"predicted_category: {m['predicted_category']}")
            print(f"confidence: {m['confidence']}")
            print(f"reason/evidence used by engine: {m['reason_evidence']}")
            print("-" * 80)

    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print(f"Dataset: {report['dataset_name']}")
    print(f"Records: {report['total_eligible']}")
    print(f"Match Precision: {report['match_precision']:.2%}")
    print(f"Match Recall: {report['match_recall']:.2%}")
    print(f"Classification Accuracy: {report['classification_accuracy']:.2%}")
    print(f"Auto-Verified Precision: {report['auto_verified_precision']:.2%}")
    print(f"Incorrect Auto-Verifications: {report['false_auto_verified']}")
    print(f"Misclassified Records: {len(report['misclassified'])}")
    print(f"Open Exceptions: {report['open_exceptions']}")
    print("=" * 80)
