"""
ReconAI — Finance Copilot LangGraph Workflow
============================================
Stateful pipeline ensuring all AI answers are strictly grounded in
verified reconciliation records:
understand_query
→ select_finance_tool
→ retrieve_real_data
→ generate_answer
→ validate_answer
→ END
"""

from __future__ import annotations

import re
import json
import logging
from typing import Dict, Any, List, Optional, TypedDict
from langgraph.graph import StateGraph, END

try:
    from models.schemas import CopilotResponse, ChatMessage
except (ImportError, ValueError):
    from ..models.schemas import CopilotResponse, ChatMessage
from .gemini_client import is_gemini_configured, generate_content_with_fallback, PRIMARY_MODEL
from .finance_tools import (
    get_run_summary,
    get_open_exceptions,
    get_exception_by_invoice,
    get_reconciliation_by_invoice,
    get_exceptions_by_category,
    get_low_confidence_records,
    get_high_value_exceptions,
    get_delayed_settlements,
    get_unresolved_amount,
    get_execution_trace,
)

logger = logging.getLogger("reconai.copilot_graph")


class CopilotState(TypedDict):
    query: str
    run_id: Optional[str]
    conversation_history: List[Dict[str, str]]
    intent: str
    target_invoice_id: Optional[str]
    target_category: Optional[str]
    selected_tool: str
    tool_args: Dict[str, Any]
    retrieved_data: Any
    invoice_found: Optional[bool]
    raw_answer: str
    final_answer: str
    referenced_ids: List[str]
    ai_used: bool


# ---------------------------------------------------------------------------
# Node 1: Understand Query
# ---------------------------------------------------------------------------

def understand_query_node(state: CopilotState) -> Dict[str, Any]:
    query = state.get("query", "").strip()
    q_lower = query.lower()

    # Search for invoice IDs
    id_pattern = r"\b(?:BILL|INV|SET|PAY|BNK|RES)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b"
    found_ids = re.findall(id_pattern, query, re.IGNORECASE)
    target_id = found_ids[0].upper() if found_ids else None

    # Check for categories
    target_cat = None
    if "duplicate" in q_lower:
        target_cat = "Duplicate"
    elif "partial" in q_lower:
        target_cat = "Partial Payment"
    elif "refund" in q_lower:
        target_cat = "Refund"
    elif "missing" in q_lower:
        target_cat = "Missing Settlement"
    elif "mismatch" in q_lower or "variance" in q_lower:
        target_cat = "Amount Mismatch"
    elif "ambiguous" in q_lower:
        target_cat = "Ambiguous Match"

    # Classify intent
    if target_id:
        intent = "SPECIFIC_INVOICE"
    elif ("unresolved" in q_lower or "outstanding" in q_lower) and ("amount" in q_lower or "value" in q_lower or "worth" in q_lower):
        intent = "UNRESOLVED_AMOUNT"
    elif "delayed" in q_lower or "late" in q_lower or "sla" in q_lower:
        intent = "DELAYED_SETTLEMENTS"
    elif "highest" in q_lower or "largest" in q_lower or "biggest" in q_lower or "top exception" in q_lower:
        intent = "HIGH_VALUE_EXCEPTIONS"
    elif "review first" in q_lower or "priority" in q_lower or "risk" in q_lower:
        intent = "PRIORITY_RISKS"
    elif target_cat:
        intent = "CATEGORY_FILTER"
    elif ("how many" in q_lower and "exception" in q_lower) or ("open exception" in q_lower) or ("unresolved" in q_lower and "count" in q_lower):
        intent = "OPEN_EXCEPTIONS"
    elif "trace" in q_lower or "pipeline" in q_lower or "node" in q_lower or "timing" in q_lower:
        intent = "EXECUTION_TRACE"
    elif "low confidence" in q_lower or "confidence" in q_lower:
        intent = "LOW_CONFIDENCE"
    else:
        intent = "RUN_SUMMARY"

    return {
        "intent": intent,
        "target_invoice_id": target_id,
        "target_category": target_cat,
    }


# ---------------------------------------------------------------------------
# Node 2: Select Finance Tool
# ---------------------------------------------------------------------------

