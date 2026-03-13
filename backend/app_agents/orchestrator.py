"""
Orchestrator — wires all agents together and runs the invoice processing pipeline.

This module demonstrates all 4 OpenAI Agents SDK primitives working together:

  1. AGENTS: Five specialized agents, each with a focused role
  2. HANDOFFS: Triage → Extraction → Vendor → PO Match → Decision
  3. TOOLS: llmwhisperer_extract, vendor_lookup, po_lookup, approve_invoice, flag_for_review
  4. GUARDRAILS: pdf_file_guardrail (input) + decision_output_guardrail (output)

The Runner.run() call starts the agent loop:
  → Agent receives prompt
  → Agent decides to call a tool or hand off
  → SDK executes tool, returns result to agent
  → Agent reasons about result and decides next action
  → Loop continues until a terminal state (no more handoffs/tools)

SSE streaming: process_invoice_streaming() yields events as each agent step completes,
enabling real-time UI updates.
"""
import asyncio
import json
import traceback
from typing import AsyncIterator

from agents import Runner, RunConfig, handoff, InputGuardrailTripwireTriggered

from app_agents.setup import configure_azure_client, get_deployment_name
from app_agents.triage_agent import create_triage_agent
from app_agents.extraction_agent import create_extraction_agent
from app_agents.vendor_agent import create_vendor_agent
from app_agents.po_match_agent import create_po_match_agent
from app_agents.decision_agent import create_decision_agent
from database import queries as db_queries
from guardrails.input_guardrail import pdf_file_guardrail
from guardrails.output_guardrail import decision_output_guardrail


def build_pipeline():
    """
    Build the agent pipeline with handoffs wired in the correct order.

    Handoff chain: Triage → Extraction → Vendor → PO Match → Decision

    We create agents from the terminal end (Decision) backwards so that
    each agent can reference the next agent in its handoffs list.
    """
    # Configure Azure OpenAI client (idempotent)
    configure_azure_client()

    # Step 5: Decision Agent (terminal — no further handoffs)
    decision_agent = create_decision_agent()

    # Step 4: PO Matching Agent → hands off to Decision
    po_match_agent = create_po_match_agent(handoffs=[decision_agent])

    # Step 3: Vendor Lookup Agent → hands off to PO Match
    vendor_agent = create_vendor_agent(handoffs=[po_match_agent])

    # Step 2: Extraction Agent → hands off to Vendor Lookup
    extraction_agent = create_extraction_agent(handoffs=[vendor_agent])

    # Step 1: Triage Agent (entry point) → hands off to Extraction
    # Also attaches the PDF input guardrail
    triage_agent = create_triage_agent(handoffs=[extraction_agent])
    triage_agent.input_guardrails = [pdf_file_guardrail]

    return triage_agent


async def process_invoice(file_path: str) -> dict:
    """
    Process a single invoice through the full agent pipeline.

    This is the synchronous (batch) version — waits for full completion
    before returning. Used for simple API calls.

    Returns a dict with:
      - final_output: agent's final text response
      - trace: list of agent execution steps
      - invoice_data: parsed invoice fields (if extraction succeeded)
    """
    triage_agent = build_pipeline()

    try:
        result = await Runner.run(
            triage_agent,
            input=f"Process this invoice PDF located at: {file_path}",
        )

        # Extract structured trace from new_items
        trace = _extract_trace(result)
        _persist_pipeline_response(result, result.final_output)

        return {
            "success": True,
            "final_output": result.final_output,
            "trace": trace,
        }

    except InputGuardrailTripwireTriggered as e:
        return {
            "success": False,
            "error": "input_validation_failed",
            "message": str(e),
            "trace": [],
        }
    except Exception as e:
        return {
            "success": False,
            "error": "pipeline_error",
            "message": str(e),
            "traceback": traceback.format_exc(),
            "trace": [],
        }


