"""
FastAPI backend for the AP Invoice Processing Agentic App.

Endpoints:
  POST /api/upload-invoice      — Upload PDF, trigger agent pipeline (SSE streaming)
  GET  /api/invoices            — List all processed invoices
  GET  /api/invoices/{id}       — Single invoice + full agent trace
  GET  /api/review-queue        — Items needing human review
  POST /api/review-queue/{id}/resolve — Human resolves a review item
  GET  /api/vendors             — All vendors
  GET  /api/purchase-orders     — All POs
  GET  /api/stats               — Dashboard stats
"""
import os
import uuid
import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import aiofiles

from config import settings
from database.init_db import init_db
from database import queries
from database.models import ReviewResolveRequest, StatsResponse
from app_agents.orchestrator import process_invoice, process_invoice_streaming, process_chat_streaming


# ─── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AP Invoice Processing Agent",
    description="Agentic AP invoice processing using OpenAI Agents SDK + Azure OpenAI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """Initialize the database on startup."""
    init_db(settings.SQLITE_DB_PATH)
    print("✅ AP Invoice Processing Agent started")
    print(f"   DB: {settings.SQLITE_DB_PATH}")
    print(f"   Upload dir: {settings.UPLOAD_DIR}")


# ─── Invoice Upload + Processing ─────────────────────────────────────────────

@app.post("/api/upload-invoice")
async def upload_invoice(
    file: UploadFile = File(...),
    notes: str = Form(""),
):
    """
    Upload a PDF invoice and process it through the agent pipeline.

    Accepts an optional `notes` form field — submitter context passed to the
    agent prompt (e.g. PO reference, pre-approval note, vendor onboarding status).

    Returns Server-Sent Events (SSE) for real-time step updates.
    """
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save uploaded file
    file_id = uuid.uuid4().hex[:8]
    safe_name = f"{file_id}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Stream processing events via SSE
    async def event_stream() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'event': 'upload_complete', 'filename': file.filename, 'file_path': file_path})}\n\n"

        async for event in process_invoice_streaming(file_path, notes=notes):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/upload-invoice-sync")
async def upload_invoice_sync(file: UploadFile = File(...)):
    """
    Synchronous version of invoice upload — returns full result when done.
    Useful for testing without SSE support.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file_id = uuid.uuid4().hex[:8]
    safe_name = f"{file_id}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    result = await process_invoice(file_path)
    return result


# ─── Chat ─────────────────────────────────────────────────────────────────────

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(body: ChatRequest):
    """
    Handle a text chat query through the Triage Agent.
    Returns SSE stream with agent responses.
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    async def event_stream() -> AsyncIterator[str]:
        async for event in process_chat_streaming(body.message.strip()):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ─── Invoices ─────────────────────────────────────────────────────────────────

@app.get("/api/invoices")
async def list_invoices():
    """List all processed invoices, most recent first."""
    return queries.list_invoices()


@app.get("/api/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    """Get a single invoice by ID, including full agent trace."""
    invoice = queries.get_invoice_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return invoice


# ─── Review Queue ─────────────────────────────────────────────────────────────

@app.get("/api/review-queue")
async def get_review_queue(status: str = "pending"):
    """Get review queue items. Filter by status: pending, in_review, resolved."""
    return queries.list_review_queue(status)


@app.post("/api/review-queue/{item_id}/resolve")
async def resolve_review_item(item_id: int, body: ReviewResolveRequest):
    """
    Human reviewer approves or rejects a flagged invoice.

    This is the HUMAN-IN-THE-LOOP pattern — agents flag items for review,
    humans make the final call on ambiguous cases.
    """
    if body.resolution not in ("approve", "reject"):
        raise HTTPException(
            status_code=400,
            detail="resolution must be 'approve' or 'reject'"
        )

    success = queries.resolve_review_item(
        item_id=item_id,
        resolution=body.resolution,
        notes=body.notes or "",
        resolved_by=body.resolved_by or "AP Reviewer",
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Review item {item_id} not found")

    return {
        "success": True,
        "item_id": item_id,
        "resolution": body.resolution,
        "message": f"Invoice has been {'approved' if body.resolution == 'approve' else 'rejected'} by reviewer",
    }


# ─── Reference Data ───────────────────────────────────────────────────────────

@app.get("/api/vendors")
async def list_vendors():
    """List all vendors in the vendor master."""
    return queries.list_vendors()


@app.get("/api/purchase-orders")
async def list_purchase_orders():
    """List all purchase orders."""
    return queries.list_all_pos()


# ─── Stats ────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics."""
    return queries.get_stats()


# ─── Vendor History Context ───────────────────────────────────────────────────

@app.get("/api/vendors/{vendor_id}/history")
async def get_vendor_history(vendor_id: str):
    """
    Return the full operational history for a vendor.

    This is the same data the vendor_history_context tool surfaces to the
    Decision Agent — approval rate, amount ranges, common flag reasons,
    and human reviewer notes from past review queue resolutions.

    Used by the frontend Vendor Context Panel.
    """
    history = queries.get_vendor_invoice_history(vendor_id)
    return history


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "AP Invoice Processing Agent"}
