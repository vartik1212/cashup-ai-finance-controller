"""
ReconAI — Finance Copilot Service Interface
===========================================
Conversational intelligence & investigation over reconciliation runs.
- In Data-only mode (default, no GEMINI_API_KEY):
  Answers queries deterministically using real financial database records.
- When GEMINI_API_KEY is configured:
  Uses official Google GenAI client (gemini-2.5-flash / configured model)
  with grounded system context and automatic graceful fallback.
"""

from __future__ import annotations

import re
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..database.db import get_db
from ..models.schemas import (
    CopilotRequest,
    CopilotResponse,
    ReconciliationRun,
    ReconciliationResult,
    ChatMessage,
)
from .gemini_client import (
    is_gemini_configured,
    generate_content_with_fallback,
    PRIMARY_MODEL,
)


class FinanceCopilotService:
    """
    Controller copilot providing context-aware analysis over reconciliation runs.
    """

    def get_run_context(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        with get_db() as conn:
            cur_ds = None
            if not run_id:
                try:
                    source_row = conn.execute(
                        "SELECT dataset_id, active_run_id FROM active_dataset_source WHERE id = 1"
                    ).fetchone()
                    run_id = source_row["active_run_id"] if (source_row and "active_run_id" in source_row.keys()) else None
                    cur_ds = source_row["dataset_id"] if (source_row and "dataset_id" in source_row.keys()) else None
                except Exception:
                    run_id = None
                    cur_ds = None
            else:
                try:
                    source_row = conn.execute(
                        "SELECT dataset_id FROM active_dataset_source WHERE id = 1"
                    ).fetchone()
                    cur_ds = source_row["dataset_id"] if (source_row and "dataset_id" in source_row.keys()) else None
                except Exception:
                    cur_ds = None

            if not run_id:
                return {"has_data": False}

            run_row = conn.execute(
                "SELECT * FROM reconciliation_runs WHERE run_id = ?", (run_id,)
            ).fetchone()

            if not run_row:
                return {"has_data": False}

            if cur_ds and run_row["dataset_id"] != cur_ds:
                return {"has_data": False}

            run = dict(run_row)
            rid = run["run_id"]

            exceptions_rows = conn.execute(
                """
                SELECT invoice_id, customer_name, invoice_amount, difference,
                       match_type, status, exception_category, system_assessment, recommendation
                FROM reconciliation_results
                WHERE run_id = ? AND status IN ('Unresolved', 'Human Review')
                ORDER BY invoice_amount DESC
                LIMIT 20
                """,
                (rid,),
            ).fetchall()

            delayed_rows = conn.execute(
                """
                SELECT invoice_id, customer_name, invoice_amount, days_delayed, settlement_id
                FROM reconciliation_results
                WHERE run_id = ? AND match_type = 'delayed_settlement'
                ORDER BY days_delayed DESC
                LIMIT 10
                """,
                (rid,),
            ).fetchall()

            largest_unresolved = conn.execute(
                """
                SELECT invoice_id, customer_name, invoice_amount, exception_category
                FROM reconciliation_results
                WHERE run_id = ? AND status = 'Unresolved'
                ORDER BY invoice_amount DESC LIMIT 1
                """,
                (rid,),
            ).fetchone()

            return {
                "has_data": True,
                "run": run,
                "exceptions": [dict(r) for r in exceptions_rows],
                "delayed_settlements": [dict(r) for r in delayed_rows],
                "largest_unresolved": dict(largest_unresolved) if largest_unresolved else None,
            }

    def _rule_based_response(self, message: str, ctx: dict) -> str:
        """Data-driven deterministic answers when Gemini is not connected."""
        msg = message.lower()

        if not ctx.get("has_data"):
            return (
                "No reconciliation run data is currently loaded. "
                "Please click **Load Demo** and **Run Reconciliation** first."
            )

        run = ctx["run"]
        exceptions = ctx.get("exceptions", [])

        if "how many" in msg and ("exception" in msg or "open" in msg):
            count = run.get("open_exception_count", len(exceptions))
            unresolved = run.get("unresolved", 0)
            review = run.get("human_review", 0)
            return (
                f"There are **{count} open exceptions** currently requiring attention:\n"
                f"- **{unresolved}** Unresolved transactions\n"
                f"- **{review}** Flagged for Human Review"
            )

        if "unresolved value" in msg or ("unresolved" in msg and "amount" in msg or "value" in msg and "unresolved" in msg):
            val = run.get("unresolved_amount", 0.0)
            return (
                f"The total unresolved value is **₹{val:,.2f}** across "
                f"**{run.get('unresolved', 0)}** unresolved transactions."
            )

        if "largest" in msg or "highest" in msg:
            lu = ctx.get("largest_unresolved")
            if lu:
                return (
                    f"The highest-value unresolved transaction is **{lu['invoice_id']}** "
                    f"({lu['customer_name']}) for **₹{lu['invoice_amount']:,.2f}**.\n"
                    f"- Exception Category: {lu['exception_category'] or 'Unresolved Discrepancy'}"
                )
            if exceptions:
                top = exceptions[0]
                return (
                    f"The highest-value open exception is **{top['invoice_id']}** "
                    f"({top['customer_name']}) for **₹{top['invoice_amount']:,.2f}**.\n"
                    f"- Exception Category: {top.get('exception_category', 'Human Review')}"
                )
            return "No open exceptions found in current run."

        if "delayed" in msg:
            delayed = ctx.get("delayed_settlements", [])
            if not delayed:
                return "No delayed settlements detected in the current run."
            lines = [
                f"- **{d['invoice_id']}** ({d['customer_name']}): ₹{d['invoice_amount']:,.2f} — delayed {d['days_delayed']} days (Settlement {d['settlement_id']})"
                for d in delayed[:5]
            ]
            return (
                f"**Delayed settlements ({len(delayed)} records exceeding 5-day SLA):**\n"
                + "\n".join(lines)
            )

        if "summar" in msg or "overview" in msg or "run" in msg and "report" in msg:
            return (
                f"**Reconciliation Run {run['run_id']} Summary**\n\n"
                f"- **Records Processed**: {run['records_processed']}\n"
                f"- **Match Rate**: {run['match_rate']*100:.1f}%\n"
                f"- **Verified Accuracy**: {run['verified_accuracy']*100:.1f}%\n"
                f"- **Exact Matches**: {run['exact_matches']}\n"
                f"- **Fee-Adjusted Matches**: {run['fee_matches']}\n"
                f"- **Probable/Delayed Matches**: {run.get('probable_matches', 0)}\n"
                f"- **Human Review Required**: {run['human_review']}\n"
                f"- **Unresolved**: {run['unresolved']}\n"
                f"- **Reconciled Value**: ₹{run['reconciled_amount']:,.2f}\n"
                f"- **Unresolved Value**: ₹{run['unresolved_amount']:,.2f}\n"
                f"- **Execution Time**: {run.get('processing_time_ms', 0):.0f}ms"
            )

        if "why" in msg and "unresolved" in msg or "reason" in msg:
            cats = {}
            for e in exceptions:
                c = e.get("exception_category") or "Amount Variance"
                cats[c] = cats.get(c, 0) + 1
            breakdown = "\n".join(f"- **{k}**: {v} cases" for k, v in sorted(cats.items()))
            return (
                f"Transactions are flagged or unresolved due to the following reasons:\n\n"
                f"{breakdown}"
            )

        if "exception" in msg or "attention" in msg or "immediate" in msg:
            if not exceptions:
                return "No open exceptions requiring attention."
            lines = [
                f"- **{e['invoice_id']}** ({e['customer_name']}): ₹{e['invoice_amount']:,.2f} — {e.get('exception_category') or 'Review'} ({e['status']})"
                for e in exceptions[:6]
            ]
            return (
                f"**Open Exceptions Requiring Attention ({len(exceptions)} total):**\n\n"
                + "\n".join(lines)
            )

        # Default fallback
        return (
            f"Active run `{run['run_id']}` is ready.\n\n"
            f"You can ask:\n"
            f"- *How many exceptions are open?*\n"
            f"- *What is the unresolved value?*\n"
            f"- *Show highest-value exceptions.*\n"
            f"- *Show delayed settlements.*\n"
            f"- *Summarize this reconciliation run.*"
        )

    def _extract_ids(self, text: str) -> List[str]:
        patterns = [
            r"INV-\d{4}-\d{4}",
            r"SET-\d{4}-\d{4}",
            r"PAY-\d{4}-\d{4}",
            r"BNK-\d{4}-\d{4}",
            r"RUN-[A-Z0-9]{8}",
        ]
        ids = []
        for pattern in patterns:
            ids.extend(re.findall(pattern, text))
        return list(dict.fromkeys(ids))

    async def handle_query(self, req: CopilotRequest) -> CopilotResponse:
        from .copilot_graph import run_copilot_pipeline
        return await run_copilot_pipeline(req.message, req.run_id, req.conversation_history)



copilot_service = FinanceCopilotService()