def select_finance_tool_node(state: CopilotState) -> Dict[str, Any]:
    intent = state.get("intent", "RUN_SUMMARY")
    target_id = state.get("target_invoice_id")
    target_cat = state.get("target_category")

    if intent == "SPECIFIC_INVOICE" and target_id:
        tool = "get_reconciliation_by_invoice"
        args = {"invoice_id": target_id}
    elif intent == "UNRESOLVED_AMOUNT":
        tool = "get_unresolved_amount"
        args = {}
    elif intent == "DELAYED_SETTLEMENTS":
        tool = "get_delayed_settlements"
        args = {"limit": 10}
    elif intent == "HIGH_VALUE_EXCEPTIONS" or intent == "PRIORITY_RISKS":
        tool = "get_high_value_exceptions"
        args = {"limit": 5}
    elif intent == "CATEGORY_FILTER" and target_cat:
        tool = "get_exceptions_by_category"
        args = {"category": target_cat}
    elif intent == "OPEN_EXCEPTIONS":
        tool = "get_open_exceptions"
        args = {"limit": 20}
    elif intent == "EXECUTION_TRACE":
        tool = "get_execution_trace"
        args = {}
    elif intent == "LOW_CONFIDENCE":
        tool = "get_low_confidence_records"
        args = {"threshold": 0.70}
    else:
        tool = "get_run_summary"
        args = {}

    return {
        "selected_tool": tool,
        "tool_args": args,
    }


# ---------------------------------------------------------------------------
# Node 3: Retrieve Real Data
# ---------------------------------------------------------------------------

def retrieve_real_data_node(state: CopilotState) -> Dict[str, Any]:
    tool = state.get("selected_tool", "get_run_summary")
    args = state.get("tool_args", {})
    run_id = state.get("run_id")

    invoice_found = None

    if tool == "get_reconciliation_by_invoice":
        data = get_reconciliation_by_invoice(args.get("invoice_id", ""), run_id)
        invoice_found = data is not None
    elif tool == "get_unresolved_amount":
        data = get_unresolved_amount(run_id)
    elif tool == "get_delayed_settlements":
        data = get_delayed_settlements(run_id, limit=args.get("limit", 10))
    elif tool == "get_high_value_exceptions":
        data = get_high_value_exceptions(run_id, limit=args.get("limit", 5))
    elif tool == "get_exceptions_by_category":
        data = get_exceptions_by_category(args.get("category", ""), run_id)
    elif tool == "get_open_exceptions":
        data = get_open_exceptions(run_id, limit=args.get("limit", 20))
    elif tool == "get_execution_trace":
        data = get_execution_trace(run_id)
    elif tool == "get_low_confidence_records":
        data = get_low_confidence_records(run_id, threshold=args.get("threshold", 0.70))
    else:
        data = get_run_summary(run_id)

    # For priority risks or run summary, also fetch high value exceptions as extra context
    extra_context = {}
    if tool == "get_run_summary":
        extra_context["high_value_exceptions"] = get_high_value_exceptions(run_id, limit=3)
        extra_context["unresolved_info"] = get_unresolved_amount(run_id)

    if extra_context and isinstance(data, dict):
        data["extra_context"] = extra_context

    return {
        "retrieved_data": data,
        "invoice_found": invoice_found,
    }


# ---------------------------------------------------------------------------
# Node 4: Generate Answer
# ---------------------------------------------------------------------------

