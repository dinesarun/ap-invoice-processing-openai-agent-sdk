"""
Invoice Query Tool — gives the Triage Agent the ability to answer questions
about invoice status, pending reviews, and processing statistics.

Returns RICH, CONTEXTUAL data by joining across all four tables:
  processed_invoices + vendor_master + purchase_orders + review_queue

This is intentionally not just a raw row dump. Every query includes:
  - Vendor names (not just IDs)
  - PO context where available
  - Aging / time-in-queue for pending items
  - Grouped summaries so the Triage Agent can reason across the data
  - Reviewer notes from past resolutions (institutional memory)
"""
import json
import sqlite3
from datetime import datetime, timezone
from agents import function_tool
from database.queries import get_conn, get_stats, search_vendors_by_name, get_vendor_invoice_history


def _days_ago(ts_str: str | None) -> int | None:
    """Return how many days ago a timestamp was."""
    if not ts_str:
        return None
    try:
        ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).days
    except Exception:
        return None


@function_tool
def invoice_query(
    query_type: str,
    filter_value: str = "",
    limit: int = 10,
) -> str:
    """
    Query the full AP invoice dataset to answer user questions with rich context.

    Returns joined data across vendors, purchase orders, invoices, and review queue —
    not just raw rows. Every result includes vendor names, PO details, aging info,
    and grouped summaries so you can reason and synthesize insights.

    query_type options:
      - "pending_invoices"  : Review queue items with vendor names, PO context, aging, flag reasons
      - "flagged_invoices"  : All flagged invoices grouped by reason and priority
      - "approved_invoices" : Recently approved invoices with vendor and PO details
      - "all_invoices"      : All processed invoices with full context
      - "stats"             : Enhanced stats: totals, vendor breakdown, pending summary
      - "invoice_status"    : Full details for one invoice (filter_value = invoice_id or invoice_number)
      - "vendor_invoices"   : All invoices for a specific vendor with vendor profile (filter_value = vendor name or ID)

    Args:
        query_type:   One of the query types above.
        filter_value: Required for invoice_status and vendor_invoices.
        limit:        Max records to return (default 10).

    Returns:
        Rich JSON context for the agent to analyze and synthesize.
    """
    try:
        if query_type == "pending_invoices":
            return _pending_invoices(limit)

        elif query_type == "flagged_invoices":
            return _flagged_invoices(limit)

        elif query_type == "approved_invoices":
            return _approved_invoices(limit)

        elif query_type == "all_invoices":
            return _all_invoices(limit)

        elif query_type == "stats":
            return _enhanced_stats()

        elif query_type == "invoice_status":
            if not filter_value:
                return json.dumps({"error": "filter_value is required for invoice_status"})
            return _invoice_status(filter_value)

        elif query_type == "vendor_invoices":
            if not filter_value:
                return json.dumps({"error": "filter_value is required for vendor_invoices"})
            return _vendor_invoices(filter_value, limit)

        else:
            return json.dumps({
                "error": f"Unknown query_type '{query_type}'.",
                "valid_types": [
                    "pending_invoices", "flagged_invoices", "approved_invoices",
                    "all_invoices", "stats", "invoice_status", "vendor_invoices",
                ],
            })

    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── Query implementations ────────────────────────────────────────────────────

