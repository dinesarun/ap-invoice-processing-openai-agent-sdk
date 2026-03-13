"""
Pydantic models for database entities and API responses.
"""
from __future__ import annotations
from typing import Optional, List, Any
from datetime import datetime, date
from pydantic import BaseModel


# ─── Vendor ──────────────────────────────────────────────────────────────────

class Vendor(BaseModel):
    vendor_id: str
    vendor_name: str
    address: Optional[str] = None
    tax_id: Optional[str] = None
    payment_terms: str = "Net 30"
    bank_account: Optional[str] = None
    status: str = "active"
    created_at: Optional[str] = None


# ─── Purchase Order ───────────────────────────────────────────────────────────

class LineItem(BaseModel):
    description: str
    qty: float
    unit_price: float
    amount: float


class PurchaseOrder(BaseModel):
    po_number: str
    vendor_id: str
    po_date: Optional[str] = None
    total_amount: float
    currency: str = "USD"
    line_items: Optional[List[LineItem]] = None
    status: str = "open"
    department: Optional[str] = None
    approver: Optional[str] = None


# ─── Processed Invoice ────────────────────────────────────────────────────────

class ProcessedInvoice(BaseModel):
    invoice_id: str
    vendor_id: Optional[str] = None
    po_number: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = "USD"
    extracted_fields: Optional[str] = None   # JSON string
    confidence_score: Optional[float] = None
    status: str  # approved / flagged_for_review / rejected
    decision_reason: Optional[str] = None
    agent_trace: Optional[str] = None        # JSON string
    processed_at: Optional[str] = None


# ─── Review Queue ─────────────────────────────────────────────────────────────

class ReviewQueueItem(BaseModel):
    id: Optional[int] = None
    invoice_id: str
    reason: str
    priority: str = "medium"
    assigned_to: Optional[str] = None
    status: str = "pending"
    created_at: Optional[str] = None


# ─── API request/response helpers ────────────────────────────────────────────

class ProcessingResult(BaseModel):
    invoice_id: str
    status: str
    decision_reason: str
    confidence_score: float
    extracted_fields: dict
    agent_trace: List[dict]


class ReviewResolveRequest(BaseModel):
    resolution: str       # "approve" or "reject"
    notes: Optional[str] = None
    resolved_by: Optional[str] = None


class StatsResponse(BaseModel):
    total_processed: int
    approved: int
    flagged_for_review: int
    rejected: int
    approval_rate: float
    avg_confidence_score: float
    common_flag_reasons: List[dict]
