"""
Vendor History Context Tool — the "context layer" for the Decision Agent.

This tool is the practical implementation of the "Context as Moat" idea:
every invoice we process adds to the operational history that future agents
can draw on. The Decision Agent is no longer making decisions in isolation —
it's reasoning over accumulated institutional memory.

What this tool surfaces:
  - Approval rate for this vendor (are they typically clean?)
  - Historical amount range (is this invoice unusual in size?)
  - Common flag reasons (what tends to go wrong with this vendor?)
  - Human reviewer notes (the richest signal — past human judgments
    that the agent should learn from and apply to the current decision)

The compounding effect:
  Invoice #1  → agent has no history, decides on rules alone
  Invoice #10  → agent sees a pattern forming
  Invoice #50  → agent knows this vendor's normal behaviour intimately
  Invoice #100 → reviewer notes encode institutional knowledge
               that even a new AP employee wouldn't have
"""
import json
from agents import function_tool

from database.queries import get_vendor_invoice_history


@function_tool
def vendor_history_context(vendor_id: str) -> str:
    """
    Retrieve historical invoice processing context for a vendor.

    Call this tool BEFORE making a final approve/flag decision.
    It gives you the operational history of how this vendor's invoices
    have been handled in the past — approval rates, typical amounts,
    common issues, and crucially, any notes left by human reviewers
    when they resolved flagged invoices.

    Use the returned context to:
    - Detect if the current invoice amount is anomalous vs. history
    - Check if this vendor has a pattern of specific issues
    - Apply precedent from human reviewer decisions
      (e.g., "reviewer previously approved rush delivery surcharges
       from this vendor — treat similarly this time")
    - Adjust confidence in your decision based on vendor track record

    Args:
        vendor_id: The vendor ID from the vendor_master table (e.g., "V001").

    Returns:
        JSON with:
          has_history: bool — False if this is the vendor's first invoice
          summary: approval_rate_pct, avg/min/max invoice amounts, avg confidence
          recent_invoices: last N invoices with status and decision_reason
          common_flag_reasons: top flag reasons for this vendor
          reviewer_notes: human reviewer notes from resolved review queue items
                          — treat these as high-signal precedent
    """
    if not vendor_id or vendor_id.strip() == "":
        return json.dumps({
            "has_history": False,
            "message": "No vendor_id provided — cannot retrieve history",
        })

    history = get_vendor_invoice_history(vendor_id.strip())

    if not history.get("has_history"):
        return json.dumps({
            "has_history": False,
            "vendor_id": vendor_id,
            "message": (
                "No prior invoices found for this vendor. "
                "This is their first invoice in our system — "
                "apply standard rules and consider a slightly more cautious threshold."
            ),
        })

    # Build a plain-English interpretation alongside the raw data
    # so the LLM can reason about it more easily
    summary = history["summary"]
    notes = history.get("reviewer_notes", [])
    flags = history.get("common_flag_reasons", [])

    interpretation = _build_interpretation(summary, notes, flags)
    history["interpretation"] = interpretation

    return json.dumps(history, default=str)


def _build_interpretation(summary: dict, reviewer_notes: list, flag_reasons: list) -> str:
    """
    Produce a plain-English summary the Decision Agent can reason over directly.
    This reduces the cognitive load on the LLM — instead of parsing raw stats,
    it gets a pre-digested narrative.
    """
    lines = []

    rate = summary["approval_rate_pct"]
    total = summary["total_invoices"]

    if rate >= 90:
        lines.append(f"High-trust vendor: {rate}% approval rate across {total} prior invoices.")
    elif rate >= 70:
        lines.append(f"Generally reliable vendor: {rate}% approval rate across {total} invoices — occasional issues.")
    elif rate >= 50:
        lines.append(f"Mixed history: only {rate}% approval rate across {total} invoices — review carefully.")
    else:
        lines.append(f"High-risk vendor: only {rate}% approval rate across {total} invoices — escalate if any doubt.")

    avg = summary["avg_invoice_amount"]
    lo = summary["min_invoice_amount"]
    hi = summary["max_invoice_amount"]
    lines.append(f"Typical invoice range: ${lo:,.2f} – ${hi:,.2f} (avg ${avg:,.2f}).")

    if flag_reasons:
        top = flag_reasons[0]["reason"]
        lines.append(f"Most common flag reason: \"{top}\".")

    if reviewer_notes:
        lines.append("Reviewer precedents (apply these to the current decision):")
        for n in reviewer_notes[:3]:
            note_text = n.get("note", "").strip()
            by = n.get("resolved_by") or "reviewer"
            original = n.get("original_flag_reason", "")
            inv = n.get("invoice_number", "")
            amount = n.get("invoice_amount")
            amount_str = f"${amount:,.2f}" if amount else ""
            lines.append(
                f'  • Invoice {inv} {amount_str} was flagged ("{original}") '
                f'then resolved by {by} with note: "{note_text}"'
            )
    else:
        lines.append("No human reviewer notes on record for this vendor yet.")

    return " ".join(lines)
