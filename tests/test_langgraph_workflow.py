"""
ReconAI — LangGraph Workflow Unit Tests
====================================
Validates stateful LangGraph orchestration pipeline:
- Graph compilation
- Full end-to-end execution across demo dataset
- Conditional routing behavior
- Execution trace & ground truth precision/recall verification
"""

import sys
import unittest
import json
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.workflow.reconciliation_graph import (
    reconciliation_graph,
    build_reconciliation_graph,
    ingest_node,
    normalize_node,
    match_node,
    verify_node,
    classify_node,
    exception_investigator_node,
    report_node,
)
from backend.models.schemas import (
    Invoice,
    Settlement,
    BankTransaction,
    ReconciliationStatus,
    MatchType,
)


def _load_demo_data():
    data_dir = Path(__file__).parent.parent / "data"
    with open(data_dir / "invoices.json", "r", encoding="utf-8") as f:
        invs = json.load(f)
    with open(data_dir / "settlements.json", "r", encoding="utf-8") as f:
        sets = json.load(f)
    with open(data_dir / "bank_transactions.json", "r", encoding="utf-8") as f:
        bnks = json.load(f)
    with open(data_dir / "ground_truth.json", "r", encoding="utf-8") as f:
        gt = json.load(f)
    return invs, sets, bnks, gt


class TestLangGraphCompilation(unittest.TestCase):
    def test_graph_compiles(self):
        graph = build_reconciliation_graph()
        self.assertIsNotNone(graph)
        self.assertTrue(hasattr(graph, "invoke"))


class TestLangGraphExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.invs, cls.sets, cls.bnks, cls.gt = _load_demo_data()

    def test_full_pipeline_execution(self):
        state = {
            "run_id": "TEST-RUN-LANGGRAPH-01",
            "raw_invoices": self.invs,
            "raw_settlements": self.sets,
            "raw_bank_transactions": self.bnks,
            "ground_truth_records": self.gt,
        }

        output = reconciliation_graph.invoke(state)

        self.assertIn("run_summary", output)
        run = output["run_summary"]
        results = output["reconciliation_results"]
        trace = output["trace"]

        nodes = [t.node for t in trace]
        expected_nodes = [
            "INGEST",
            "NORMALIZE",
            "MATCH",
            "VERIFY",
            "CLASSIFY",
            "EXCEPTION_ANALYSIS",
            "REPORT",
        ]
        for node in expected_nodes:
            self.assertIn(
                node,
                nodes,
                f"Expected node {node} was not found in execution trace!",
            )

        for t in trace:
            self.assertGreaterEqual(t.duration_ms, 0.0)
            self.assertEqual(t.status, "completed")

        for r in results:
            self.assertGreaterEqual(r.confidence_score, 0.0)
            self.assertLessEqual(r.confidence_score, 1.0)

        expected_exceptions = run.human_review + run.unresolved
        self.assertEqual(run.open_exception_count, expected_exceptions)
        self.assertEqual(run.open_exception_count, 35)

        reconciled = run.exact_matches + run.fee_matches + run.probable_matches
        self.assertAlmostEqual(
            run.match_rate,
            reconciled / run.records_processed,
            places=3,
        )

        self.assertEqual(run.verified_accuracy, 1.0)
        self.assertEqual(run.precision, 1.0)
        self.assertEqual(run.recall, 1.0)

    def test_conditional_routing_without_exceptions(self):
        exact_invs = [
            inv for inv in self.invs if inv.get("ground_truth_scenario") == "exact_match"
        ][:3]
        exact_sets = [
            s
            for s in self.sets
            if s.get("invoice_reference") in [inv["invoice_id"] for inv in exact_invs]
        ]

        state = {
            "run_id": "TEST-NO-EXC",
            "raw_invoices": exact_invs,
            "raw_settlements": exact_sets,
            "raw_bank_transactions": self.bnks,
            "ground_truth_records": [],
        }

        output = reconciliation_graph.invoke(state)
        nodes = [t.node for t in output["trace"]]

        self.assertIn("REPORT", nodes)
        self.assertNotIn("EXCEPTION_ANALYSIS", nodes)


if __name__ == "__main__":
    unittest.main()