def _pending_invoices(limit: int) -> str:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT
                 rq.id        AS queue_id,
                 rq.invoice_id,
                 rq.reason    AS flag_reason,
                 rq.priority,
                 rq.created_at AS queued_at,
                 pi.invoice_number,
                 pi.invoice_date,
                 pi.total_amount,
                 pi.currency,
                 pi.confidence_score,
                 pi.po_number,
                 pi.vendor_id,
                 COALESCE(vm.vendor_name, pi.vendor_id, 'Unknown Vendor') AS vendor_name,
                 vm.status    AS vendor_status,
                 vm.payment_terms,
                 po.total_amount AS po_amount,
                 po.department,
                 po.approver
               FROM review_queue rq
               LEFT JOIN processed_invoices pi ON rq.invoice_id = pi.invoice_id
               LEFT JOIN vendor_master vm ON pi.vendor_id = vm.vendor_id
               LEFT JOIN purchase_orders po ON pi.po_number = po.po_number
               WHERE rq.status = 'pending'
               ORDER BY
                 CASE rq.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                 rq.created_at ASC""",
        ).fetchall()

    items = [dict(r) for r in rows]

    # Enrich with aging
    for item in items:
        item["days_pending"] = _days_ago(item.get("queued_at"))
        if item.get("po_amount") and item.get("total_amount"):
            variance_pct = abs(item["total_amount"] - item["po_amount"]) / item["po_amount"] * 100
            item["po_variance_pct"] = round(variance_pct, 1)

    # Grouped summary
    by_vendor: dict = {}
    by_priority = {"high": 0, "medium": 0, "low": 0}
    total_amount = 0.0
    oldest_days = 0

    for item in items:
        v = item.get("vendor_name", "Unknown")
        by_vendor[v] = by_vendor.get(v, 0) + 1
        p = item.get("priority", "medium")
        by_priority[p] = by_priority.get(p, 0) + 1
        total_amount += item.get("total_amount") or 0
        d = item.get("days_pending") or 0
        if d > oldest_days:
            oldest_days = d

    return json.dumps({
        "query": "pending_invoices",
        "total_pending": len(items),
        "total_amount_at_risk": round(total_amount, 2),
        "oldest_pending_days": oldest_days,
        "by_priority": by_priority,
        "by_vendor": by_vendor,
        "items": items[:limit],
    }, default=str)


def _flagged_invoices(limit: int) -> str:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT
                 pi.invoice_id,
                 pi.invoice_number,
                 pi.invoice_date,
                 pi.total_amount,
                 pi.currency,
                 pi.status,
                 pi.decision_reason,
                 pi.confidence_score,
                 pi.po_number,
                 pi.vendor_id,
                 pi.processed_at,
                 COALESCE(vm.vendor_name, pi.vendor_id, 'Unknown') AS vendor_name,
                 vm.status AS vendor_status,
                 po.total_amount AS po_amount,
                 po.department,
                 rq.priority,
                 rq.id AS queue_id,
                 rq.created_at AS queued_at
               FROM processed_invoices pi
               LEFT JOIN vendor_master vm ON pi.vendor_id = vm.vendor_id
               LEFT JOIN purchase_orders po ON pi.po_number = po.po_number
               LEFT JOIN review_queue rq ON pi.invoice_id = rq.invoice_id
                 AND rq.status = 'pending'
               WHERE pi.status = 'flagged_for_review'
               ORDER BY pi.processed_at DESC""",
        ).fetchall()

    items = [dict(r) for r in rows]
    for item in items:
        item["days_since_flagged"] = _days_ago(item.get("processed_at"))

    # Group by top flag reason keywords
    reason_counts: dict = {}
    for item in items:
        reason = item.get("decision_reason") or "Unknown"
        # Bucket by first meaningful keyword
        key = reason[:60]
        reason_counts[key] = reason_counts.get(key, 0) + 1

    top_reasons = sorted(reason_counts.items(), key=lambda x: -x[1])[:5]

    return json.dumps({
        "query": "flagged_invoices",
        "total": len(items),
        "top_flag_reasons": [{"reason": r, "count": c} for r, c in top_reasons],
        "invoices": items[:limit],
    }, default=str)


