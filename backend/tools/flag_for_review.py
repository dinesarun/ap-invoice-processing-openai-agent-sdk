"""
Flag for Review Tool — saves invoice to processed_invoices as flagged and adds to review_queue.
"""
import json
import uuid
from agents import function_tool

from database import queries
from database.queries import store_invoice_fingerprint


@function_tool
def flag_for_review(
    invoice_number: str,
    vendor_id: str,
    po_number: str,
    invoice_date: str,
    total_amount: float,
    currency: str,
    extracted_fields: str,
    confidence_score: float,
    flag_reason: str,
    priority: str = "medium",
    agent_trace: str = "[]",
) -> str:
    """
    Flag an invoice for human review and add it to the review queue.

    Call this tool when the invoice cannot be auto-approved due to:
    - Amount variance between 5% and 10% of PO amount
    - Vendor is inactive or status is unclear
    - PO is partially matched or partially received
    - Low confidence score (< 0.70) on critical fields
    - Missing non-critical fields
    - Any other uncertainty that warrants human judgment

    Args:
        invoice_number: The invoice number from the document.
        vendor_id: Matched or attempted vendor ID (use empty string if not found).
        po_number: Matched or referenced PO number (use empty string if not found).
        invoice_date: Invoice date in YYYY-MM-DD format.
        total_amount: Total invoice amount as a number.
        currency: Currency code (e.g., "USD").
        extracted_fields: JSON string of all extracted invoice fields.
        confidence_score: Extraction confidence 0.0-1.0.
        flag_reason: Clear explanation of WHY this invoice needs human review.
        priority: Review priority — "low", "medium", or "high".
                  Use "high" if amount > $10,000 or vendor is completely unknown.
        agent_trace: JSON array of agent execution steps for audit trail.

    Returns:
        JSON string with invoice_id, review queue ID, and next steps.
    """
    invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"

    invoice_data = {
        "invoice_id": invoice_id,
        "vendor_id": vendor_id or None,
        "po_number": po_number or None,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "total_amount": total_amount,
        "currency": currency,
        "extracted_fields": extracted_fields if isinstance(extracted_fields, str) else json.dumps(extracted_fields),
        "confidence_score": confidence_score,
        "status": "flagged_for_review",
        "decision_reason": flag_reason,
        "pipeline_response": None,
        "agent_trace": agent_trace if isinstance(agent_trace, str) else json.dumps(agent_trace),
    }

    queries.insert_processed_invoice(invoice_data)

    # Store content fingerprint so future submissions can be compared
    try:
        fields = json.loads(extracted_fields) if isinstance(extracted_fields, str) else extracted_fields
        store_invoice_fingerprint(invoice_id, fields, vendor_id or "", total_amount, invoice_date)
    except Exception:
        pass

    queue_data = {
        "invoice_id": invoice_id,
        "reason": flag_reason,
        "priority": priority,
        "assigned_to": None,
    }
    queue_id = queries.insert_review_queue_item(queue_data)

    return json.dumps({
        "success": True,
        "invoice_id": invoice_id,
        "review_queue_id": queue_id,
        "status": "flagged_for_review",
        "priority": priority,
        "message": (
            f"Invoice {invoice_number} has been flagged for human review "
            f"(Queue ID: {queue_id}). Reason: {flag_reason}"
        ),
        "flag_reason": flag_reason,
        "confidence_score": confidence_score,
    })
