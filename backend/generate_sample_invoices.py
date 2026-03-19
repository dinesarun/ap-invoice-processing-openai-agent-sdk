"""
Generate sample PDF invoices for testing the AP agent pipeline.

4 invoices covering the main scenarios:
  1. Happy path  — Acme, PO matches exactly → auto-approve
  2. Amount mismatch — TechCorp, 15% over PO amount → flag for review
  3. Unknown vendor — NewVendor XYZ not in master → flag for review
  4. No PO reference — Global Logistics, no PO number → flag for review

Run: python generate_sample_invoices.py
"""
import os
import sys
from pathlib import Path
import unicodedata

try:
    from fpdf import FPDF
except ImportError:
    print("fpdf2 not installed. Run: pip install fpdf2")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).parent.parent / "sample_invoices"
OUTPUT_DIR.mkdir(exist_ok=True)


def normalize_pdf_text(value: str) -> str:
    """Convert common Unicode punctuation to ASCII for core PDF fonts."""
    normalized = unicodedata.normalize("NFKD", value)
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u2192": "->",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized.encode("latin-1", "ignore").decode("latin-1")


class InvoicePDF(FPDF):
    """Simple invoice PDF layout using fpdf2."""

    def safe_cell(self, *args, text: str = "", **kwargs):
        return self.cell(*args, text=normalize_pdf_text(text), **kwargs)

    def safe_multi_cell(self, *args, text: str = "", **kwargs):
        return self.multi_cell(*args, text=normalize_pdf_text(text), **kwargs)

    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def draw_invoice(self, data: dict):
        self.add_page()
        self.set_margins(20, 20, 20)

        # ── Vendor block (top-left) ──
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(30, 64, 175)  # Blue
        self.safe_cell(0, 10, text=data["vendor_name"], ln=True)

        self.set_font("Helvetica", "", 10)
        self.set_text_color(60)
        for line in data.get("vendor_address", "").split("\n"):
            self.safe_cell(0, 6, text=line, ln=True)
        if data.get("vendor_tax_id"):
            self.safe_cell(0, 6, text=f"Tax ID: {data['vendor_tax_id']}", ln=True)

        self.ln(5)

        # ── INVOICE label (right side) ──
        self.set_xy(120, 20)
        self.set_font("Helvetica", "B", 24)
        self.set_text_color(30, 64, 175)
        self.safe_cell(70, 12, text="INVOICE", align="R", ln=True)

        # ── Invoice meta table ──
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60)

        meta = [
            ("Invoice Number:", data.get("invoice_number", "")),
            ("Invoice Date:", data.get("invoice_date", "")),
            ("Due Date:", data.get("due_date", "")),
            ("Payment Terms:", data.get("payment_terms", "Net 30")),
        ]
        if data.get("po_number"):
            meta.append(("PO Number:", data["po_number"]))

        for label, value in meta:
            self.set_x(120)
            self.set_font("Helvetica", "B", 10)
            self.safe_cell(50, 7, text=label)
            self.set_font("Helvetica", "", 10)
            self.safe_cell(0, 7, text=value, ln=True)

        self.ln(8)

        # ── Bill To ──
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(30, 64, 175)
        self.safe_cell(0, 7, text="Bill To:", ln=True)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60)
        for line in data.get("bill_to", "AP Department\nYour Company Inc.").split("\n"):
            self.safe_cell(0, 6, text=line, ln=True)

        self.ln(8)

        # ── Line items table ──
        # Header row
        self.set_fill_color(30, 64, 175)
        self.set_text_color(255)
        self.set_font("Helvetica", "B", 10)
        col_widths = [90, 20, 30, 30]
        headers = ["Description", "Qty", "Unit Price", "Amount"]
        for w, h in zip(col_widths, headers):
            self.safe_cell(w, 8, text=h, fill=True, align="C")
        self.ln()

        # Data rows
        self.set_text_color(40)
        self.set_font("Helvetica", "", 9)
        fill = False
        for i, item in enumerate(data.get("line_items", [])):
            self.set_fill_color(240, 244, 255) if fill else self.set_fill_color(255)
            self.safe_cell(col_widths[0], 7, text=item["description"][:55], fill=True)
            self.safe_cell(col_widths[1], 7, text=str(item["qty"]), fill=True, align="C")
            self.safe_cell(col_widths[2], 7, text=f"${item['unit_price']:,.2f}", fill=True, align="R")
            self.safe_cell(col_widths[3], 7, text=f"${item['amount']:,.2f}", fill=True, align="R")
            self.ln()
            fill = not fill

        self.ln(4)

        # ── Totals ──
        def total_row(label, value, bold=False):
            self.set_x(120)
            self.set_font("Helvetica", "B" if bold else "", 10)
            self.set_text_color(40)
            self.safe_cell(50, 7, text=label)
            self.set_font("Helvetica", "B" if bold else "", 10)
            self.safe_cell(0, 7, text=value, align="R", ln=True)

        total_row("Subtotal:", f"${data.get('subtotal', 0):,.2f}")
        total_row(f"Tax ({data.get('tax_rate', 0)}%):", f"${data.get('tax_amount', 0):,.2f}")

        # Divider
        self.set_x(120)
        self.set_draw_color(30, 64, 175)
        self.line(120, self.get_y(), 190, self.get_y())
        self.ln(2)
        total_row("Total:", f"${data.get('total_amount', 0):,.2f}", bold=True)

        self.ln(10)

        # ── Payment info ──
        if data.get("bank_account"):
            self.set_font("Helvetica", "", 9)
            self.set_text_color(100)
            self.safe_cell(0, 6, text=f"Please remit payment to: Bank Account {data['bank_account']}", ln=True)

        # ── Notes ──
        if data.get("notes"):
            self.ln(5)
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(120)
            self.safe_multi_cell(0, 6, text=data["notes"])


