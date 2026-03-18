"""
Chat Intent Guardrail — LLM-judgment guardrail for chat queries.

Demonstrates an LLM-based input guardrail that keeps the Triage Agent scoped
to its domain. Without this, anyone could use the AP assistant as a general-purpose
chatbot (ask it to write poems, explain recipes, help with unrelated code, etc.),
burning tokens and exposing the agent to off-domain misuse.

Why LLM judgment (not keyword matching):
  AP-related queries are too varied for a keyword list. "What's the status of vendor
  Acme?" and "Are there any pending items?" are clearly in scope; "How do I make
  masala dosa?" is clearly not. An LLM guardrail handles the ambiguous middle ground
  far better than rules.

Fires only for chat queries (no PDF path in message).
Passes through silently for all invoice upload requests.
"""
import re
from pydantic import BaseModel
from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    TResponseInputItem,
    Runner,
    input_guardrail,
)
from app_agents.setup import get_deployment_name


class ChatIntentOutput(BaseModel):
    is_ap_related: bool
    reason: str


_intent_agent: Agent | None = None


def _get_intent_agent() -> Agent:
    global _intent_agent
    if _intent_agent is None:
        _intent_agent = Agent(
            name="Chat Intent Checker",
            instructions="""You are a scope guardrail for an AP (Accounts Payable) invoice processing assistant.

Your job: decide if a user's chat query is within the scope of AP invoice operations.

IN SCOPE → is_ap_related=True:
  - Invoice questions: status, history, specific invoices, amounts
  - Vendor questions: vendor details, approval history, risk level
  - Purchase order questions: PO status, matching, variance
  - Review queue: pending items, flagged invoices, resolution status
  - AP statistics and reporting: approval rates, processing stats, summaries
  - Workflow questions: how the pipeline works, why something was flagged
  - General finance/procurement context relevant to AP operations
  - Questions about the system itself ("how does this work?", "what agents are used?")

OUT OF SCOPE → is_ap_related=False:
  - Completely unrelated topics: cooking, travel, sports, entertainment, general coding
  - Requests to use the assistant as a general chatbot
  - Personal advice, creative writing, jokes
  - Anything with no plausible connection to AP/invoicing/procurement/finance

Be generous — if there is any reasonable connection to AP, procurement, or financial
operations, allow it. Only block queries that are clearly and obviously unrelated.
Return is_ap_related and a brief reason (one sentence).""",
            model=get_deployment_name(),
            output_type=ChatIntentOutput,
        )
    return _intent_agent


def _extract_text(input: str | list[TResponseInputItem]) -> str:
    if isinstance(input, str):
        return input
    if isinstance(input, list):
        parts = []
        for item in input:
            if isinstance(item, dict) and item.get("type") == "input_text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(parts)
    return str(input)


@input_guardrail
async def chat_intent_guardrail(
    ctx: RunContextWrapper,
    agent: Agent,
    input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    """
    LLM-judgment guardrail: ensures chat queries are within AP domain scope.
    Passes through silently for all invoice upload requests (PDF path present).
    """
    text = _extract_text(input)

    # Invoice uploads always contain a .pdf path — skip intent check entirely
    if re.search(r"[\./A-Za-z0-9_-][^\s]*\.pdf", text, re.IGNORECASE):
        return GuardrailFunctionOutput(
            output_info=ChatIntentOutput(is_ap_related=True, reason="Invoice upload — not a chat query"),
            tripwire_triggered=False,
        )

    result = await Runner.run(
        _get_intent_agent(),
        input=f"Is this query within scope of an AP invoice processing assistant?\n\n\"{text}\"",
        context=ctx.context,
    )
    output = result.final_output_as(ChatIntentOutput)

    return GuardrailFunctionOutput(
        output_info=output,
        tripwire_triggered=not output.is_ap_related,
    )
