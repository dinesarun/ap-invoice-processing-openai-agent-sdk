"""
Output Guardrail — validates the Decision Agent's final output has required fields.

Demonstrates OUTPUT guardrails: these run AFTER the agent produces its response,
allowing validation and rejection of malformed outputs before they're returned
to the caller.

This guardrail ensures the decision output always contains:
- invoice_id
- status (one of: approved / flagged_for_review / rejected)
- decision_reason
- confidence_score
"""
import json
import re
from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    output_guardrail,
)
from pydantic import BaseModel
from typing import Any


VALID_STATUSES = {"approved", "flagged_for_review", "rejected"}


class DecisionValidationOutput(BaseModel):
    is_valid: bool
    missing_fields: list[str]
    reason: str


def _extract_json_from_text(text: str) -> dict | None:
    """Try to extract a JSON object from a text string."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown code fence
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find a raw JSON object in the text
    match = re.search(r"\{[^{}]*\"invoice_id\"[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


@output_guardrail
async def decision_output_guardrail(
    ctx: RunContextWrapper,
    agent: Agent,
    output: Any,
) -> GuardrailFunctionOutput:
    """
    Validate that the Decision Agent's output contains all required fields.

    Required fields: invoice_id, status, decision_reason (or flag_reason), confidence_score.
    The status must be one of: approved, flagged_for_review, rejected.
    """
    # Extract text from output
    if hasattr(output, "final_output"):
        text = str(output.final_output)
    elif isinstance(output, str):
        text = output
    else:
        text = str(output)

    # Check if the text references a successful tool call result
    # (the approve_invoice or flag_for_review tools return JSON with these fields)
    required_keywords = ["invoice_id", "status", "confidence_score"]
    missing = []

    for keyword in required_keywords:
        if keyword not in text:
            missing.append(keyword)

    # Check for decision reason (either field name works)
    if "decision_reason" not in text and "flag_reason" not in text:
        missing.append("decision_reason/flag_reason")

    # Check for valid status value
    has_valid_status = any(s in text for s in VALID_STATUSES)
    if not has_valid_status:
        missing.append("valid_status_value")

    if missing:
        return GuardrailFunctionOutput(
            output_info=DecisionValidationOutput(
                is_valid=False,
                missing_fields=missing,
                reason=(
                    f"Decision output is missing required fields: {missing}. "
                    "The decision agent must call either approve_invoice or flag_for_review tool."
                ),
            ),
            tripwire_triggered=True,
        )

    return GuardrailFunctionOutput(
        output_info=DecisionValidationOutput(
            is_valid=True,
            missing_fields=[],
            reason="Decision output contains all required fields",
        ),
        tripwire_triggered=False,
    )
