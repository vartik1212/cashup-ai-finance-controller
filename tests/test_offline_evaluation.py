"""
Offline Evaluation Test Suite
============================
Ensures offline evaluation runs deterministically against the hidden ground truth
without altering or leaking into production ingestion or reconciliation workflows.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from evaluation.evaluate_baseline import run_offline_evaluation


def test_offline_baseline_evaluation():
    metrics = run_offline_evaluation()

    assert metrics["total_cases"] == 60
    assert metrics["correct_classifications"] == 51
    assert metrics["incorrect_classifications"] == 9
    assert metrics["classification_accuracy"] == 0.85
    assert metrics["false_auto_verified"] == 9
    assert metrics["false_unresolved"] == 0

    # Verify per-category totals match the expected 60-case distribution
    expected_totals = {
        "Exact Match": 30,
        "Fee Adjusted": 8,
        "Delayed Settlement": 5,
        "Partial Payment": 4,
        "Refund": 3,
        "Duplicate": 3,
        "Amount Mismatch": 3,
        "Missing Settlement": 2,
        "Ambiguous Match": 2,
    }
    category_totals = {
        k: v["total"] for k, v in metrics["per_category_results"].items()
    }
    assert category_totals == expected_totals
