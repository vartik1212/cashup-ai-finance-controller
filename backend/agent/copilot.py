"""
ReconAI — AI Copilot (LangGraph + Gemini stub)

Architecture is established. Gemini integration added when API key is present.
Falls back gracefully when no key is configured.
"""

from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Optional

try:
    from models.schemas import CopilotRequest, CopilotResponse
    from database.db import get_db
except (ImportError, ValueError):
    from ..models.schemas import CopilotRequest, CopilotResponse
    from ..database.db import get_db


async def get_copilot_response(req: CopilotRequest) -> CopilotResponse:
    """
    Main copilot entry point.
    1. Queries reconciliation data from SQLite deterministically.
    2. If Gemini API key is present, uses Gemini to generate natural language.
    3. If no key, returns a structured data-driven answer without AI.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    ai_available = bool(api_key)

    # Always fetch real data — never fabricate
    context_data = _fetch_context(req.run_id)

    if not ai_available:
        answer = _rule_based_response(req.message, context_data)
        return CopilotResponse(
            message=answer,
            ai_available=False,
            referenced_ids=_extract_ids(answer),
            error=None,
        )

    # --- Gemini integration (activated when GEMINI_API_KEY is set) ---
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=_build_system_prompt(context_data),
        )

        history = [
            {"role": msg.role, "parts": [msg.content]}
            for msg in req.conversation_history[-10:]
        ]

        chat = model.start_chat(history=history)
        response = chat.send_message(req.message)
        answer = response.text

        return CopilotResponse(
            message=answer,
            ai_available=True,
            referenced_ids=_extract_ids(answer),
        )

    except Exception as e:
        fallback = _rule_based_response(req.message, context_data)
        return CopilotResponse(
            message=fallback,
            ai_available=False,
            error=f"AI unavailable: {str(e)}",
            referenced_ids=_extract_ids(fallback),
        )


def _fetch_context(run_id: Optional[str]) -> dict:
    """Fetch real reconciliation data for context. Deterministic."""
    try:
        with get_db() as conn:
            if run_id:
                run_row = conn.execute(
                    "SELECT * FROM reconciliation_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
            else:
                run_row = conn.execute(
                    "SELECT * FROM reconciliation_runs ORDER BY timestamp DESC LIMIT 1"
                ).fetchone()

            if not run_row:
                return {"has_data": False}

            run = dict(run_row)
            rid = run["run_id"]

            # Exceptions
            exceptions = conn.execute("""
                SELECT invoice_id, customer_name, invoice_amount, difference,
                       exception_category, confidence_score, status, system_assessment
                FROM reconciliation_results
                WHERE run_id = ? AND status IN ('Unresolved', 'Human Review')
                ORDER BY invoice_amount DESC
                LIMIT 20
            """, (rid,)).fetchall()

            # Largest unresolved
            largest = conn.execute("""
                SELECT invoice_id, customer_name, invoice_amount, exception_category
                FROM reconciliation_results
                WHERE run_id = ? AND status = 'Unresolved'
                ORDER BY invoice_amount DESC LIMIT 1
            """, (rid,)).fetchone()

            # Delayed settlements
            delayed = conn.execute("""
                SELECT invoice_id, customer_name, invoice_amount, days_delayed
                FROM reconciliation_results
                WHERE run_id = ? AND match_type = 'delayed_settlement'
                ORDER BY days_delayed DESC LIMIT 10
            """, (rid,)).fetchall()

        return {
            "has_data": True,
            "run": run,
            "exceptions": [dict(r) for r in exceptions],
            "largest_unresolved": dict(largest) if largest else None,
            "delayed_settlements": [dict(r) for r in delayed],
        }
    except Exception:
        return {"has_data": False}


def _build_system_prompt(ctx: dict) -> str:
    """Build a system prompt grounded in real reconciliation data."""
    if not ctx.get("has_data"):
        return (
            "You are ReconAI Finance Copilot. No reconciliation data is currently loaded. "
            "Ask the user to run a reconciliation first. Never fabricate financial data."
        )

    run = ctx["run"]
    exceptions_summary = "\n".join(
        f"- {e['invoice_id']}: {e['customer_name']} ₹{e['invoice_amount']:,.0f} — {e['exception_category']} ({e['status']})"
        for e in ctx["exceptions"][:10]
    )

    return f"""You are ReconAI Finance Copilot, an expert financial reconciliation assistant.

