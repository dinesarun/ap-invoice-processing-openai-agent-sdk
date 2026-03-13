"""
Database query helper functions — thin wrappers around SQLite.
All functions accept an optional db_path; defaults to settings.SQLITE_DB_PATH.
"""
import sqlite3
import json
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
            """SELECT rq.*, pi.invoice_number, pi.vendor_id, pi.total_amount, pi.currency
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
