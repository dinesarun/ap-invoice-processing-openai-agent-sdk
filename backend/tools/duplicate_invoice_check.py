"""
Duplicate Invoice Check Tool.

This is the difference between instruction-based hope and deterministic detection.

The Decision Agent's instructions previously said "flag suspected duplicates" —
but the agent had no tool to check. It would have had to notice a matching
invoice_number buried in vendor_history_context's recent_invoices list.
That's unreliable.

This tool makes duplicate detection a hard, explicit DB lookup:
  - Exact match:  same invoice_number in processed_invoices → definite duplicate
  - Fuzzy match:  same vendor + same amount + same date, different invoice number
                  → likely re-submission with a new reference number

The Decision Agent MUST call this as its first action, before any approval logic.
A positive result short-circuits everything: flag immediately, priority=high.
"""
import json
from agents import function_tool

from database.queries import check_duplicate_invoice


@function_tool
def duplicate_invoice_check(
    invoice_number: str,
    vendor_id: str = "",
    total_amount: float = 0.0,
    invoice_date: str = "",
) -> str:
    """
    Check whether this invoice has been submitted and processed before.

    ALWAYS call this as your very first action. A duplicate invoice that
    slips through to payment is a direct financial loss — it must be caught
    before any other decision logic runs.

    Two detection modes:
      - Exact:  same invoice_number found in processed_invoices
                → definite duplicate, flag with priority="high" immediately
      - Fuzzy:  same vendor_id + same total_amount + same invoice_date,
                but different invoice_number
                → likely re-submission; flag with priority="high"

    If is_duplicate is True, do NOT run any other approval checks.
    Call flag_for_review immediately with:
      - flag_reason: include the prior submission details from this response
      - priority: "high"

    Args:
        invoice_number: Invoice number extracted from the document.
        vendor_id:      Matched vendor ID (pass empty string if unknown).
        total_amount:   Invoice total as a float (used for fuzzy matching).
        invoice_date:   Invoice date as YYYY-MM-DD (used for fuzzy matching).

    Returns:
        JSON with is_duplicate (bool), match_type ("exact"|"fuzzy"|null),
        detail (plain-English explanation), and prior_submissions list.
    """
    if not invoice_number or invoice_number.strip() == "":
        return json.dumps({
            "is_duplicate": False,
            "match_type": None,
            "detail": "No invoice_number provided — cannot check for duplicates.",
            "prior_submissions": [],
        })

    result = check_duplicate_invoice(
        invoice_number=invoice_number.strip(),
        vendor_id=vendor_id.strip(),
        total_amount=total_amount,
        invoice_date=invoice_date.strip(),
    )

    return json.dumps(result, default=str)
