"""
Input Guardrail — validates that the uploaded file is a valid PDF.

Demonstrates the GUARDRAIL primitive of the OpenAI Agents SDK.
Input guardrails run BEFORE the agent processes the input, allowing
early rejection of invalid inputs without burning LLM tokens.

The guardrail checks:
1. File extension is .pdf
2. File magic bytes are %PDF (PDF signature)
3. File is not empty
"""
import os
import re
from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    TResponseInputItem,
    input_guardrail,
)
from pydantic import BaseModel


class PDFValidationOutput(BaseModel):
    is_valid_pdf: bool
    reason: str


@input_guardrail
async def pdf_file_guardrail(
    ctx: RunContextWrapper,
    agent: Agent,
    input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    """
    Validate that the input references a valid PDF file.

    Extracts the file path from the input message and checks:
    - The file exists on disk
    - The extension is .pdf (case-insensitive)
    - The file starts with the PDF magic bytes %PDF
    """
    # Extract text from input
    if isinstance(input, str):
        text = input
    elif isinstance(input, list):
        parts = []
        for item in input:
            if isinstance(item, dict) and item.get("type") == "input_text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        text = " ".join(parts)
    else:
        text = str(input)

    # Extract file path from the message
    # Matches typical "Process this invoice PDF located at: /path/to/file.pdf"
    path_match = re.search(r"(?:at:|path:)?\s*(/[^\s]+\.pdf)", text, re.IGNORECASE)

    if not path_match:
        # No file path found — let the agent handle it (might be a status query etc.)
        return GuardrailFunctionOutput(
            output_info=PDFValidationOutput(
                is_valid_pdf=True,
                reason="No file path detected in input — passing through",
            ),
            tripwire_triggered=False,
        )

    file_path = path_match.group(1)

    # Check existence
    if not os.path.exists(file_path):
        return GuardrailFunctionOutput(
            output_info=PDFValidationOutput(
                is_valid_pdf=False,
                reason=f"File not found: {file_path}",
            ),
            tripwire_triggered=True,
        )

    # Check extension
    if not file_path.lower().endswith(".pdf"):
        return GuardrailFunctionOutput(
            output_info=PDFValidationOutput(
                is_valid_pdf=False,
                reason=f"File is not a PDF (extension: {os.path.splitext(file_path)[1]})",
            ),
            tripwire_triggered=True,
        )

    # Check file size
    if os.path.getsize(file_path) == 0:
        return GuardrailFunctionOutput(
            output_info=PDFValidationOutput(
                is_valid_pdf=False,
                reason="File is empty (0 bytes)",
            ),
            tripwire_triggered=True,
        )

    # Check PDF magic bytes
    try:
        with open(file_path, "rb") as f:
            header = f.read(5)
        if not header.startswith(b"%PDF"):
            return GuardrailFunctionOutput(
                output_info=PDFValidationOutput(
                    is_valid_pdf=False,
                    reason="File does not have valid PDF header (magic bytes %PDF not found)",
                ),
                tripwire_triggered=True,
            )
    except OSError as e:
        return GuardrailFunctionOutput(
            output_info=PDFValidationOutput(
                is_valid_pdf=False,
                reason=f"Cannot read file: {e}",
            ),
            tripwire_triggered=True,
        )

    return GuardrailFunctionOutput(
        output_info=PDFValidationOutput(
            is_valid_pdf=True,
            reason=f"Valid PDF file confirmed: {file_path}",
        ),
        tripwire_triggered=False,
    )