def _format_deterministic_answer(state: CopilotState) -> str:
    """Deterministic fallback formatting when Gemini is offline."""
    tool = state.get("selected_tool")
    data = state.get("retrieved_data")
    query = state.get("query", "")
    q_lower = query.lower()

    if state.get("invoice_found") is False:
        target_id = state.get("target_invoice_id")
        return f"Invoice **{target_id}** was not found in the active reconciliation run. Please verify the invoice reference."

    if tool == "get_reconciliation_by_invoice":
        r = data
        return (
            f"**Invoice {r['invoice_id']} Details**\n"
            f"- **Customer**: {r.get('customer_name')} ({r.get('customer_id')})\n"
            f"- **Invoice Amount**: ₹{r.get('invoice_amount', 0):,.2f}\n"
            f"- **Settlement Amount**: ₹{r.get('settlement_amount', 0) or 0:,.2f} ({r.get('settlement_id') or 'None'})\n"
            f"- **Difference**: ₹{abs(r.get('difference', 0)):,.2f}\n"
            f"- **Terminal Status**: {r.get('status')}\n"
            f"- **Classification**: {r.get('match_type')}\n"
            f"- **Confidence Score**: {r.get('confidence_score', 0)*100:.1f}%\n"
            f"- **System Assessment**: {r.get('system_assessment')}\n"
            f"- **Recommendation**: {r.get('recommendation')}"
        )

    if tool == "get_unresolved_amount":
        return (
            f"The total unresolved financial value is **₹{data.get('total_unresolved_amount', 0):,.2f}** "
            f"across **{data.get('unresolved_count', 0)}** unresolved transactions.\n\n"
            f"Largest unresolved item: **{data.get('largest_unresolved', {}).get('invoice_id', 'None')}** "
            f"(₹{data.get('largest_unresolved', {}).get('invoice_amount', 0):,.2f})."
        )

    if tool == "get_delayed_settlements":
        if not data:
            return "No settlements exceeded the standard 5-day delivery SLA in this run."
        lines = [
            f"- **{d['invoice_id']}** ({d['customer_name']}): ₹{d['invoice_amount']:,.2f} — delayed {d['days_delayed']} days (Settlement {d['settlement_id']})"
            for d in data[:6]
        ]
        return f"**Delayed Settlements ({len(data)} detected exceeding SLA):**\n" + "\n".join(lines)

    if tool == "get_high_value_exceptions":
        if not data:
            return "There are no open exceptions requiring review in this run."
        lines = [
            f"- **{e['invoice_id']}** ({e['customer_name']}): ₹{e['invoice_amount']:,.2f} — {e.get('exception_category') or 'Review'} ({e['status']})"
            for e in data
        ]
        return f"**Highest-Value Exceptions Requiring Review:**\n" + "\n".join(lines)

    if tool == "get_exceptions_by_category":
        cat = state.get("target_category", "Exceptions")
        if not data:
            return f"No exceptions found for category **{cat}**."
        lines = [
            f"- **{e['invoice_id']}** ({e['customer_name']}): ₹{e['invoice_amount']:,.2f} — Diff: ₹{abs(e.get('difference', 0)):,.2f} ({e['status']})"
            for e in data[:6]
        ]
        return f"**{cat} Exceptions ({len(data)} total):**\n" + "\n".join(lines)

    if tool == "get_open_exceptions":
        if not data:
            return "No open unresolved exceptions currently require attention."
        lines = [
            f"- **{e['invoice_id']}** ({e['customer_name']}): ₹{e['invoice_amount']:,.2f} — {e.get('exception_category') or 'Review'} ({e['status']})"
            for e in data[:6]
        ]
        return f"**Open Exceptions Requiring Review ({len(data)} items):**\n" + "\n".join(lines)

    # Run summary
    run = data
    if "percentage" in q_lower and "auto" in q_lower:
        auto_rate = run.get("auto_resolution_rate", 0.0) * 100
        auto_count = run.get("auto_resolved", 0)
        return f"**{auto_rate:.1f}%** of records were auto-verified ({auto_count} of {run.get('records_processed', 0)} total records)."

    if "unresolved" in q_lower and "how many" in q_lower:
        return f"There are **{run.get('unresolved', 0)} unresolved** transactions and **{run.get('human_review', 0)}** transactions flagged for Human Review."

    acc_str = f"{run.get('verified_accuracy', 0)*100:.1f}%" if run.get('verified_accuracy') is not None else 'N/A'
    return (
        f"**Reconciliation Run Summary ({run.get('run_id')})**\n\n"
        f"- **Records Processed**: {run.get('records_processed')}\n"
        f"- **Match Rate**: {run.get('match_rate', 0)*100:.1f}%\n"
        f"- **Verified Accuracy**: {acc_str}\n"
        f"- **Auto-Resolved**: {run.get('auto_resolved')} ({run.get('auto_resolution_rate', 0)*100:.1f}%)\n"
        f"- **Human Review**: {run.get('human_review')}\n"
        f"- **Unresolved**: {run.get('unresolved')}\n"
        f"- **Open Exceptions**: {run.get('open_exception_count')}\n"
        f"- **Reconciled Value**: ₹{run.get('reconciled_amount', 0):,.2f}\n"
        f"- **Unresolved Value**: ₹{run.get('unresolved_amount', 0):,.2f}"
    )