async def process_invoice_streaming(file_path: str) -> AsyncIterator[str]:
    """
    Process an invoice and yield SSE events as each agent step completes.

    Yields JSON-encoded SSE event strings:
      data: {"event": "agent_start", "agent": "...", "step": N}
      data: {"event": "tool_call", "tool": "...", "input": {...}}
      data: {"event": "tool_result", "tool": "...", "output": "..."}
      data: {"event": "handoff", "from_agent": "...", "to_agent": "..."}
      data: {"event": "agent_complete", "agent": "...", "output": "..."}
      data: {"event": "pipeline_complete", "result": {...}}
      data: {"event": "pipeline_error", "error": "..."}
    """
    triage_agent = build_pipeline()

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    try:
        # Stream using Runner.run_streamed for real-time events
        result = Runner.run_streamed(
            triage_agent,
            input=f"Process this invoice PDF located at: {file_path}",
        )

        current_agent = "Triage Agent"
        step = 0

        async for event in result.stream_events():
            event_type = event.type

            if event_type == "agent_updated_stream_event":
                new_agent = event.new_agent.name if event.new_agent else "Unknown"
                if new_agent != current_agent:
                    step += 1
                    yield _sse({
                        "event": "handoff",
                        "from_agent": current_agent,
                        "to_agent": new_agent,
                        "step": step,
                    })
                    current_agent = new_agent

            elif event_type == "run_item_stream_event":
                item = event.item
                item_type = getattr(item, "type", None)

                if item_type == "tool_call_item":
                    tool_name = getattr(item, "raw_item", {})
                    if hasattr(item, "raw_item"):
                        raw = item.raw_item
                        name = getattr(raw, "name", str(raw))
                        args_str = getattr(raw, "arguments", "{}")
                        try:
                            args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        except Exception:
                            args = {"raw": args_str}
                        yield _sse({
                            "event": "tool_call",
                            "agent": current_agent,
                            "tool": name,
                            "input": args,
                            "step": step,
                        })

                elif item_type == "tool_call_output_item":
                    raw_output = getattr(item, "output", "")
                    # Truncate large outputs for SSE
                    display = raw_output[:500] + "..." if len(str(raw_output)) > 500 else raw_output
                    yield _sse({
                        "event": "tool_result",
                        "agent": current_agent,
                        "output": display,
                        "step": step,
                    })

                elif item_type == "message_output_item":
                    # Agent produced a text message
                    text = ""
                    if hasattr(item, "raw_item"):
                        raw = item.raw_item
                        if hasattr(raw, "content"):
                            for c in (raw.content or []):
                                if hasattr(c, "text"):
                                    text += c.text
                    if text:
                        yield _sse({
                            "event": "agent_message",
                            "agent": current_agent,
                            "message": text[:1000],
                            "step": step,
                        })

        # stream_events() drains the run loop and leaves the completed
        # RunResultStreaming object populated with final_output/new_items.
        final_output = result.final_output
        if final_output is None and hasattr(result, "final_output_as"):
            try:
                final_output = result.final_output_as(str)
            except Exception:
                final_output = None

        trace = _extract_trace(result)
        _persist_pipeline_response(result, final_output)

        yield _sse({
            "event": "pipeline_complete",
            "final_output": str(final_output)[:2000],
            "trace": trace,
        })

    except InputGuardrailTripwireTriggered as e:
        yield _sse({
            "event": "pipeline_error",
            "error": "input_validation_failed",
            "message": str(e),
        })
    except Exception as e:
        yield _sse({
            "event": "pipeline_error",
            "error": "pipeline_error",
            "message": str(e),
        })


def _extract_trace(result) -> list:
    """Extract a structured trace from a Runner result's new_items."""
    trace = []
    if not hasattr(result, "new_items"):
        return trace

    for item in result.new_items:
        item_type = getattr(item, "type", None)
        raw = getattr(item, "raw_item", None)

        if item_type == "tool_call_item" and raw:
            trace.append({
                "type": "tool_call",
                "agent": getattr(item, "agent", {}).name if hasattr(item, "agent") and item.agent else "unknown",
                "tool": getattr(raw, "name", "unknown"),
                "input": _safe_json(getattr(raw, "arguments", "{}")),
            })
        elif item_type == "tool_call_output_item":
            trace.append({
                "type": "tool_result",
                "output": str(getattr(item, "output", ""))[:500],
            })
        elif item_type == "message_output_item" and raw:
            text = ""
            for c in (getattr(raw, "content", []) or []):
                if hasattr(c, "text"):
                    text += c.text
            if text:
                trace.append({
                    "type": "message",
                    "agent": getattr(item, "agent", {}).name if hasattr(item, "agent") and item.agent else "unknown",
                    "content": text[:500],
                })

    return trace


def _safe_json(val) -> dict:
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except Exception:
        return {"raw": str(val)}


def _extract_invoice_id(result) -> str | None:
    """Best-effort extraction of invoice_id from tool outputs in run items."""
    if not hasattr(result, "new_items"):
        return None

    for item in reversed(result.new_items):
        if getattr(item, "type", None) != "tool_call_output_item":
            continue

        parsed = _safe_json(getattr(item, "output", ""))
        invoice_id = parsed.get("invoice_id") if isinstance(parsed, dict) else None
        if invoice_id:
            return str(invoice_id)

    return None


def _persist_pipeline_response(result, final_output) -> None:
    """Persist final pipeline response text to processed_invoices if possible."""
    invoice_id = _extract_invoice_id(result)
    if not invoice_id:
        return

    response_text = str(final_output) if final_output is not None else ""
    if not response_text:
        return

    try:
        db_queries.update_pipeline_response(invoice_id, response_text)
    except Exception:
        # Persistence failure should not break the invoice processing pipeline.
        pass
