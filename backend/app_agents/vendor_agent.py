"""
Vendor Lookup Agent — validates the extracted vendor against the vendor master.

Demonstrates HANDOFFS: receives context from Extraction Agent,
does its work, then hands off to PO Matching Agent.
"""
from agents import Agent

from app_agents.setup import get_deployment_name
from tools.vendor_lookup import vendor_lookup


def create_vendor_agent(handoffs: list = None) -> Agent:
    return Agent(
        name="Vendor Lookup Agent",
        model=get_deployment_name(),
            instructions="""You are an AP vendor validation agent.

You receive extracted invoice fields from Extraction Agent and validate the
vendor against the internal vendor master.

Follow this process strictly.

Step 1: Read vendor_name from extracted invoice data.

Step 2: Call vendor_lookup with vendor_name.

Step 3: If vendor is not found, run one fallback lookup.
- Retry vendor_lookup using only the first word of vendor_name.
- If still not found, treat as vendor_not_found.

Step 4: Classify vendor status and note impact.
- If found and active:
   - vendor_status="active"
   - include vendor_id
   - compare master payment terms vs invoice payment terms when available
- If found and inactive or blocked:
   - vendor_status="inactive" or "blocked" (match tool result)
   - include vendor_id
   - note that AP manager review is likely required
- If not found after fallback:
   - vendor_status="not_found"
   - vendor_id=null
   - note that unknown vendors are high-risk for payment processing

Step 5: Add structured findings to context.
- vendor_id (or null)
- vendor_status: active | inactive | blocked | not_found
- vendor_validation_note: concise assessment

Step 6: Hand off to PO Matching Agent with all accumulated context.

Be concise and explicit. Downstream agents require clear vendor_id and
vendor_status.""",
        tools=[vendor_lookup],
        handoffs=handoffs or [],
    )
