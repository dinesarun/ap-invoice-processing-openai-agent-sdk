"""
Invoice Fraud Analysis Tool.

Behavioral fraud analysis that goes beyond simple duplicate detection.
Looks for patterns that indicate fraud vs. legitimate recurring business:

  1. VELOCITY ANOMALY
     Too many invoices from the same vendor in a 7-day window.
     Legitimate vendors invoice on a schedule; a burst of submissions is suspicious.

  2. BILLING CYCLE DEVIATION
     If a vendor invoices every ~30 days and suddenly submits after 3 days,
     the schedule break warrants review. Statistical deviation from historical
     mean ± 2.5 standard deviations triggers this signal.

  3. INVOICE SPLITTING
     Multiple invoices from the same vendor against the same PO in a 30-day
     window whose combined total is within 5% of the PO amount.
     Classic tactic to keep each invoice below an approval threshold.

  4. JUST-BELOW-THRESHOLD AMOUNTS
     Amounts between 95%-99% of a common AP approval threshold
     ($1k, $5k, $10k, $25k, $50k). Threshold-avoidance is a well-known
     AP fraud technique.

  5. ROUND-NUMBER AMOUNTS
     Legitimate itemized invoices almost never total to exact hundreds.
     Round totals (e.g., $5,000.00, $12,000.00) are a low-severity signal
     worth noting in the audit trace.

The Decision Agent uses this analysis alongside vendor history and
content fingerprinting to differentiate genuine recurring orders from
fraudulent duplicate submissions.
"""
import json
from agents import function_tool

from database.queries import analyze_invoice_fraud_signals as _analyze


@function_tool
def invoice_fraud_analysis(
    vendor_id: str,
    total_amount: float,
    invoice_date: str = "",
    po_number: str = "",
) -> str:
    """
    Run behavioral fraud analysis on an incoming invoice.

    This tool detects patterns that simple duplicate checks miss:
      - Burst submission velocity from a single vendor
      - Invoice dates that fall outside the vendor's normal billing rhythm
      - Invoice splitting across multiple bills against the same PO
      - Amounts suspiciously close to (but below) approval thresholds
      - Unusually round invoice totals

    Crucially, this tool also supports LEGITIMATE recurring orders:
    a vendor that invoices every 30 days for the same services is NOT
    a duplicate — it is an expected recurring pattern. The billing cycle
    analysis distinguishes the two by measuring statistical deviation
    from the vendor's historical schedule.

    Args:
        vendor_id:     Matched vendor ID from vendor_master.
        total_amount:  Invoice total as a float.
        invoice_date:  Invoice date in YYYY-MM-DD format (used for cycle analysis).
        po_number:     Referenced PO number (used for splitting detection).

    Returns:
        JSON with fraud_signals list (each with type, severity, detail),
        overall_risk ("high"/"medium"/"low"), signal_count, and has_signals flag.
    """
    result = _analyze(
        vendor_id=vendor_id,
        total_amount=total_amount,
        invoice_date=invoice_date,
        po_number=po_number,
    )
    return json.dumps(result, default=str)