# ─── Invoice definitions ──────────────────────────────────────────────────────

INVOICES = [
    {
        "filename": "invoice_001_acme_happy_path.pdf",
        "description": "Happy path — Acme Office Supplies, exact PO match",
        "vendor_name": "Acme Office Supplies",
        "vendor_address": "123 Commerce Blvd, Chicago, IL 60601",
        "vendor_tax_id": "12-3456789",
        "bill_to": "AP Department\nYour Company Inc.\n500 Corporate Plaza\nNew York, NY 10001",
        "invoice_number": "INV-2024-0891",
        "invoice_date": "2024-03-01",
        "due_date": "2024-03-31",
        "payment_terms": "Net 30",
        "po_number": "PO-2024-001",
        "line_items": [
            {"description": "A4 Copy Paper (500 sheets)", "qty": 50, "unit_price": 25.00, "amount": 1250.00},
            {"description": "Ballpoint Pens (box of 50)", "qty": 20, "unit_price": 18.00, "amount": 360.00},
            {"description": "Stapler + Staples Set", "qty": 20, "unit_price": 42.00, "amount": 840.00},
        ],
        "subtotal": 2450.00,
        "tax_rate": 0,
        "tax_amount": 0.00,
        "total_amount": 2450.00,
        "bank_account": "ACC-001-4567",
        "notes": "Thank you for your business! Payment due within 30 days.",
    },
    {
        "filename": "invoice_002_techcorp_amount_mismatch.pdf",
        "description": "Amount mismatch — TechCorp, 19.6% over PO amount (should flag)",
        "vendor_name": "TechCorp Solutions",
        "vendor_address": "456 Tech Park, Austin, TX 78701",
        "vendor_tax_id": "23-4567890",
        "bill_to": "IT Department\nYour Company Inc.\n500 Corporate Plaza\nNew York, NY 10001",
        "invoice_number": "INV-TC-2024-0342",
        "invoice_date": "2024-03-05",
        "due_date": "2024-04-19",
        "payment_terms": "Net 45",
        "po_number": "PO-2024-005",
        "line_items": [
            {"description": "Dell Laptop 15\" (i7, 16GB RAM)", "qty": 5, "unit_price": 1800.00, "amount": 9000.00},
            {"description": "27\" 4K Monitor", "qty": 5, "unit_price": 650.00, "amount": 3250.00},
            {"description": "Wireless Keyboard + Mouse Set", "qty": 10, "unit_price": 125.00, "amount": 1250.00},
            {"description": "USB-C Docking Station", "qty": 10, "unit_price": 200.00, "amount": 2000.00},
            {"description": "Enterprise AV Software License (annual)", "qty": 10, "unit_price": 300.00, "amount": 3000.00},
            {"description": "Rush Delivery & Installation Fee", "qty": 1, "unit_price": 3625.00, "amount": 3625.00},
        ],
        "subtotal": 22125.00,
        "tax_rate": 0,
        "tax_amount": 0.00,
        "total_amount": 22125.00,
        "bank_account": "ACC-002-8901",
        "notes": "Additional rush delivery fee applies per amended delivery request dated Feb 28, 2024.",
    },
    {
        "filename": "invoice_003_newvendor_unknown.pdf",
        "description": "Unknown vendor — NewVendor XYZ not in master",
        "vendor_name": "NewVendor XYZ Corporation",
        "vendor_address": "999 Startup Lane, San Francisco, CA 94105",
        "vendor_tax_id": "99-8877665",
        "bill_to": "AP Department\nYour Company Inc.\n500 Corporate Plaza\nNew York, NY 10001",
        "invoice_number": "NV-2024-001",
        "invoice_date": "2024-03-10",
        "due_date": "2024-04-09",
        "payment_terms": "Net 30",
        "po_number": "PO-2024-099",
        "line_items": [
            {"description": "Custom Software Development (40 hrs)", "qty": 40, "unit_price": 150.00, "amount": 6000.00},
            {"description": "QA Testing Services (20 hrs)", "qty": 20, "unit_price": 100.00, "amount": 2000.00},
        ],
        "subtotal": 8000.00,
        "tax_rate": 8,
        "tax_amount": 640.00,
        "total_amount": 8640.00,
        "bank_account": "Wire: 123456789",
        "notes": "First invoice — new vendor onboarding in progress. Contact: billing@newvendorxyz.com",
    },
    {
        "filename": "invoice_004_global_logistics_no_po.pdf",
        "description": "Missing PO — Global Logistics invoice without PO number",
        "vendor_name": "Global Logistics Inc.",
        "vendor_address": "789 Harbor Dr, Los Angeles, CA 90001",
        "vendor_tax_id": "34-5678901",
        "bill_to": "Supply Chain Department\nYour Company Inc.\n500 Corporate Plaza\nNew York, NY 10001",
        "invoice_number": "GLI-2024-0156",
        "invoice_date": "2024-03-08",
        "due_date": "2024-03-23",
        "payment_terms": "Net 15",
        "po_number": "",  # No PO number — intentionally missing
        "line_items": [
            {"description": "Freight Shipping Services — March 2024", "qty": 1, "unit_price": 5200.00, "amount": 5200.00},
            {"description": "Warehousing Fee — March 2024", "qty": 1, "unit_price": 1500.00, "amount": 1500.00},
            {"description": "Fuel Surcharge (8% of freight)", "qty": 1, "unit_price": 420.00, "amount": 420.00},
        ],
        "subtotal": 7120.00,
        "tax_rate": 0,
        "tax_amount": 0.00,
        "total_amount": 7120.00,
        "bank_account": "ACC-003-2345",
        "notes": "No PO referenced — recurring monthly services. Please contact logistics@globallogistics.com for PO assignment.",
    },
]