def _approved_invoices(limit: int) -> str:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT
                 pi.invoice_id,
                 pi.invoice_number,
                 pi.invoice_date,
                 pi.total_amount,
                 pi.currency,
                 pi.confidence_score,
                 pi.po_number,
                 pi.vendor_id,
                 pi.processed_at,
                 pi.decision_reason,
                 COALESCE(vm.vendor_name, pi.vendor_id, 'Unknown') AS vendor_name,
                 po.department,
                 po.approver
               FROM processed_invoices pi
               LEFT JOIN vendor_master vm ON pi.vendor_id = vm.vendor_id
               LEFT JOIN purchase_orders po ON pi.po_number = po.po_number
               WHERE pi.status = 'approved'
               ORDER BY pi.processed_at DESC""",
        ).fetchall()

    items = [dict(r) for r in rows]
    total_value = sum(i.get("total_amount") or 0 for i in items)
    avg_confidence = (
        sum(i.get("confidence_score") or 0 for i in items) / len(items) if items else 0
    )

    return json.dumps({
        "query": "approved_invoices",
        "total": len(items),
        "total_approved_value": round(total_value, 2),
        "avg_confidence_score": round(avg_confidence, 3),
        "invoices": items[:limit],
    }, default=str)


def _all_invoices(limit: int) -> str:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT
                 pi.invoice_id,
                 pi.invoice_number,
                 pi.invoice_date,
                 pi.total_amount,
                 pi.currency,
                 pi.status,
                 pi.confidence_score,
                 pi.po_number,
                 pi.vendor_id,
                 pi.processed_at,
                 pi.decision_reason,
                 COALESCE(vm.vendor_name, pi.vendor_id, 'Unknown') AS vendor_name
               FROM processed_invoices pi
               LEFT JOIN vendor_master vm ON pi.vendor_id = vm.vendor_id
               ORDER BY pi.processed_at DESC""",
        ).fetchall()

    items = [dict(r) for r in rows]
    by_status = {}
    for i in items:
        s = i.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1

    return json.dumps({
        "query": "all_invoices",
        "total": len(items),
        "by_status": by_status,
        "invoices": items[:limit],
    }, default=str)


