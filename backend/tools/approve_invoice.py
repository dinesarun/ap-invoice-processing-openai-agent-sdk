"""
Approve Invoice Tool — persists an approved invoice to the database.
"""
import json
import uuid
from typing import Optional
from agents import function_tool

from database import queries


@function_tool
def approve_invoice(
    invoice_number: str,
    vendor_id: str,
    po_number: str,
    invoice_date: str,
    total_amount: float,
    currency: str,
    extracted_fields: str,
    confidence_score: float,
    decision_reason: str,
    agent_trace: str = "[]",
) -> str:
    """
    Approve an invoice and record it in the processed_invoices table.

    Call this tool when all validation checks have passed:
    - Vendor is found and active
    - PO exists and amount variance is within tolerance (<5%)
    - All required fields are present
    - Confidence score is acceptable

    Args:
        invoice_number: The invoice number from the document.
        vendor_id: The matched vendor ID from vendor_master.
        po_number: The matched PO number from purchase_orders.
        invoice_date: Invoice date in YYYY-MM-DD format.
        total_amount: Total invoice amount as a number.
        currency: Currency code (e.g., "USD").
        extracted_fields: JSON string of all extracted invoice fields.
        confidence_score: Extraction confidence 0.0-1.0.
        decision_reason: Brief explanation of why the invoice was approved.
        agent_trace: JSON array of agent execution steps for audit trail.

    Returns:
        JSON string with invoice_id and confirmation message.
    """
    invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"

    data = {
        "invoice_id": invoice_id,
        "vendor_id": vendor_id,
        "po_number": po_number,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "total_amount": total_amount,
        "currency": currency,
        "extracted_fields": extracted_fields if isinstance(extracted_fields, str) else json.dumps(extracted_fields),
        "confidence_score": confidence_score,
        "status": "approved",
        "decision_reason": decision_reason,
        "pipeline_response": None,
        "agent_trace": agent_trace if isinstance(agent_trace, str) else json.dumps(agent_trace),
    }

    queries.insert_processed_invoice(data)

    return json.dumps({
        "success": True,
        "invoice_id": invoice_id,
        "status": "approved",
        "message": f"Invoice {invoice_number} has been approved and recorded with ID {invoice_id}.",
        "decision_reason": decision_reason,
        "confidence_score": confidence_score,
    })
