"""
Extraction Agent — uses LLMWhisperer to OCR the PDF, then parses invoice fields.

This agent demonstrates the TOOL USE primitive of the Agents SDK:
  - The agent is given the llmwhisperer_extract tool
  - It decides when and how to call the tool
  - After getting the raw text, the LLM itself parses the structured fields
  - It self-assigns a confidence score based on extraction quality
"""
from agents import Agent

from agents.setup import get_deployment_name
from tools.llmwhisperer_tool import llmwhisperer_extract


def create_extraction_agent(handoffs: list = None) -> Agent:
    """
    Factory that creates the Extraction Agent.
    handoffs are injected by the orchestrator to avoid circular imports.
    """
    return Agent(
        name="Extraction Agent",
        model=get_deployment_name(),
        instructions="""You are an expert AP invoice data extraction agent.

Your job is to extract structured data from invoice PDFs with high accuracy.

WORKFLOW:
1. Call the llmwhisperer_extract tool with the provided file_path to get raw OCR text.
2. Carefully parse the raw text to identify ALL of these fields:
   - invoice_number: The invoice/bill number
   - invoice_date: Date of the invoice (YYYY-MM-DD format)
   - due_date: Payment due date (YYYY-MM-DD format)
   - payment_terms: e.g., "Net 30", "Net 45"
   - vendor_name: The name of the company issuing the invoice
   - vendor_address: Full address of the vendor
   - vendor_tax_id: Tax ID / EIN if present
   - bill_to: Who the invoice is addressed to
   - po_number: Purchase order number referenced (critical!)
   - line_items: Array of {description, qty, unit_price, amount} for each item
   - subtotal: Pre-tax total
   - tax_amount: Tax amount (0 if none)
   - tax_rate: Tax percentage (0 if none)
   - total_amount: Final invoice total (CRITICAL — must be accurate)
   - currency: Currency code (default "USD")

3. Assign a confidence_score (0.0 to 1.0) based on:
   - 1.0: All fields clearly visible, amounts add up correctly
   - 0.8-0.9: Most fields found, minor uncertainty in a few
   - 0.6-0.79: Several fields missing or unclear
   - Below 0.6: Major extraction issues (poor scan quality, unusual format)

4. Return a JSON object with all extracted fields plus the confidence_score.

IMPORTANT:
- Always convert amounts to numbers (not strings with $ signs)
- If a field is not found, set it to null (not an empty string)
- Double-check that line item amounts sum to the subtotal
- The total_amount is the most critical field — flag low confidence if unclear
- Hand off to the Vendor Lookup Agent once extraction is complete

Output your result as a structured JSON object with all extracted fields.
Then explicitly say "Handing off to Vendor Lookup Agent" and hand off.""",
        tools=[llmwhisperer_extract],
        handoffs=handoffs or [],
    )