VIDEO_INVOICES = [
    {
        "filename": "video_invoice_A_summit_consulting.pdf",
        "description": "Video demo A — Summit Consulting, strategy engagement, exact PO match",
        "vendor_name": "Summit Consulting Group",
        "vendor_address": "321 Executive Way, New York, NY 10001",
        "vendor_tax_id": "45-6789012",
        "bill_to": "Executive Department\nYour Company Inc.\n500 Corporate Plaza\nNew York, NY 10001",
        "invoice_number": "SCG-2024-0781",
        "invoice_date": "2024-03-12",
        "due_date": "2024-05-11",
        "payment_terms": "Net 60",
        "po_number": "PO-2024-015",
        "line_items": [
            {"description": "Strategy Consulting - Phase 1 (40 hrs @ $350/hr)", "qty": 40, "unit_price": 350.00, "amount": 14000.00},
            {"description": "Market Analysis Report", "qty": 1, "unit_price": 8000.00, "amount": 8000.00},
            {"description": "Workshop Facilitation (2 days)", "qty": 2, "unit_price": 1500.00, "amount": 3000.00},
        ],
        "subtotal": 25000.00,
        "tax_rate": 0,
        "tax_amount": 0.00,
        "total_amount": 25000.00,
        "bank_account": "ACC-004-6789",
        "notes": "Deliverables: Phase 1 strategy deck, market analysis PDF, and workshop summary report delivered on March 10, 2024.",
    },
    {
        "filename": "video_invoice_B_pacific_printing.pdf",
        "description": "Video demo B — Pacific Printing, marketing collateral, exact PO match",
        "vendor_name": "Pacific Printing Co.",
        "vendor_address": "654 Industrial Ave, Seattle, WA 98101",
        "vendor_tax_id": "56-7890123",
        "bill_to": "Marketing Department\nYour Company Inc.\n500 Corporate Plaza\nNew York, NY 10001",
        "invoice_number": "PPC-2024-0334",
        "invoice_date": "2024-03-14",
        "due_date": "2024-04-13",
        "payment_terms": "Net 30",
        "po_number": "PO-2024-020",
        "line_items": [
            {"description": "Annual Report Printing - 500 copies", "qty": 500, "unit_price": 5.50, "amount": 2750.00},
            {"description": "Marketing Brochures - 1000 copies", "qty": 1000, "unit_price": 0.80, "amount": 800.00},
            {"description": "Design & Prepress Services", "qty": 1, "unit_price": 250.00, "amount": 250.00},
        ],
        "subtotal": 3800.00,
        "tax_rate": 0,
        "tax_amount": 0.00,
        "total_amount": 3800.00,
        "bank_account": "ACC-005-0123",
        "notes": "All print files proofed and approved by Rachel Kim (Marketing) on March 8, 2024. Delivery completed March 13.",
    },
    {
        "filename": "video_invoice_C_midwest_data.pdf",
        "description": "Video demo C — Midwest Data Systems, IT services, within variance",
        "vendor_name": "Midwest Data Systems",
        "vendor_address": "147 Data Center Dr, Columbus, OH 43201",
        "vendor_tax_id": "78-9012345",
        "bill_to": "IT Department\nYour Company Inc.\n500 Corporate Plaza\nNew York, NY 10001",
        "invoice_number": "MDS-2024-0512",
        "invoice_date": "2024-03-15",
        "due_date": "2024-04-29",
        "payment_terms": "Net 45",
        "po_number": "PO-2024-030",
        "line_items": [
            {"description": "Cloud Backup Service - Annual License", "qty": 1, "unit_price": 4500.00, "amount": 4500.00},
            {"description": "IT Support Contract - Q1 (Jan-Mar 2024)", "qty": 1, "unit_price": 2500.00, "amount": 2500.00},
            {"description": "Software License Renewal (5 seats)", "qty": 5, "unit_price": 280.00, "amount": 1400.00},
        ],
        "subtotal": 8400.00,
        "tax_rate": 0,
        "tax_amount": 0.00,
        "total_amount": 8400.00,
        "bank_account": "ACC-007-8901",
        "notes": "License keys delivered digitally. Support contract SLA: 4-hour response. Renewal confirmation ref: MDS-R-2024-030.",
    },
]


def generate_all():
    print(f"Generating {len(INVOICES)} sample invoices in: {OUTPUT_DIR}")
    for inv in INVOICES:
        pdf = InvoicePDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.draw_invoice(inv)
        out_path = OUTPUT_DIR / inv["filename"]
        pdf.output(str(out_path))
        print(f"  ✅ {inv['filename']} — {inv['description']}")

    print(f"\nGenerating {len(VIDEO_INVOICES)} video demo invoices...")
    for inv in VIDEO_INVOICES:
        pdf = InvoicePDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.draw_invoice(inv)
        out_path = OUTPUT_DIR / inv["filename"]
        pdf.output(str(out_path))
        print(f"  ✅ {inv['filename']} — {inv['description']}")

    print("Done!")


if __name__ == "__main__":
    generate_all()
