"""
Database query helper functions — thin wrappers around SQLite.
All functions accept an optional db_path; defaults to settings.SQLITE_DB_PATH.
"""
import hashlib
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from config import settings


def get_conn(db_path: str = None) -> sqlite3.Connection:
    path = db_path or settings.SQLITE_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Vendors ─────────────────────────────────────────────────────────────────

def get_vendor_by_id(vendor_id: str) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM vendor_master WHERE vendor_id = ?", (vendor_id,)
        ).fetchone()
    return dict(row) if row else None


def search_vendors_by_name(name: str) -> List[Dict]:
    """Fuzzy search vendors by name using LIKE."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM vendor_master WHERE vendor_name LIKE ? ORDER BY vendor_name",
            (f"%{name}%",),
        ).fetchall()
    return [dict(r) for r in rows]


def list_vendors() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM vendor_master ORDER BY vendor_name").fetchall()
    return [dict(r) for r in rows]


# ─── Purchase Orders ──────────────────────────────────────────────────────────

def get_po_by_number(po_number: str) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM purchase_orders WHERE po_number = ?", (po_number,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("line_items"):
        d["line_items"] = json.loads(d["line_items"])
    return d


def list_pos_by_vendor(vendor_id: str) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM purchase_orders WHERE vendor_id = ? ORDER BY po_date DESC",
            (vendor_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("line_items"):
            d["line_items"] = json.loads(d["line_items"])
        result.append(d)
    return result


def list_all_pos() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM purchase_orders ORDER BY po_date DESC").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d.get("line_items"):
            try:
                d["line_items"] = json.loads(d["line_items"])
            except Exception:
                pass
        result.append(d)
    return result


# ─── Processed Invoices ───────────────────────────────────────────────────────

def insert_processed_invoice(data: Dict) -> str:
    """Insert a processed invoice record. Returns invoice_id."""
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO processed_invoices
               (invoice_id, vendor_id, po_number, invoice_number, invoice_date,
                total_amount, currency, extracted_fields, confidence_score,
                status, decision_reason, pipeline_response, agent_trace)
               VALUES (:invoice_id, :vendor_id, :po_number, :invoice_number, :invoice_date,
                       :total_amount, :currency, :extracted_fields, :confidence_score,
                       :status, :decision_reason, :pipeline_response, :agent_trace)""",
            data,
        )
        conn.commit()
    return data["invoice_id"]


def update_pipeline_response(invoice_id: str, pipeline_response: str) -> bool:
    """Persist the final pipeline response text for a processed invoice."""
    if not invoice_id:
        return False

    with get_conn() as conn:
        cur = conn.execute(
            """UPDATE processed_invoices
               SET pipeline_response = ?
               WHERE invoice_id = ?""",
            (pipeline_response, invoice_id),
        )
        conn.commit()
        return cur.rowcount > 0


def get_invoice_by_id(invoice_id: str) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM processed_invoices WHERE invoice_id = ?", (invoice_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    for field in ("extracted_fields", "agent_trace"):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                pass
    return d


