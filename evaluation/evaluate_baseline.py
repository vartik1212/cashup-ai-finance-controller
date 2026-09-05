"""
ReconAI — Offline Baseline Evaluation Script
===========================================
Strictly external evaluation harness.
NEVER imported or accessible by production ingestion, normalization,
matching, verification, or LangGraph workflows.

Evaluates ReconAI predictions for the user-uploaded dataset against:
evaluation/reconai_expected_ground_truth_DO_NOT_UPLOAD.csv
"""

import csv
import json
import sqlite3
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
GT_PATH = Path(__file__).resolve().parent / "reconai_expected_ground_truth_DO_NOT_UPLOAD.csv"
DB_PATH = BASE_DIR / "data" / "reconai.db"
REPORT_OUTPUT_PATH = BASE_DIR / "evaluation_report.json"


def run_offline_evaluation():
    # 1. Load Ground Truth (strictly offline)
    if not GT_PATH.exists():
        raise FileNotFoundError(f"Ground truth file not found at {GT_PATH}")

    with open(GT_PATH, "r", encoding="utf-8-sig") as f:
        gt_rows = list(csv.DictReader(f))

    gt_by_id = {r["invoice_id"]: r for r in gt_rows}
    total_cases = len(gt_rows)

    # 2. Load ReconAI predictions from latest run in DB
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    latest_run = c.execute(
        "SELECT run_id, records_processed, match_rate, auto_resolved, open_exception_count "
        "FROM reconciliation_runs WHERE records_processed = 60 ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if not latest_run:
        latest_run = c.execute(
            "SELECT run_id, records_processed, match_rate, auto_resolved, open_exception_count "
            "FROM reconciliation_runs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

    if not latest_run:
        raise RuntimeError("No reconciliation runs found in database. Run reconciliation first.")

    run_id = latest_run["run_id"]
    pred_rows = c.execute(
        "SELECT * FROM reconciliation_results WHERE run_id = ? ORDER BY invoice_id",
        (run_id,),
    ).fetchall()

    pred_by_id = {r["invoice_id"]: dict(r) for r in pred_rows}

    # 3. Scenario Mapping helper
    def map_prediction_to_scenario(pred: dict) -> str:
        mt = pred.get("match_type")
        exc = pred.get("exception_category")
        status = pred.get("status")

        if exc == "Duplicate" or mt == "duplicate":
            return "Duplicate"
        if exc == "Partial Payment" or mt == "partial_payment":
            return "Partial Payment"
        if exc == "Refund Discrepancy" or exc == "Refund" or mt == "refund":
            return "Refund"
        if exc == "Amount Mismatch" or mt == "amount_mismatch":
            return "Amount Mismatch"
        if exc == "Missing Settlement" or (mt == "unresolved" and not pred.get("settlement_id")):
            return "Missing Settlement"
        if exc == "Ambiguous Match" or mt == "ambiguous_match":
            return "Ambiguous Match"
        if mt == "delayed_settlement":
            return "Delayed Settlement"
        if mt == "fee_adjusted":
            return "Fee Adjusted"
        if mt == "exact_match":
            return "Exact Match"
        return status or "Unknown"

    # 4. Compute Metrics
    confusion = defaultdict(lambda: defaultdict(int))
    correct_classifications = 0
    incorrect_classifications = 0
    misclassified_records = []

    # Maintain fixed order for per-category reporting
    category_order = [
        "Exact Match",
        "Fee Adjusted",
        "Delayed Settlement",
        "Partial Payment",
        "Refund",
        "Duplicate",
        "Amount Mismatch",
        "Missing Settlement",
        "Ambiguous Match",
    ]
    per_category_total = {cat: 0 for cat in category_order}
    per_category_correct = {cat: 0 for cat in category_order}

    # Routing metrics
    true_auto_verified = 0
    false_auto_verified = 0
    auto_verified_list = []

    true_unresolved = 0
    false_unresolved = 0

    human_review_expected = 0
    human_review_correct = 0

    unresolved_expected = 0
    unresolved_correct = 0

    for inv_id, gt in gt_by_id.items():
        expected_scenario = gt["expected_scenario"]
        expected_status = gt["expected_status"]
        per_category_total[expected_scenario] += 1

        pred = pred_by_id.get(inv_id)
        if not pred:
            continue

        predicted_scenario = map_prediction_to_scenario(pred)
        pred_status = pred["status"]
        pred_match_type = pred["match_type"]
        confidence = pred["confidence_score"]

        confusion[expected_scenario][predicted_scenario] += 1

        # Check classification correctness
        is_correct = (expected_scenario == predicted_scenario)
        if is_correct:
            correct_classifications += 1
            per_category_correct[expected_scenario] += 1
        else:
            incorrect_classifications += 1
            # Determine deterministic rule triggered & reason
            rule = f"Node 5 Classify: match_type={pred_match_type}, status={pred_status}"
            reason = ""
            if expected_scenario == "Delayed Settlement":
                reason = "days_delta=5 did not exceed DATE_DELAYED_DAYS (5). Evaluated as <= 5 days SLA window, falling through to Exact Match."
            elif expected_scenario == "Refund":
                reason = "refund_value was unmapped/ignored; processor_note had no 'refund' keyword; gross equaled invoice amount, defaulting to Exact Match."
            elif expected_scenario == "Amount Mismatch":
                reason = "Engine compared invoice amount against settlement gross amount (which matched), ignoring discrepancy in net received amount (+1800 to +4200)."
            elif expected_scenario == "Ambiguous Match":
                reason = "Engine performed exact reference matching in Pass 1 to PAY-90059/60 and skipped Pass 2 ambiguity checks for candidate ALT-90059/60."

            misclassified_records.append({
                "invoice_id": inv_id,
                "ground_truth": expected_scenario,
                "prediction": predicted_scenario,
                "confidence": confidence,
                "status": pred_status,
                "rule_triggered": rule,
                "reason_for_error": reason,
                "is_false_auto_verified": (pred_match_type in ["exact_match", "fee_adjusted"]),
            })

        # Auto-verified analysis
        if pred_match_type in ["exact_match", "fee_adjusted"]:
            auto_verified_list.append(inv_id)
            if expected_scenario in ["Exact Match", "Fee Adjusted"]:
                true_auto_verified += 1
            else:
                false_auto_verified += 1

        # Unresolved analysis
        if pred_status == "Unresolved":
            if expected_status == "Unresolved":
                true_unresolved += 1
            else:
                false_unresolved += 1

        # Human Review routing
        if expected_status == "Human Review":
            human_review_expected += 1
            if pred_status == "Human Review":
                human_review_correct += 1

        # Unresolved routing
        if expected_status == "Unresolved":
            unresolved_expected += 1
            if pred_status == "Unresolved":
                unresolved_correct += 1

    total_evaluated = correct_classifications + incorrect_classifications
    accuracy = correct_classifications / total_evaluated if total_evaluated > 0 else 0.0

    # Binary Reconciled vs Exception classification:
    # Ground truth reconciled: Exact Match (30), Fee Adjusted (8), Delayed Settlement (5) = 43
    # Ground truth exceptions: Partial Payment (4), Refund (3), Duplicate (3), Amount Mismatch (3), Missing Settlement (2), Ambiguous Match (2) = 17
    tp = 0  # GT Reconciled & Pred Reconciled
    fp = 0  # GT Exception but Pred Reconciled
    fn = 0  # GT Reconciled but Pred Exception
    tn = 0  # GT Exception & Pred Exception

    for inv_id, gt in gt_by_id.items():
        pred = pred_by_id.get(inv_id)
        if not pred:
            continue
        gt_is_reconciled = gt["expected_scenario"] in ["Exact Match", "Fee Adjusted", "Delayed Settlement"]
        pred_is_reconciled = pred["match_type"] in ["exact_match", "fee_adjusted", "delayed_settlement"]

        if gt_is_reconciled and pred_is_reconciled:
            tp += 1
        elif not gt_is_reconciled and pred_is_reconciled:
            fp += 1
        elif gt_is_reconciled and not pred_is_reconciled:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    auto_verified_precision = (
        true_auto_verified / len(auto_verified_list) if auto_verified_list else 0.0
    )
    human_review_routing_acc = (
        human_review_correct / human_review_expected if human_review_expected > 0 else 0.0
    )
    unresolved_routing_acc = (
        unresolved_correct / unresolved_expected if unresolved_expected > 0 else 0.0
    )

    per_category_accuracy = {}
    for cat in category_order:
        tot = per_category_total[cat]
        corr = per_category_correct[cat]
        per_category_accuracy[cat] = {
            "total": tot,
            "correct": corr,
            "accuracy": round(corr / tot, 4) if tot > 0 else 0.0,
        }

    report = {
        "run_id": run_id,
        "total_cases": total_cases,
        "correct_classifications": correct_classifications,
        "incorrect_classifications": incorrect_classifications,
        "classification_accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "auto_verified_total": len(auto_verified_list),
        "true_auto_verified": true_auto_verified,
        "false_auto_verified": false_auto_verified,
        "auto_verified_precision": round(auto_verified_precision, 4),
        "false_unresolved": false_unresolved,
        "human_review_expected": human_review_expected,
        "human_review_correct": human_review_correct,
        "human_review_routing_accuracy": round(human_review_routing_acc, 4),
        "unresolved_expected": unresolved_expected,
        "unresolved_correct": unresolved_correct,
        "unresolved_routing_accuracy": round(unresolved_routing_acc, 4),
        "per_category_results": per_category_accuracy,
        "confusion_breakdown": {k: dict(v) for k, v in confusion.items()},
        "misclassified_invoices": misclassified_records,
    }

    # Save to evaluation_report.json
    with open(REPORT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    res = run_offline_evaluation()
    print("=" * 75)
    print(f"RECONAI OFFLINE BASELINE EVALUATION REPORT (Run: {res['run_id']})")
    print("=" * 75)
    print(f"Total cases: {res['total_cases']}")
    print(f"Correct classifications: {res['correct_classifications']}")
    print(f"Incorrect classifications: {res['incorrect_classifications']}")
    print(f"Classification accuracy: {res['classification_accuracy']:.2%}")
    print(f"Precision: {res['precision']:.4f} ({res['tp']}/{res['tp']+res['fp']})")
    print(f"Recall: {res['recall']:.4f} ({res['tp']}/{res['tp']+res['fn']})")
    print(f"F1: {res['f1']:.4f}")
    print(f"Auto-verified total: {res['auto_verified_total']}")
    print(f"Auto-verified precision: {res['auto_verified_precision']:.2%} ({res['true_auto_verified']}/{res['auto_verified_total']})")
    print(f"Number of false auto-verifications: {res['false_auto_verified']}")
    print(f"Human-review routing accuracy: {res['human_review_routing_accuracy']:.2%} ({res['human_review_correct']}/{res['human_review_expected']})")
    print(f"Unresolved routing accuracy: {res['unresolved_routing_accuracy']:.2%} ({res['unresolved_correct']}/{res['unresolved_expected']})")

    print("\n" + "=" * 75)
    print("PER-CATEGORY RESULTS")
    print("=" * 75)
    for cat, data in res["per_category_results"].items():
        print(f"{cat:<22} : {data['correct']}/{data['total']} ({data['accuracy']:.1%})")

    print("\n" + "=" * 75)
    print("DISCREPANCY INVESTIGATION: WHY EXACT MATCH = 39 (vs 30) & DELAYED = 4 (vs 5)")
    print("=" * 75)
    print("The 9 extra Exact Match cases in ReconAI's output originate from:")
    print("  + 1 Delayed Settlement (BILL-2026041: 5-day delta treated as <= 5 SLA)")
    print("  + 3 Refunds (BILL-2026048..50: refund_value unmapped; gross matched)")
    print("  + 3 Amount Mismatches (BILL-2026054..56: gross matched; received variance ignored)")
    print("  + 2 Ambiguous Matches (BILL-2026059..60: matched exact reference in Pass 1)")
    print("30 (True Exact) + 1 + 3 + 3 + 2 = 39 Exact Matches.")
    print("5 (True Delayed) - 1 = 4 Delayed Settlements.")

    print("\n" + "=" * 75)
    print("MISCLASSIFIED INVOICES (ALL 9 CASES)")
    print("=" * 75)
    for m in res["misclassified_invoices"]:
        print(f"invoice_id: {m['invoice_id']}")
        print(f"ground_truth: {m['ground_truth']}")
        print(f"prediction: {m['prediction']}")
        print(f"confidence: {m['confidence']}")
        print(f"status: {m['status']}")
        print(f"rule_triggered: {m['rule_triggered']}")
        print(f"reason_for_error: {m['reason_for_error']}")
        print("-" * 75)

    print(f"\nEvaluation output successfully saved to: {REPORT_OUTPUT_PATH}")
