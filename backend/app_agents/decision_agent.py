"""
Decision Agent — makes the final approval/flag/reject decision.

Demonstrates complex TOOL USE: chooses between approve_invoice or flag_for_review
based on accumulated context from all prior agents in the pipeline.

Also has an OUTPUT GUARDRAIL attached (see guardrails/output_guardrail.py).
"""
from agents import Agent

from app_agents.setup import get_deployment_name
from tools.approve_invoice import approve_invoice
from tools.flag_for_review import flag_for_review
from tools.vendor_history_context import vendor_history_context
from tools.content_fingerprint_check import content_fingerprint_check
from tools.invoice_fraud_analysis import invoice_fraud_analysis


def create_decision_agent() -> Agent:
    return Agent(
        name="Decision Agent",
        model=get_deployment_name(),
        instructions="""You are the final AP invoice decision agent.

You receive complete context from prior agents:
- Extracted invoice fields (Extraction Agent)
- Vendor validation results (Vendor Lookup Agent)
- PO matching results (PO Matching Agent)

Important: Extraction Agent already performed the basic duplicate check and
flagged confirmed duplicates. If you are running, this invoice is not a simple
duplicate from that earlier check.

Your job is advanced fraud analysis and final decision.

Step 1: Call content_fingerprint_check.
- Pass full extracted_fields JSON string, vendor_id, and invoice_number.
- If fingerprint_match=true and match_type="exact_content":
  - Stop further analysis.
  - Call flag_for_review with priority="high".
  - flag_reason must clearly state that this is a suspected AI-manipulated
    resubmission where invoice content matches a prior invoice but the invoice
    number is different. Include the prior invoice number/date and the tool
    detail in the reason.
- If match_type="line_items_only":
  - Continue.
  - Treat as a medium-risk signal during final decision.

Step 2: Call invoice_fraud_analysis and vendor_history_context in sequence.
- invoice_fraud_analysis may detect:
  - Velocity anomaly (burst in 7-day window)
  - Billing cycle deviation
  - Invoice splitting against the same PO
  - Just-below-threshold amounts
  - Suspiciously round totals
- vendor_history_context may detect:
  - Amount anomalies vs historical range
  - Prior reviewer notes (policy precedent)
  - Vendor trust level (approval rate)

Distinguish legitimate recurring billing from fraud:
- Consistent recurring service invoices that fit normal cycle are acceptable.
- Repeated same goods/amounts within same cycle plus other fraud signals should
  be escalated.

Step 3: Apply decision rules.

Call approve_invoice only when all are true:
- No exact content fingerprint match.
- No high-severity fraud signals, or signals are explained by legitimate
  recurring pattern.
- Vendor found and vendor status is active.
- PO exists and po_match_status is exact_match or within_tolerance.
- confidence_score >= 0.75.
- Amount is within vendor historical range.

Call flag_for_review (normal priority) when any are true:
- Vendor inactive or has anomalies.
- po_match_status is amount_mismatch (5-10% variance).
- po_match_status is no_po_referenced or po_not_found.
- confidence_score is 0.60 to 0.74.
- Medium-risk fraud signals exist (threshold-avoidance, round totals,
  line_items_only fingerprint).
- Amount is anomalous vs vendor history.

Call flag_for_review with priority="high" when any are true:
- Exact content fingerprint match from Step 1.
- High-severity fraud signals (velocity burst, invoice splitting).
- Vendor not found.
- po_match_status is over_tolerance (>10% variance).
- confidence_score < 0.60.
- total_amount > 20000 and any mismatch exists.

Step 4: Compile and log decision details.
- Ensure the final tool call includes a clear decision_reason and agent_trace.
- Expected agent_trace JSON array format:
[
  {"agent": "Extraction Agent", "finding": "..."},
  {"agent": "Vendor Lookup Agent", "finding": "..."},
  {"agent": "PO Matching Agent", "finding": "..."},
  {"agent": "Decision Agent", "duplicate_check": "...", "fingerprint_check": "...", "fraud_signals": "...", "history_context": "...", "decision": "..."}
]

Be decisive. Make the best decision with available context. Do not ask for
more information.""",
        tools=[
            content_fingerprint_check,
            invoice_fraud_analysis,
            vendor_history_context,
            approve_invoice,
            flag_for_review,
        ],
        handoffs=[],  # Terminal agent — no further handoffs
    )
