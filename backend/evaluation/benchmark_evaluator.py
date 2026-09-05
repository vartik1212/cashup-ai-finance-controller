"""
ReconAI — Post-Reconciliation Benchmark Evaluator
================================================
Post-hoc evaluation layer strictly executed AFTER reconciliation finishes.
The matcher, verifier, and classifier NEVER have access to this module or its files.

Discovers if a hidden benchmark answer key matches the active invoice IDs:
- If a matching answer key is found: calculates exact classification accuracy,
  precision, recall, auto-verified precision, incorrect auto-verifications,
  and builds the misclassification list.
- If no answer key is found (e.g. standard uploaded financial data): returns None,
  preserving 'N/A (No Ground Truth)'.
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

try:
    from models.schemas import (
        ReconciliationResult,
        ScenarioPerformance,
        BenchmarkEvaluation,
        MisclassifiedRecord,
        MatchType,
        ReconciliationStatus,
    )
except ImportError:
    from backend.models.schemas import (
        ReconciliationResult,
        ScenarioPerformance,
        BenchmarkEvaluation,
        MisclassifiedRecord,
        MatchType,
        ReconciliationStatus,
    )

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
EVAL_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation"

RECONCILED_SCENARIOS = {"Exact Match", "Fee Adjusted", "Delayed Settlement"}
EXCEPTION_SCENARIOS = {
    "Partial Payment",
    "Duplicate",
    "Refund Discrepancy",
    "Refund",
    "Amount Mismatch",
    "Missing Settlement",
    "Ambiguous Match",
}


def canonicalize_scenario(scen: str) -> str:
    if not scen:
        return "Unknown"
    s = scen.strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "exact_match": "Exact Match",
        "exact": "Exact Match",
        "fee_adjusted": "Fee Adjusted",
        "fee_match": "Fee Adjusted",
        "delayed_settlement": "Delayed Settlement",
        "delayed": "Delayed Settlement",
        "partial_payment": "Partial Payment",
        "partial": "Partial Payment",
        "duplicate_payment": "Duplicate",
        "duplicate": "Duplicate",
        "refund": "Refund Discrepancy",
        "refund_discrepancy": "Refund Discrepancy",
        "amount_mismatch": "Amount Mismatch",
        "missing_settlement": "Missing Settlement",
        "ambiguous_match": "Ambiguous Match",
        "ambiguous": "Ambiguous Match",
    }
    return mapping.get(s, scen)


def map_prediction_to_scenario(res: ReconciliationResult) -> str:
    mt = res.match_type.value if hasattr(res.match_type, "value") else str(res.match_type)
    exc = res.exception_category.value if res.exception_category and hasattr(res.exception_category, "value") else (str(res.exception_category) if res.exception_category else None)
    status = res.status.value if hasattr(res.status, "value") else str(res.status)

    if exc == "Duplicate" or mt == "duplicate":
        return "Duplicate"
    if exc == "Partial Payment" or mt == "partial_payment":
        return "Partial Payment"
    if exc in ["Refund Discrepancy", "Refund"] or mt == "refund":
        return "Refund Discrepancy"
    if exc == "Amount Mismatch" or mt == "amount_mismatch":
        return "Amount Mismatch"
    if exc == "Missing Settlement" or (mt == "unresolved" and not res.settlement_id):
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


def find_ground_truth_for_invoices(
    invoice_ids: List[str],
    dataset_id: Optional[str] = None,
) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    STRICT DATASET OWNERSHIP ENFORCEMENT:
    Ground truth is ONLY returned when explicitly associated with dataset_id.
    Never retrieves benchmark ground truth globally.
    Never falls back to disk files or past answer keys for ordinary uploaded datasets.
    """
    if not invoice_ids or not dataset_id:
        return None

    # Retrieve strictly dataset-scoped ground truth from database
    try:
        try:
            from database.db import get_dataset_ground_truth
        except ImportError:
            from ..database.db import get_dataset_ground_truth
        records = get_dataset_ground_truth(dataset_id)
        if records:
            gt_map = {}
            for item in records:
                iid = item.get("invoice_id")
                if iid:
                    scen = item.get("scenario") or item.get("expected_scenario", "")
                    stat = item.get("expected_status") or item.get("status", "")
                    sid = item.get("settlement_id") or item.get("expected_settlement_id")
                    gt_map[iid] = {
                        "invoice_id": iid,
                        "expected_scenario": canonicalize_scenario(scen),
                        "expected_status": stat,
                        "expected_settlement_id": sid,
                    }
            return gt_map
    except Exception:
        pass

    # Benchmark dataset mode fallback strictly for "DATASET-BENCHMARK"
    if dataset_id == "DATASET-BENCHMARK":
        candidate_paths = [
            DATA_DIR / "ground_truth.json",
            DATA_DIR / "ground_truth.csv",
        ]
        for path in candidate_paths:
            if not path.exists():
                continue
            gt_by_id: Dict[str, Dict[str, Any]] = {}
            try:
                if path.suffix.lower() == ".json":
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for item in data:
                            iid = item.get("invoice_id")
                            if iid:
                                gt_by_id[iid] = {
                                    "invoice_id": iid,
                                    "expected_scenario": canonicalize_scenario(item.get("scenario", "")),
                                    "expected_status": item.get("expected_status", ""),
                                    "expected_settlement_id": item.get("settlement_id"),
                                }
                elif path.suffix.lower() == ".csv":
                    with open(path, "r", encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            iid = row.get("invoice_id")
                            if iid:
                                gt_by_id[iid] = {
                                    "invoice_id": iid,
                                    "expected_scenario": canonicalize_scenario(row.get("scenario", "")),
                                    "expected_status": row.get("expected_status", ""),
                                    "expected_settlement_id": row.get("settlement_id"),
                                }
                if gt_by_id:
                    return gt_by_id
            except Exception:
                continue

    return None


def evaluate_benchmark_run(
    results: List[ReconciliationResult],
    gt_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluates actual predictions against the isolated answer key.
    Calculates:
    - classification_accuracy
    - match_precision
    - match_recall
    - auto_verified_precision
    - incorrect_auto_verifications
    - misclassified_records
    - scenario_performance
    """
    total_records = len(results)
    correct_classifications = 0
    incorrect_classifications = 0
    misclassified_records: List[MisclassifiedRecord] = []

    # Scenario breakdown tracking
    scenario_totals = defaultdict(int)
    scenario_correct = defaultdict(int)

    # Reconciled vs Exception tracking
    tp = 0  # GT Reconciled & Pred Reconciled
    fp = 0  # GT Exception & Pred Reconciled
    fn = 0  # GT Reconciled & Pred Exception
    tn = 0  # GT Exception & Pred Exception

    # Auto-verified tracking
    auto_verified_count = 0
    true_auto_verified = 0

    for r in results:
        gt = gt_map.get(r.invoice_id)
        if not gt:
            continue

        expected_scenario = gt["expected_scenario"]
        predicted_scenario = map_prediction_to_scenario(r)
        status_val = r.status.value if hasattr(r.status, "value") else str(r.status)

        scenario_totals[expected_scenario] += 1

        is_correct = (expected_scenario == predicted_scenario)
        r.ground_truth_scenario = expected_scenario
        r.is_correct_prediction = is_correct

        if is_correct:
            correct_classifications += 1
            scenario_correct[expected_scenario] += 1
        else:
            incorrect_classifications += 1
            misclassified_records.append(
                MisclassifiedRecord(
                    invoice_id=r.invoice_id,
                    expected=expected_scenario,
                    predicted=predicted_scenario,
                    confidence=r.confidence_score,
                    status=status_val,
                )
            )

        # Reconciled tracking
        gt_is_reconciled = expected_scenario in RECONCILED_SCENARIOS
        pred_is_reconciled = predicted_scenario in RECONCILED_SCENARIOS

        if gt_is_reconciled and pred_is_reconciled:
            tp += 1
        elif not gt_is_reconciled and pred_is_reconciled:
            fp += 1
        elif gt_is_reconciled and not pred_is_reconciled:
            fn += 1
        else:
            tn += 1

        # Auto-verified tracking
        # Exact Match, Fee Match, and Probable Match are auto-verified
        mt_val = r.match_type.value if hasattr(r.match_type, "value") else str(r.match_type)
        if mt_val in ["exact_match", "fee_adjusted"] or status_val in ["Exact Match", "Fee Match"]:
            auto_verified_count += 1
            if gt_is_reconciled and (expected_scenario in ["Exact Match", "Fee Adjusted"]):
                true_auto_verified += 1

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    accuracy = round(correct_classifications / total_records, 4) if total_records > 0 else 0.0
    auto_verified_precision = (
        round(true_auto_verified / auto_verified_count, 4) if auto_verified_count > 0 else 0.0
    )
    incorrect_auto_verifications = auto_verified_count - true_auto_verified

    # Build scenario performance list
    scenario_performance: List[ScenarioPerformance] = []
    for sc, tot in sorted(scenario_totals.items()):
        corr = scenario_correct[sc]
        acc = round(corr / tot, 4) if tot > 0 else 0.0
        scenario_performance.append(
            ScenarioPerformance(
                scenario=sc,
                total_cases=tot,
                correctly_identified=corr,
                accuracy=acc,
            )
        )

    benchmark_eval = BenchmarkEvaluation(
        total_records=total_records,
        correct_classifications=correct_classifications,
        incorrect_classifications=incorrect_classifications,
        precision=precision,
        recall=recall,
        classification_accuracy=accuracy,
        auto_verified_precision=auto_verified_precision,
        incorrect_auto_verifications=incorrect_auto_verifications,
        misclassified_records=misclassified_records,
    )

    return {
        "classification_accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "auto_verified_precision": auto_verified_precision,
        "incorrect_auto_verifications": incorrect_auto_verifications,
        "scenario_performance": scenario_performance,
        "benchmark_evaluation": benchmark_eval,
    }