def list_invoices() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM processed_invoices ORDER BY processed_at DESC"
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        for field in ("extracted_fields", "agent_trace"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
        result.append(d)
    return result


# ─── Review Queue ─────────────────────────────────────────────────────────────

def insert_review_queue_item(data: Dict) -> int:
    """Insert item into review queue. Returns the new row id."""
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO review_queue (invoice_id, reason, priority, assigned_to)
               VALUES (:invoice_id, :reason, :priority, :assigned_to)""",
            data,
        )
        conn.commit()
        return cur.lastrowid


def list_review_queue(status: str = "pending") -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT rq.*, pi.invoice_number, pi.vendor_id, pi.total_amount, pi.currency,
                      pi.status as invoice_status
               FROM review_queue rq
               LEFT JOIN processed_invoices pi ON rq.invoice_id = pi.invoice_id
               WHERE rq.status = ?
               ORDER BY rq.created_at DESC""",
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def resolve_review_item(item_id: int, resolution: str, notes: str, resolved_by: str) -> bool:
    """Mark a review queue item as resolved and update the invoice status."""
    new_invoice_status = "approved" if resolution == "approve" else "rejected"
    with get_conn() as conn:
        # Fetch invoice_id
        row = conn.execute(
            "SELECT invoice_id FROM review_queue WHERE id = ?", (item_id,)
        ).fetchone()
        if not row:
            return False
        invoice_id = row["invoice_id"]

        conn.execute(
            """UPDATE review_queue
               SET status = 'resolved', notes = ?, resolved_by = ?,
                   resolved_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (notes, resolved_by, item_id),
        )
        conn.execute(
            "UPDATE processed_invoices SET status = ? WHERE invoice_id = ?",
            (new_invoice_status, invoice_id),
        )
        conn.commit()
    return True


# ─── Duplicate Detection ──────────────────────────────────────────────────────

def check_duplicate_invoice(
    invoice_number: str,
    vendor_id: str = "",
    total_amount: float = 0.0,
    invoice_date: str = "",
) -> Dict:
    """
    Check for prior submissions of the same invoice.

    Runs two passes:
      1. Exact match  — same invoice_number (regardless of vendor/amount)
      2. Fuzzy match  — same vendor + same amount + same date, different number
                        (catches re-submitted invoices with fresh reference numbers)

    Returns a dict with `is_duplicate`, `match_type`, and full details of
    every prior submission found.
    """
    with get_conn() as conn:
        # Pass 1: exact invoice_number match
        exact_rows = conn.execute(
            """SELECT invoice_id, vendor_id, po_number, invoice_number,
                      invoice_date, total_amount, status, decision_reason,
                      processed_at
               FROM processed_invoices
               WHERE invoice_number = ?
               ORDER BY processed_at DESC""",
            (invoice_number,),
        ).fetchall()

        # Pass 2: fuzzy — same vendor + amount + date, different number
        fuzzy_rows = []
        if vendor_id and total_amount and invoice_date:
            fuzzy_rows = conn.execute(
                """SELECT invoice_id, vendor_id, po_number, invoice_number,
                          invoice_date, total_amount, status, decision_reason,
                          processed_at
                   FROM processed_invoices
                   WHERE vendor_id = ?
                     AND ABS(total_amount - ?) < 0.01
                     AND invoice_date = ?
                     AND (invoice_number != ? OR invoice_number IS NULL)
                   ORDER BY processed_at DESC""",
                (vendor_id, total_amount, invoice_date, invoice_number),
            ).fetchall()

    exact = [dict(r) for r in exact_rows]
    fuzzy = [dict(r) for r in fuzzy_rows]

    if exact:
        return {
            "is_duplicate": True,
            "match_type": "exact",
            "detail": (
                f"Invoice number '{invoice_number}' was already submitted "
                f"{len(exact)} time(s). Most recent: "
                f"status={exact[0]['status']}, processed={exact[0]['processed_at']}"
            ),
            "prior_submissions": exact,
        }

    if fuzzy:
        return {
            "is_duplicate": True,
            "match_type": "fuzzy",
            "detail": (
                f"Different invoice number but same vendor, amount "
                f"(${total_amount:,.2f}), and date ({invoice_date}) was "
                f"already processed {len(fuzzy)} time(s). "
                f"Possible re-submission with a new reference number."
            ),
            "prior_submissions": fuzzy,
        }

    return {
        "is_duplicate": False,
        "match_type": None,
        "detail": "No prior submission found. Invoice appears to be new.",
        "prior_submissions": [],
    }


# ─── Vendor History (Context Layer) ──────────────────────────────────────────

def get_vendor_invoice_history(vendor_id: str, limit: int = 20) -> Dict:
    """
    Return the full processing history for a vendor from processed_invoices
    and any human reviewer notes from review_queue.

    This is the core query powering the vendor_history_context tool —
    it turns our operational database into a live context layer that
    compounds in value as more invoices are processed.
    """
    with get_conn() as conn:
        # Aggregate stats
        stats_row = conn.execute(
            """SELECT
                COUNT(*)                                        AS total,
                SUM(CASE WHEN status = 'approved'          THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status = 'flagged_for_review' THEN 1 ELSE 0 END) AS flagged,
                SUM(CASE WHEN status = 'rejected'          THEN 1 ELSE 0 END) AS rejected,
                AVG(total_amount)                               AS avg_amount,
                MIN(total_amount)                               AS min_amount,
                MAX(total_amount)                               AS max_amount,
                AVG(confidence_score)                           AS avg_confidence
               FROM processed_invoices
               WHERE vendor_id = ?""",
            (vendor_id,),
        ).fetchone()

        # Most recent invoices (for pattern recognition)
        recent_rows = conn.execute(
            """SELECT invoice_id, invoice_number, invoice_date, total_amount,
                      status, decision_reason, confidence_score, processed_at
               FROM processed_invoices
               WHERE vendor_id = ?
               ORDER BY processed_at DESC
               LIMIT ?""",
            (vendor_id, limit),
        ).fetchall()

        # Common flag reasons for this vendor
        flag_reason_rows = conn.execute(
            """SELECT decision_reason, COUNT(*) AS cnt
               FROM processed_invoices
               WHERE vendor_id = ? AND status != 'approved'
                 AND decision_reason IS NOT NULL AND decision_reason != ''
               GROUP BY decision_reason
               ORDER BY cnt DESC
               LIMIT 3""",
            (vendor_id,),
        ).fetchall()

        # Human reviewer notes — the most valuable context signal.
        # These are the notes AP reviewers leave when resolving flagged invoices.
        # Each note represents a human judgment call that should inform future decisions.
        reviewer_note_rows = conn.execute(
            """SELECT rq.notes, rq.resolved_by, rq.resolved_at, rq.reason,
                      pi.invoice_number, pi.total_amount
               FROM review_queue rq
               JOIN processed_invoices pi ON rq.invoice_id = pi.invoice_id
               WHERE pi.vendor_id = ?
                 AND rq.status = 'resolved'
                 AND rq.notes IS NOT NULL AND rq.notes != ''
               ORDER BY rq.resolved_at DESC
               LIMIT 5""",
            (vendor_id,),
        ).fetchall()

    if not stats_row or stats_row["total"] == 0:
        return {"has_history": False, "vendor_id": vendor_id}

    s = dict(stats_row)
    approval_rate = round(s["approved"] / s["total"] * 100, 1) if s["total"] else 0.0

    return {
        "has_history": True,
        "vendor_id": vendor_id,
        "summary": {
            "total_invoices": s["total"],
            "approved": s["approved"],
            "flagged": s["flagged"],
            "rejected": s["rejected"],
            "approval_rate_pct": approval_rate,
            "avg_invoice_amount": round(s["avg_amount"] or 0, 2),
            "min_invoice_amount": round(s["min_amount"] or 0, 2),
            "max_invoice_amount": round(s["max_amount"] or 0, 2),
            "avg_confidence_score": round(s["avg_confidence"] or 0, 3),
        },
        "recent_invoices": [dict(r) for r in recent_rows],
        "common_flag_reasons": [
            {"reason": r["decision_reason"], "count": r["cnt"]}
            for r in flag_reason_rows
        ],
        "reviewer_notes": [
            {
                "note": r["notes"],
                "resolved_by": r["resolved_by"],
                "resolved_at": r["resolved_at"],
                "original_flag_reason": r["reason"],
                "invoice_number": r["invoice_number"],
                "invoice_amount": r["total_amount"],
            }
            for r in reviewer_note_rows
        ],
    }


# ─── Stats ────────────────────────────────────────────────────────────────────

def get_stats() -> Dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM processed_invoices").fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM processed_invoices WHERE status = 'approved'"
        ).fetchone()[0]
        flagged = conn.execute(
            "SELECT COUNT(*) FROM processed_invoices WHERE status = 'flagged_for_review'"
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM processed_invoices WHERE status = 'rejected'"
        ).fetchone()[0]
        avg_conf = conn.execute(
            "SELECT AVG(confidence_score) FROM processed_invoices"
        ).fetchone()[0] or 0.0
        reasons = conn.execute(
            """SELECT decision_reason, COUNT(*) as cnt
               FROM processed_invoices
               WHERE status != 'approved'
               GROUP BY decision_reason
               ORDER BY cnt DESC
               LIMIT 5"""
        ).fetchall()

    return {
        "total_processed": total,
        "approved": approved,
        "flagged_for_review": flagged,
        "rejected": rejected,
        "approval_rate": round(approved / total * 100, 1) if total else 0.0,
        "avg_confidence_score": round(avg_conf, 3),
        "common_flag_reasons": [{"reason": r[0], "count": r[1]} for r in reasons],
    }


# ─── Content Fingerprinting ───────────────────────────────────────────────────

def _compute_content_fingerprint(extracted_fields: dict) -> tuple:
    """
    Compute SHA-256 hashes for full content and line items only.

    Normalization: lowercase + trimmed descriptions, rounded amounts, sorted by description.
    Returns (content_hash, line_items_hash).
    """
    line_items = extracted_fields.get("line_items") or []
    normalized_items = sorted(
        [
            {
                "description": str(item.get("description", "")).strip().lower(),
                "qty": round(float(item.get("qty", 0) or 0), 2),
                "unit_price": round(float(item.get("unit_price", 0) or 0), 2),
                "amount": round(float(item.get("amount", 0) or 0), 2),
            }
            for item in line_items
            if item
        ],
        key=lambda x: x["description"],
    )

    line_items_str = json.dumps(normalized_items, sort_keys=True)
    line_items_hash = hashlib.sha256(line_items_str.encode()).hexdigest()

    content_data = {
        "vendor_name": str(extracted_fields.get("vendor_name", "")).strip().lower(),
        "total_amount": round(float(extracted_fields.get("total_amount", 0) or 0), 2),
        "invoice_date": str(extracted_fields.get("invoice_date", "") or ""),
        "line_items": normalized_items,
    }
    content_str = json.dumps(content_data, sort_keys=True)
    content_hash = hashlib.sha256(content_str.encode()).hexdigest()

    return content_hash, line_items_hash


def store_invoice_fingerprint(
    invoice_id: str,
    extracted_fields: dict,
    vendor_id: str = "",
    total_amount: float = 0.0,
    invoice_date: str = "",
) -> None:
    """Store a content fingerprint for a newly persisted invoice. Failures are silenced."""
    try:
        content_hash, line_items_hash = _compute_content_fingerprint(extracted_fields)
        with get_conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO invoice_fingerprints
                   (invoice_id, content_hash, line_items_hash, vendor_id, total_amount, invoice_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (invoice_id, content_hash, line_items_hash, vendor_id, total_amount, invoice_date),
            )
            conn.commit()
    except Exception:
        pass


def check_content_fingerprint(
    extracted_fields: dict,
    vendor_id: str = "",
    invoice_number: str = "",
) -> dict:
    """
    Check if this invoice's content was already processed before.

    Two passes:
      1. Exact content match  — same vendor + amounts + normalized line items, different invoice_number
                                → strong indicator of AI-manipulated resubmission
      2. Line items only match — same goods/services, different total
                                → possible invoice splitting or amount manipulation
    """
    content_hash, line_items_hash = _compute_content_fingerprint(extracted_fields)

    with get_conn() as conn:
        exact_rows = conn.execute(
            """SELECT f.invoice_id, f.vendor_id, f.total_amount, f.invoice_date,
                      pi.invoice_number, pi.status, pi.processed_at
               FROM invoice_fingerprints f
               JOIN processed_invoices pi ON f.invoice_id = pi.invoice_id
               WHERE f.content_hash = ?
                 AND (? = '' OR pi.invoice_number != ?)
               ORDER BY f.created_at DESC
               LIMIT 5""",
            (content_hash, invoice_number, invoice_number),
        ).fetchall()

        line_only_rows = conn.execute(
            """SELECT f.invoice_id, f.vendor_id, f.total_amount, f.invoice_date,
                      pi.invoice_number, pi.status, pi.processed_at
               FROM invoice_fingerprints f
               JOIN processed_invoices pi ON f.invoice_id = pi.invoice_id
               WHERE f.line_items_hash = ?
                 AND f.content_hash != ?
               ORDER BY f.created_at DESC
               LIMIT 5""",
            (line_items_hash, content_hash),
        ).fetchall()

    exact = [dict(r) for r in exact_rows]
    line_match = [dict(r) for r in line_only_rows]

    if exact:
        return {
            "fingerprint_match": True,
            "match_type": "exact_content",
            "detail": (
                f"Invoice content is identical to a previously processed invoice with a "
                f"different invoice number — strong indicator of AI-manipulated resubmission. "
                f"Prior: {exact[0]['invoice_number']} (status={exact[0]['status']}, "
                f"processed={exact[0]['processed_at']})"
            ),
            "prior_matches": exact,
            "manipulation_risk": "high",
        }

    if line_match:
        return {
            "fingerprint_match": True,
            "match_type": "line_items_only",
            "detail": (
                f"Line items match a previously processed invoice but total amount differs — "
                f"possible invoice splitting or amount manipulation. "
                f"Prior: {line_match[0]['invoice_number']} "
                f"(amount=${line_match[0]['total_amount']:,.2f}, status={line_match[0]['status']})"
            ),
            "prior_matches": line_match,
            "manipulation_risk": "medium",
        }

    return {
        "fingerprint_match": False,
        "match_type": None,
        "detail": "No content fingerprint match. Invoice content appears unique.",
        "prior_matches": [],
        "manipulation_risk": "low",
    }


# ─── Behavioral Fraud Analysis ────────────────────────────────────────────────

def analyze_invoice_fraud_signals(
    vendor_id: str,
    total_amount: float,
    invoice_date: str = "",
    po_number: str = "",
) -> dict:
    """
    Analyze behavioral fraud signals for an incoming invoice:
      - Submission velocity anomaly (too many invoices in 7-day window)
      - Billing cycle deviation (invoice date outside normal submission rhythm)
      - Invoice splitting (multiple invoices against same PO summing near PO total)
      - Just-below-approval-threshold amounts
      - Suspiciously round amounts

    Returns a dict with fraud_signals list, overall_risk, and has_signals flag.
    """
    signals = []

    with get_conn() as conn:
        # Velocity — count of vendor invoices in last 7 days
        vel_row = conn.execute(
            """SELECT COUNT(*) AS cnt, COALESCE(SUM(total_amount), 0) AS total
               FROM processed_invoices
               WHERE vendor_id = ?
                 AND processed_at >= datetime('now', '-7 days')""",
            (vendor_id,),
        ).fetchone()

        # Billing cycle — last 30 invoice dates for gap analysis
        history_rows = conn.execute(
            """SELECT invoice_date, total_amount
               FROM processed_invoices
               WHERE vendor_id = ?
                 AND invoice_date IS NOT NULL AND invoice_date != ''
               ORDER BY invoice_date DESC
               LIMIT 30""",
            (vendor_id,),
        ).fetchall()

        # Splitting — same vendor + same PO in last 30 days
        po_invoices = []
        po_total = None
        if po_number:
            po_invoices = conn.execute(
                """SELECT total_amount, invoice_number
                   FROM processed_invoices
                   WHERE vendor_id = ? AND po_number = ?
                     AND processed_at >= datetime('now', '-30 days')""",
                (vendor_id, po_number),
            ).fetchall()
            po_row = conn.execute(
                "SELECT total_amount FROM purchase_orders WHERE po_number = ?",
                (po_number,),
            ).fetchone()
            po_total = po_row["total_amount"] if po_row else None

    # --- Velocity anomaly ---
    if vel_row and vel_row["cnt"] >= 3:
        severity = "high" if vel_row["cnt"] >= 5 else "medium"
        signals.append({
            "type": "velocity_anomaly",
            "severity": severity,
            "detail": (
                f"Vendor submitted {vel_row['cnt']} invoices in the last 7 days "
                f"(total: ${vel_row['total']:,.2f}). Unusual submission frequency."
            ),
        })

    # --- Billing cycle analysis ---
    history_list = [dict(r) for r in history_rows]
    if len(history_list) >= 4 and invoice_date:
        dates = []
        for inv in history_list:
            try:
                dates.append(datetime.strptime(inv["invoice_date"], "%Y-%m-%d"))
            except Exception:
                pass
        if len(dates) >= 4:
            gaps = [(dates[i] - dates[i + 1]).days for i in range(len(dates) - 1)]
            avg_gap = sum(gaps) / len(gaps)
            std_gap = (sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)) ** 0.5
            try:
                current_dt = datetime.strptime(invoice_date, "%Y-%m-%d")
                gap_from_last = abs((current_dt - dates[0]).days)
                if std_gap > 0 and abs(gap_from_last - avg_gap) > 2.5 * std_gap:
                    signals.append({
                        "type": "billing_cycle_anomaly",
                        "severity": "medium",
                        "detail": (
                            f"Invoice date {invoice_date} deviates significantly from vendor's "
                            f"normal billing cycle (avg {avg_gap:.0f}d between invoices, "
                            f"±{std_gap:.0f}d). This submission is "
                            f"{abs(gap_from_last - avg_gap):.0f}d off the expected schedule."
                        ),
                    })
            except Exception:
                pass

    # --- Invoice splitting detection ---
    po_invoices_list = [dict(r) for r in po_invoices]
    if po_invoices_list and po_total and len(po_invoices_list) >= 2:
        existing_sum = sum(inv["total_amount"] for inv in po_invoices_list)
        combined_total = existing_sum + total_amount
        if abs(combined_total - po_total) / po_total < 0.05:
            signals.append({
                "type": "invoice_splitting",
                "severity": "high",
                "detail": (
                    f"Possible invoice splitting: {len(po_invoices_list) + 1} invoices against "
                    f"PO {po_number} in the last 30 days sum to ${combined_total:,.2f} "
                    f"(PO total: ${po_total:,.2f}). Multiple billings below approval threshold."
                ),
            })

    # --- Just-below-threshold detection ---
    APPROVAL_THRESHOLDS = [1_000, 5_000, 10_000, 25_000, 50_000]
    for threshold in APPROVAL_THRESHOLDS:
        if threshold * 0.95 <= total_amount < threshold:
            signals.append({
                "type": "just_below_threshold",
                "severity": "medium",
                "detail": (
                    f"Amount ${total_amount:,.2f} is just below the ${threshold:,} "
                    f"approval threshold — possible threshold-avoidance."
                ),
            })
            break

    # --- Round-number amount ---
    if total_amount >= 1_000 and total_amount == round(total_amount, -2):
        signals.append({
            "type": "round_number_amount",
            "severity": "low",
            "detail": (
                f"Amount ${total_amount:,.2f} is an unusually round number. "
                f"Itemized invoices rarely total to exact hundreds."
            ),
        })

    overall_risk = "low"
    if any(s["severity"] == "high" for s in signals):
        overall_risk = "high"
    elif any(s["severity"] == "medium" for s in signals):
        overall_risk = "medium"

    return {
        "fraud_signals": signals,
        "signal_count": len(signals),
        "overall_risk": overall_risk,
        "vendor_id": vendor_id,
        "has_signals": len(signals) > 0,
    }
