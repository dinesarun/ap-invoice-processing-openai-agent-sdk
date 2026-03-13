"""
PO Lookup Tool — queries purchase_orders table and compares amounts.
"""
import json
from agents import function_tool

from database import queries


@function_tool
def po_lookup(po_number: str = "", vendor_id: str = "", invoice_amount: float = 0.0) -> str:
    """
    Look up a Purchase Order and optionally compare it against an invoice amount.

    Retrieves PO details from the purchase_orders table and calculates
    the variance between the PO amount and the provided invoice amount.
    This is a critical step in the 3-way matching process.

    Args:
        po_number: The PO number to look up (e.g., "PO-2024-001").
        vendor_id: Optional — filter POs by vendor if po_number not provided.
        invoice_amount: Optional — if provided, calculates variance % vs PO total.

    Returns:
        JSON string with:
          - po_details: PO fields including line items
          - match_result: "exact_match" | "within_tolerance" | "amount_mismatch" | "over_tolerance"
          - variance_amount: difference in dollars
          - variance_pct: percentage difference (positive = invoice higher than PO)
          - recommendation: string advice for the decision agent
    """
    po = None

    if po_number:
        po = queries.get_po_by_number(po_number)

    if not po and vendor_id:
        pos = queries.list_pos_by_vendor(vendor_id)
        if pos:
            # Return list of POs for this vendor
            return json.dumps({
                "found": True,
                "by_vendor": True,
                "vendor_id": vendor_id,
                "purchase_orders": pos,
            })

    if not po:
        return json.dumps({
            "found": False,
            "message": f"No PO found with number '{po_number}'",
            "vendor_pos": [],
        })

    result: dict = {"found": True, "po_details": po}

    if invoice_amount and invoice_amount > 0:
        po_amount = po.get("total_amount", 0)
        variance = invoice_amount - po_amount
        variance_pct = (variance / po_amount * 100) if po_amount else 0

        if abs(variance_pct) < 0.01:
            match_result = "exact_match"
            recommendation = "Invoice amount exactly matches PO. Safe to approve."
        elif abs(variance_pct) <= 5.0:
            match_result = "within_tolerance"
            recommendation = "Invoice amount is within 5% tolerance. Can auto-approve."
        elif abs(variance_pct) <= 10.0:
            match_result = "amount_mismatch"
            recommendation = "Invoice amount differs by 5-10%. Flag for human review."
        else:
            match_result = "over_tolerance"
            recommendation = (
                f"Invoice amount differs by {variance_pct:.1f}% — exceeds 10% tolerance. "
                "Escalate for manual review or reject."
            )

        result.update({
            "match_result": match_result,
            "po_amount": po_amount,
            "invoice_amount": invoice_amount,
            "variance_amount": round(variance, 2),
            "variance_pct": round(variance_pct, 2),
            "recommendation": recommendation,
        })

    return json.dumps(result)