def _enhanced_stats() -> str:
    base = get_stats()

    with get_conn() as conn:
        # Vendor breakdown — which vendors have most pending/flagged
        vendor_breakdown = conn.execute(
            """SELECT
                 COALESCE(vm.vendor_name, pi.vendor_id, 'Unknown') AS vendor_name,
                 pi.vendor_id,
                 COUNT(*) AS total,
                 SUM(CASE WHEN pi.status = 'approved'          THEN 1 ELSE 0 END) AS approved,
                 SUM(CASE WHEN pi.status = 'flagged_for_review' THEN 1 ELSE 0 END) AS flagged,
                 ROUND(AVG(pi.total_amount), 2) AS avg_amount,
                 ROUND(SUM(pi.total_amount), 2) AS total_amount
               FROM processed_invoices pi
               LEFT JOIN vendor_master vm ON pi.vendor_id = vm.vendor_id
               GROUP BY pi.vendor_id
               ORDER BY total DESC
               LIMIT 8""",
        ).fetchall()

        # Recent 30-day activity
        recent = conn.execute(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN status = 'approved'          THEN 1 ELSE 0 END) AS approved,
                 SUM(CASE WHEN status = 'flagged_for_review' THEN 1 ELSE 0 END) AS flagged,
                 ROUND(SUM(total_amount), 2) AS total_value
               FROM processed_invoices
               WHERE processed_at >= datetime('now', '-30 days')""",
        ).fetchone()

        # Pending queue summary
        pending_summary = conn.execute(
            """SELECT
                 COUNT(*) AS count,
                 SUM(pi.total_amount) AS total_amount,
                 MAX(CAST(julianday('now') - julianday(rq.created_at) AS INTEGER)) AS oldest_days
               FROM review_queue rq
               LEFT JOIN processed_invoices pi ON rq.invoice_id = pi.invoice_id
               WHERE rq.status = 'pending'""",
        ).fetchone()

    return json.dumps({
        **base,
        "last_30_days": dict(recent) if recent else {},
        "pending_queue": dict(pending_summary) if pending_summary else {},
        "vendor_breakdown": [dict(r) for r in vendor_breakdown],
    }, default=str)


def _invoice_status(filter_value: str) -> str:
    with get_conn() as conn:
        # Try invoice_id first
        row = conn.execute(
            """SELECT
                 pi.*,
                 COALESCE(vm.vendor_name, pi.vendor_id, 'Unknown') AS vendor_name,
                 vm.address AS vendor_address,
                 vm.payment_terms,
                 vm.status AS vendor_status,
                 po.po_date,
                 po.total_amount AS po_amount,
                 po.department,
                 po.approver,
                 po.status AS po_status,
                 rq.id AS queue_id,
                 rq.priority,
                 rq.reason AS queue_reason,
                 rq.created_at AS queued_at,
                 rq.notes AS reviewer_notes,
                 rq.resolved_by,
                 rq.resolved_at
               FROM processed_invoices pi
               LEFT JOIN vendor_master vm ON pi.vendor_id = vm.vendor_id
               LEFT JOIN purchase_orders po ON pi.po_number = po.po_number
               LEFT JOIN review_queue rq ON pi.invoice_id = rq.invoice_id
               WHERE pi.invoice_id = ?
               ORDER BY rq.created_at DESC
               LIMIT 1""",
            (filter_value,),
        ).fetchone()

        if not row:
            # Try by invoice_number
            row = conn.execute(
                """SELECT
                     pi.*,
                     COALESCE(vm.vendor_name, pi.vendor_id, 'Unknown') AS vendor_name,
                     vm.address AS vendor_address,
                     vm.payment_terms,
                     vm.status AS vendor_status,
                     po.po_date,
                     po.total_amount AS po_amount,
                     po.department,
                     po.approver,
                     rq.id AS queue_id,
                     rq.priority,
                     rq.reason AS queue_reason,
                     rq.created_at AS queued_at,
                     rq.notes AS reviewer_notes,
                     rq.resolved_by,
                     rq.resolved_at
                   FROM processed_invoices pi
                   LEFT JOIN vendor_master vm ON pi.vendor_id = vm.vendor_id
                   LEFT JOIN purchase_orders po ON pi.po_number = po.po_number
                   LEFT JOIN review_queue rq ON pi.invoice_id = rq.invoice_id
                   WHERE pi.invoice_number = ?
                   ORDER BY pi.processed_at DESC
                   LIMIT 1""",
                (filter_value,),
            ).fetchone()

    if not row:
        return json.dumps({"found": False, "error": f"No invoice found matching '{filter_value}'"})

    invoice = dict(row)
    invoice["days_since_processed"] = _days_ago(invoice.get("processed_at"))
    if invoice.get("po_amount") and invoice.get("total_amount"):
        invoice["po_variance_pct"] = round(
            abs(invoice["total_amount"] - invoice["po_amount"]) / invoice["po_amount"] * 100, 1
        )

    # Parse JSON fields
    for field in ("extracted_fields", "agent_trace"):
        if isinstance(invoice.get(field), str):
            try:
                import json as _json
                invoice[field] = _json.loads(invoice[field])
            except Exception:
                pass

    return json.dumps({"found": True, "invoice": invoice}, default=str)


def _vendor_invoices(filter_value: str, limit: int) -> str:
    # Find vendor
    vendors = search_vendors_by_name(filter_value)
    vendor_id = None
    vendor_profile = None

    if vendors:
        vendor_profile = vendors[0]
        vendor_id = vendors[0]["vendor_id"]
    else:
        # Try direct vendor_id match
        vendor_id = filter_value

    with get_conn() as conn:
        rows = conn.execute(
            """SELECT
                 pi.invoice_id,
                 pi.invoice_number,
                 pi.invoice_date,
                 pi.total_amount,
                 pi.currency,
                 pi.status,
                 pi.confidence_score,
                 pi.po_number,
                 pi.decision_reason,
                 pi.processed_at,
                 po.department,
                 po.total_amount AS po_amount,
                 rq.priority,
                 rq.status AS review_status
               FROM processed_invoices pi
               LEFT JOIN purchase_orders po ON pi.po_number = po.po_number
               LEFT JOIN review_queue rq ON pi.invoice_id = rq.invoice_id
               WHERE pi.vendor_id = ?
               ORDER BY pi.processed_at DESC""",
            (vendor_id,),
        ).fetchall()

        # Also get all POs for this vendor
        pos = conn.execute(
            """SELECT po_number, po_date, total_amount, status, department, approver
               FROM purchase_orders WHERE vendor_id = ?""",
            (vendor_id,),
        ).fetchall()

    invoices = [dict(r) for r in rows]

    # Get full vendor history (operational intelligence)
    history = get_vendor_invoice_history(vendor_id)

    return json.dumps({
        "vendor_profile": vendor_profile,
        "vendor_id": vendor_id,
        "purchase_orders": [dict(r) for r in pos],
        "invoice_history_summary": history.get("summary") if history.get("has_history") else None,
        "common_flag_reasons": history.get("common_flag_reasons", []),
        "reviewer_notes": history.get("reviewer_notes", []),
        "total_invoices": len(invoices),
        "invoices": invoices[:limit],
    }, default=str)