def generate_answer_node(state: CopilotState) -> Dict[str, Any]:
    query = state.get("query", "")
    target_id = state.get("target_invoice_id")
    invoice_found = state.get("invoice_found")

    # Safety: non-existent invoice protection
    if invoice_found is False and target_id:
        msg = f"Invoice **{target_id}** was not found in the active reconciliation dataset. Please verify the invoice reference code."
        return {
            "raw_answer": msg,
            "ai_used": False,
        }

    retrieved = state.get("retrieved_data")

    # If Gemini is configured, synthesize response
    if is_gemini_configured():
        system_prompt = (
            "You are ReconAI Finance Copilot, a senior financial operations controller.\n"
            "Answer the user's question using ONLY the retrieved financial records provided below.\n"
            "STRICT RULES:\n"
            "1. Never invent or hallucinate transaction IDs, customer names, or amounts.\n"
            "2. If an invoice or transaction was not found, say clearly that it was not found.\n"
            "3. Cite specific numbers and invoice references accurately from the data.\n"
            "4. Always format currency in Indian Rupees using the ₹ symbol (e.g., ₹204,400.00). Never use USD or $.\n"
            "5. Be concise, direct, professional, and clear.\n"
            "6. Do NOT include generic conversational fluff."
        )

        prompt = (
            f"USER QUERY: {query}\n\n"
            f"RETRIEVED RECONCILIATION DATA:\n"
            f"{json.dumps(retrieved, indent=2, default=str)}\n\n"
            "Provide your grounded financial answer:"
        )

        content, model_used, latency, error = generate_content_with_fallback(
            prompt=prompt,
            system_instruction=system_prompt,
            timeout_seconds=12.0,
        )

        if content and content.strip():
            return {
                "raw_answer": content.strip(),
                "ai_used": True,
            }

    # Fallback to deterministic formatting
    fallback_text = _format_deterministic_answer(state)
    return {
        "raw_answer": fallback_text,
        "ai_used": False,
    }


# ---------------------------------------------------------------------------
# Node 5: Validate Answer
# ---------------------------------------------------------------------------

def validate_answer_node(state: CopilotState) -> Dict[str, Any]:
    raw = state.get("raw_answer", "")

    # Extract all real IDs referenced
    id_pattern = r"\b(?:BILL|INV|SET|PAY|BNK|RES)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b"
    found_ids = list(dict.fromkeys(re.findall(id_pattern, raw, re.IGNORECASE)))

    # Strip any stale hardcoded mode tags from markdown body
    clean_answer = re.sub(r"\n*\*AI Copilot:.*?\*", "", raw).strip()

    return {
        "final_answer": clean_answer,
        "referenced_ids": [i.upper() for i in found_ids],
    }


# ---------------------------------------------------------------------------
# Build LangGraph Workflow
# ---------------------------------------------------------------------------

copilot_workflow = StateGraph(CopilotState)

copilot_workflow.add_node("understand_query", understand_query_node)
copilot_workflow.add_node("select_finance_tool", select_finance_tool_node)
copilot_workflow.add_node("retrieve_real_data", retrieve_real_data_node)
copilot_workflow.add_node("generate_answer", generate_answer_node)
copilot_workflow.add_node("validate_answer", validate_answer_node)

copilot_workflow.set_entry_point("understand_query")
copilot_workflow.add_edge("understand_query", "select_finance_tool")
copilot_workflow.add_edge("select_finance_tool", "retrieve_real_data")
copilot_workflow.add_edge("retrieve_real_data", "generate_answer")
copilot_workflow.add_edge("generate_answer", "validate_answer")
copilot_workflow.add_edge("validate_answer", END)

copilot_graph = copilot_workflow.compile()


async def run_copilot_pipeline(
    message: str,
    run_id: Optional[str] = None,
    conversation_history: Optional[List[ChatMessage]] = None,
) -> CopilotResponse:
    """Main execution function invoking the LangGraph copilot workflow."""
    history = [
        {"role": m.role, "content": m.content}
        for m in (conversation_history or [])
    ]

    initial_state: CopilotState = {
        "query": message,
        "run_id": run_id,
        "conversation_history": history,
        "intent": "",
        "target_invoice_id": None,
        "target_category": None,
        "selected_tool": "",
        "tool_args": {},
        "retrieved_data": None,
        "invoice_found": None,
        "raw_answer": "",
        "final_answer": "",
        "referenced_ids": [],
        "ai_used": False,
    }

    final_state = copilot_graph.invoke(initial_state)
    ai_used = bool(final_state.get("ai_used"))
    mode = "connected" if ai_used else "data_only"

    return CopilotResponse(
        message=final_state["final_answer"],
        ai_available=ai_used,
        mode=mode,
        referenced_ids=final_state["referenced_ids"],
    )

