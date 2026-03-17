"""
Content Fingerprint Check Tool.

Detects AI-manipulated invoice resubmissions where a fraudster edits only the
invoice number (and perhaps the date) but leaves the vendor, line items, and
amounts unchanged.

How it works:
  1. Normalize extracted line items (lowercase descriptions, rounded amounts, sorted)
  2. Compute SHA-256 hash of the full invoice content (vendor + amounts + line items)
  3. Compute a separate hash for line items only (amount-agnostic)
  4. Compare against every stored fingerprint in invoice_fingerprints

Match types:
  - exact_content:   Same vendor + total + normalized line items, different invoice number
                     → almost certainly a manipulated resubmission → flag HIGH priority
  - line_items_only: Same goods/services but different total amount
                     → possible invoice splitting or amount manipulation → flag MEDIUM
  - no match:        Invoice content is genuinely new
"""
import json
from agents import function_tool

from database.queries import check_content_fingerprint as _check


@function_tool
def content_fingerprint_check(
    extracted_fields: str,
    vendor_id: str = "",
    invoice_number: str = "",
) -> str:
    """
    Check whether this invoice's content matches a previously processed invoice
    using cryptographic content fingerprinting.

    This catches AI-manipulated resubmissions where the fraudster changed only
    the invoice number but left the vendor, line items, and amounts intact.

    Call this AFTER duplicate_invoice_check (in the Extraction Agent) and
    BEFORE the final approval decision.

    Args:
        extracted_fields: JSON string of all extracted invoice fields
                          (must include vendor_name, total_amount, invoice_date,
                          and line_items array).
        vendor_id:        Matched vendor ID (empty string if unknown).
        invoice_number:   Current invoice number — used to exclude the invoice
                          itself when checking exact matches.

    Returns:
        JSON with fingerprint_match (bool), match_type, manipulation_risk
        ("high"/"medium"/"low"), detail string, and prior_matches list.
    """
    try:
        fields = json.loads(extracted_fields) if isinstance(extracted_fields, str) else extracted_fields
    except Exception:
        fields = {}

    result = _check(
        extracted_fields=fields,
        vendor_id=vendor_id,
        invoice_number=invoice_number,
    )
    return json.dumps(result, default=str)