CURRENT RECONCILIATION RUN: {run['run_id']}
Timestamp: {run['timestamp']}
Records Processed: {run['records_processed']}
Match Rate: {run['match_rate']*100:.1f}%
Verified Accuracy: {run['verified_accuracy']*100:.1f}%
Exact Matches: {run['exact_matches']}
Fee Matches: {run['fee_matches']}
Unresolved: {run['unresolved']}
Reconciled Amount: ₹{run['reconciled_amount']:,.2f}
Unresolved Amount: ₹{run['unresolved_amount']:,.2f}

TOP EXCEPTIONS (by value):
{exceptions_summary}

RULES:
- Only reference real transaction IDs and amounts from the data above.
- Never fabricate amounts, IDs, or match results.
- Be precise and professional in your financial analysis.
- If asked about data not in your context, say so clearly.
"""


def _rule_based_response(message: str, ctx: dict) -> str:
    """Structured answers without LLM. Data-driven."""
    msg = message.lower()

    if not ctx.get("has_data"):
        return (
            "No reconciliation data is currently available. "
            "Please load the demo dataset and run a reconciliation first."
        )

    run = ctx["run"]

    if "unresolved" in msg and "largest" in msg:
        lu = ctx.get("largest_unresolved")
        if lu:
            return (
                f"The largest unresolved transaction is **{lu['invoice_id']}** "
                f"({lu['customer_name']}) for ₹{lu['invoice_amount']:,.2f}. "
                f"Exception category: {lu['exception_category'] or 'Missing Settlement'}."
            )
        return "No unresolved transactions found in the current run."

    if "delayed" in msg:
        delayed = ctx.get("delayed_settlements", [])
        if not delayed:
            return "No delayed settlements detected in the current run."
        lines = [f"- {d['invoice_id']}: {d['customer_name']} ₹{d['invoice_amount']:,.2f} — delayed {d['days_delayed']} days" for d in delayed[:5]]
        return f"**Delayed settlements ({len(delayed)} found):**\n" + "\n".join(lines)

    if "summar" in msg or "overview" in msg:
        return (
            f"**Run {run['run_id']} Summary**\n\n"
            f"- Records processed: {run['records_processed']}\n"
            f"- Match rate: {run['match_rate']*100:.1f}%\n"
            f"- Verified accuracy: {run['verified_accuracy']*100:.1f}%\n"
            f"- Exact matches: {run['exact_matches']}\n"
            f"- Fee-adjusted matches: {run['fee_matches']}\n"
            f"- Human review required: {run['human_review']}\n"
            f"- Unresolved: {run['unresolved']}\n"
            f"- Reconciled amount: ₹{run['reconciled_amount']:,.2f}\n"
            f"- Unresolved amount: ₹{run['unresolved_amount']:,.2f}\n"
            f"- Processing time: {run['processing_time_ms']:.0f}ms"
        )

    if "unresolved" in msg and ("count" in msg or "how many" in msg or "total" in msg or "amount" in msg):
        unres = run.get("unresolved", 0)
        unres_amt = run.get("unresolved_amount", 0.0)
        return f"There are currently {unres} unresolved transactions totaling ₹{unres_amt:,.2f}."

    if "exception" in msg or "attention" in msg or "immediate" in msg:
        exc = ctx.get("exceptions", [])
        if not exc:
            return f"No open unresolved exceptions currently require attention. (Unresolved: {run.get('unresolved', 0)})"
        lines = [
            f"- **{e['invoice_id']}** ({e['customer_name']}): ₹{e['invoice_amount']:,.2f} — {e['exception_category']} [confidence: {e['confidence_score']:.0%}]"
            for e in exc[:8]
        ]
        return f"**{len(exc)} exceptions requiring attention:**\n" + "\n".join(lines)

    if "why" in msg and "unresolved" in msg:
        exc = ctx.get("exceptions", [])
        categories = {}
        for e in exc:
            cat = e.get("exception_category", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1
        if not categories:
            return "No unresolved transactions found."
        breakdown = "\n".join(f"- {cat}: {count}" for cat, count in sorted(categories.items()))
        return f"Transactions are unresolved for the following reasons:\n{breakdown}"

    # Default
    return (
        f"I can answer questions about the current reconciliation run ({run['run_id']}). "
        f"Try asking: 'Summarize this run', 'What is our largest unresolved transaction?', "
        f"or 'Which exceptions require immediate attention?'\n\n"
        f"*Note: AI Copilot is operating in data-only mode. Configure GEMINI_API_KEY for full AI analysis.*"
    )


def _extract_ids(text: str) -> list:
    """Extract referenced transaction IDs from response text."""
    import re
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
    return list(set(ids))
