"""
Triage Agent — the entry point for the invoice processing pipeline.

This agent:
1. Validates the incoming request is an invoice
2. Kicks off the pipeline by handing off to the Extraction Agent

Demonstrates the GUARDRAIL primitive: an input guardrail is attached
(see guardrails/input_guardrail.py) that checks the file is a valid PDF
before the agent even starts processing.
"""
from agents import Agent

from agents.setup import get_deployment_name


def create_triage_agent(handoffs: list = None) -> Agent:
    return Agent(
        name="Triage Agent",
        model=get_deployment_name(),
        instructions="""You are the AP invoice processing triage agent — the entry point
for the invoice processing pipeline.

When you receive a message to process an invoice PDF:
1. Acknowledge the request
2. Confirm the file path is provided
3. Immediately hand off to the Extraction Agent to begin processing

The Extraction Agent will:
  → Extract invoice fields using OCR
  → Hand off to Vendor Lookup Agent
  → Hand off to PO Matching Agent
  → Hand off to Decision Agent for final approval/flagging

If the user asks something unrelated to invoice processing, politely explain
that you are specialized for AP invoice processing and can help with:
- Processing invoice PDFs
- Checking invoice status
- Understanding why an invoice was flagged

Do NOT attempt to extract invoice data yourself — always hand off to the
Extraction Agent for that task.""",
        handoffs=handoffs or [],
    )
