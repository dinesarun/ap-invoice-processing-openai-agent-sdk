"""
Initialize SQLite database: create tables and seed realistic sample data.
Run directly: python -m database.init_db
"""
import sqlite3
import json
import os
import sys

# Allow running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import settings


CREATE_VENDOR_MASTER = """
CREATE TABLE IF NOT EXISTS vendor_master (
    vendor_id    TEXT PRIMARY KEY,
    vendor_name  TEXT NOT NULL,
    address      TEXT,
    tax_id       TEXT,
    payment_terms TEXT DEFAULT 'Net 30',
    bank_account TEXT,
    status       TEXT DEFAULT 'active',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_PURCHASE_ORDERS = """
CREATE TABLE IF NOT EXISTS purchase_orders (
    po_number   TEXT PRIMARY KEY,
    vendor_id   TEXT REFERENCES vendor_master(vendor_id),
    po_date     DATE,
    total_amount REAL,
    currency    TEXT DEFAULT 'USD',
    line_items  TEXT,
    status      TEXT DEFAULT 'open',
    department  TEXT,
    approver    TEXT
);
"""

CREATE_PROCESSED_INVOICES = """
CREATE TABLE IF NOT EXISTS processed_invoices (
    invoice_id       TEXT PRIMARY KEY,
    vendor_id        TEXT,
    po_number        TEXT,
    invoice_number   TEXT,
    invoice_date     DATE,
    total_amount     REAL,
    currency         TEXT,
    extracted_fields TEXT,
    confidence_score REAL,
    status           TEXT,
    decision_reason  TEXT,
    agent_trace      TEXT,
    processed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_REVIEW_QUEUE = """
CREATE TABLE IF NOT EXISTS review_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  TEXT REFERENCES processed_invoices(invoice_id),
    reason      TEXT,
    priority    TEXT DEFAULT 'medium',
    assigned_to TEXT,
    status      TEXT DEFAULT 'pending',
    notes       TEXT,
    resolved_by TEXT,
    resolved_at TIMESTAMP,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# ─── Sample Data ──────────────────────────────────────────────────────────────

VENDORS = [
    ("V001", "Acme Office Supplies", "123 Commerce Blvd, Chicago, IL 60601", "12-3456789", "Net 30", "ACC-001-4567", "active"),
    ("V002", "TechCorp Solutions", "456 Tech Park, Austin, TX 78701", "23-4567890", "Net 45", "ACC-002-8901", "active"),
    ("V003", "Global Logistics Inc.", "789 Harbor Dr, Los Angeles, CA 90001", "34-5678901", "Net 15", "ACC-003-2345", "active"),
    ("V004", "Summit Consulting Group", "321 Executive Way, New York, NY 10001", "45-6789012", "Net 60", "ACC-004-6789", "active"),
    ("V005", "Pacific Printing Co.", "654 Industrial Ave, Seattle, WA 98101", "56-7890123", "Net 30", "ACC-005-0123", "active"),
    ("V006", "Northeast Facilities Mgmt", "987 Campus Rd, Boston, MA 02101", "67-8901234", "Net 30", "ACC-006-4567", "active"),
    ("V007", "Midwest Data Systems", "147 Data Center Dr, Columbus, OH 43201", "78-9012345", "Net 45", "ACC-007-8901", "active"),
    ("V008", "Heritage Catering Services", "258 Culinary Ct, Nashville, TN 37201", "89-0123456", "Net 15", "ACC-008-2345", "active"),
    ("V009", "SkyView Travel Agency", "369 Airport Blvd, Denver, CO 80201", "90-1234567", "Net 30", "ACC-009-6789", "active"),
    ("V010", "Dormant Supplies Ltd.", "000 Old St, Nowhere, XX 00000", "11-2223333", "Net 30", "ACC-010-0001", "inactive"),
]

PURCHASE_ORDERS = [
    # Acme Office Supplies — open POs
    ("PO-2024-001", "V001", "2024-01-15", 2450.00, "USD",
     json.dumps([{"description": "A4 Copy Paper (500 sheets)", "qty": 50, "unit_price": 25.00, "amount": 1250.00},
                 {"description": "Ballpoint Pens (box of 50)", "qty": 20, "unit_price": 18.00, "amount": 360.00},
                 {"description": "Stapler + Staples Set", "qty": 20, "unit_price": 42.00, "amount": 840.00}]),
     "open", "Operations", "Sarah Johnson"),

    ("PO-2024-002", "V001", "2024-02-01", 1800.00, "USD",
     json.dumps([{"description": "Printer Ink Cartridges (HP)", "qty": 30, "unit_price": 45.00, "amount": 1350.00},
                 {"description": "File Folders (pack of 100)", "qty": 15, "unit_price": 30.00, "amount": 450.00}]),
     "open", "Finance", "Michael Chen"),

    # TechCorp Solutions
    ("PO-2024-005", "V002", "2024-01-20", 18500.00, "USD",
     json.dumps([{"description": "Dell Laptop 15\" (i7, 16GB)", "qty": 5, "unit_price": 1800.00, "amount": 9000.00},
                 {"description": "27\" 4K Monitor", "qty": 5, "unit_price": 650.00, "amount": 3250.00},
                 {"description": "Wireless Keyboard + Mouse Set", "qty": 10, "unit_price": 125.00, "amount": 1250.00},
                 {"description": "USB-C Docking Station", "qty": 10, "unit_price": 200.00, "amount": 2000.00},
                 {"description": "Enterprise AV Software License (annual)", "qty": 10, "unit_price": 300.00, "amount": 3000.00}]),
     "open", "IT", "David Park"),

    ("PO-2024-006", "V002", "2024-02-10", 9200.00, "USD",
     json.dumps([{"description": "Network Switch (24-port)", "qty": 4, "unit_price": 1200.00, "amount": 4800.00},
                 {"description": "CAT6 Ethernet Cable (1000ft)", "qty": 4, "unit_price": 180.00, "amount": 720.00},
                 {"description": "Rack Enclosure 42U", "qty": 2, "unit_price": 1840.00, "amount": 3680.00}]),
     "open", "IT", "David Park"),

    # Global Logistics Inc.
    ("PO-2024-010", "V003", "2024-01-10", 6750.00, "USD",
     json.dumps([{"description": "Freight Shipping — Q1 (domestic)", "qty": 1, "unit_price": 4500.00, "amount": 4500.00},
                 {"description": "Warehousing Fee — January", "qty": 1, "unit_price": 1500.00, "amount": 1500.00},
                 {"description": "Handling & Packaging", "qty": 1, "unit_price": 750.00, "amount": 750.00}]),
     "open", "Supply Chain", "Lisa Torres"),

    ("PO-2024-011", "V003", "2024-02-05", 4200.00, "USD",
     json.dumps([{"description": "Express Shipping — February", "qty": 1, "unit_price": 2800.00, "amount": 2800.00},
                 {"description": "Customs Clearance Fee", "qty": 1, "unit_price": 1400.00, "amount": 1400.00}]),
     "partially_received", "Supply Chain", "Lisa Torres"),

    # Summit Consulting Group
    ("PO-2024-015", "V004", "2024-01-25", 25000.00, "USD",
     json.dumps([{"description": "Strategy Consulting — Phase 1 (40 hrs)", "qty": 40, "unit_price": 350.00, "amount": 14000.00},
                 {"description": "Market Analysis Report", "qty": 1, "unit_price": 8000.00, "amount": 8000.00},
                 {"description": "Workshop Facilitation (2 days)", "qty": 2, "unit_price": 1500.00, "amount": 3000.00}]),
     "open", "Executive", "Tom Bradley"),

    # Pacific Printing Co.
    ("PO-2024-020", "V005", "2024-02-15", 3800.00, "USD",
     json.dumps([{"description": "Annual Report Printing (500 copies)", "qty": 500, "unit_price": 5.50, "amount": 2750.00},
                 {"description": "Marketing Brochures (1000 copies)", "qty": 1000, "unit_price": 0.80, "amount": 800.00},
                 {"description": "Design & Prepress Services", "qty": 1, "unit_price": 250.00, "amount": 250.00}]),
     "open", "Marketing", "Rachel Kim"),

    # Northeast Facilities
    ("PO-2024-025", "V006", "2024-01-05", 12000.00, "USD",
     json.dumps([{"description": "Janitorial Services — Q1", "qty": 3, "unit_price": 2500.00, "amount": 7500.00},
                 {"description": "HVAC Maintenance Contract", "qty": 1, "unit_price": 3000.00, "amount": 3000.00},
                 {"description": "Security System Monitoring (monthly)", "qty": 3, "unit_price": 500.00, "amount": 1500.00}]),
     "open", "Facilities", "James Wilson"),

    # Midwest Data Systems
    ("PO-2024-030", "V007", "2024-02-20", 8500.00, "USD",
     json.dumps([{"description": "Cloud Backup Service (annual)", "qty": 1, "unit_price": 4500.00, "amount": 4500.00},
                 {"description": "IT Support Contract — Q1", "qty": 1, "unit_price": 2500.00, "amount": 2500.00},
                 {"description": "Software License Renewal", "qty": 5, "unit_price": 300.00, "amount": 1500.00}]),
     "open", "IT", "Amy Zhang"),

    # Heritage Catering
    ("PO-2024-035", "V008", "2024-02-01", 5600.00, "USD",
     json.dumps([{"description": "Executive Team Catering — February (8 events)", "qty": 8, "unit_price": 700.00, "amount": 5600.00}]),
     "partially_received", "HR", "Carlos Rivera"),

    # SkyView Travel
    ("PO-2024-040", "V009", "2024-01-30", 15000.00, "USD",
     json.dumps([{"description": "Corporate Travel Management — Q1", "qty": 1, "unit_price": 8000.00, "amount": 8000.00},
                 {"description": "Hotel Bookings — Sales Team (estimated)", "qty": 1, "unit_price": 5000.00, "amount": 5000.00},
                 {"description": "Car Rental — Executive Travel", "qty": 1, "unit_price": 2000.00, "amount": 2000.00}]),
     "open", "Sales", "Patricia Lee"),
]


def init_db(db_path: str = None):
    path = db_path or settings.SQLITE_DB_PATH
    print(f"Initializing database at: {path}")
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    # Create tables
    cur.execute(CREATE_VENDOR_MASTER)
    cur.execute(CREATE_PURCHASE_ORDERS)
    cur.execute(CREATE_PROCESSED_INVOICES)
    cur.execute(CREATE_REVIEW_QUEUE)

    # Seed vendors (skip if already present)
    cur.executemany(
        "INSERT OR IGNORE INTO vendor_master "
        "(vendor_id, vendor_name, address, tax_id, payment_terms, bank_account, status) "
        "VALUES (?,?,?,?,?,?,?)",
        VENDORS,
    )

    # Seed POs
    cur.executemany(
        "INSERT OR IGNORE INTO purchase_orders "
        "(po_number, vendor_id, po_date, total_amount, currency, line_items, status, department, approver) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        PURCHASE_ORDERS,
    )

    conn.commit()
    conn.close()
    print(f"  ✅ Created tables: vendor_master, purchase_orders, processed_invoices, review_queue")
    print(f"  ✅ Seeded {len(VENDORS)} vendors and {len(PURCHASE_ORDERS)} purchase orders")


if __name__ == "__main__":
    init_db()
