#!/usr/bin/env python3
"""
Generate a deterministic minimal test PDF fixture for integration tests.

Output: ai_server/tests/fixtures/test_sample.pdf

The content is fixed so CI / local runs always produce the same file.
Requires: pymupdf (already in requirements.txt as pymupdf==1.27.2.2)

Usage:
    python scripts/generate_test_pdf.py
    python scripts/generate_test_pdf.py --output /custom/path/test.pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).parent.parent / "tests" / "fixtures" / "test_sample.pdf"


def build_pdf(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise SystemExit("ERROR: PyMuPDF not installed.\n  Run: pip install pymupdf")

    doc = fitz.open()

    # ── Page 1: structured text content ──────────────────────────────────────
    p1 = doc.new_page(width=595, height=842)  # A4 portrait

    blocks_p1 = [
        # (x, y, fontsize, text)
        (50,  50, 18, "Knowledge Hub Test Document — Logistics Claims SOP"),
        (50,  80, 10, "Version: 1.0  |  Classification: Internal  |  Effective: 2026-01-01"),
        (50,  95, 10, "Owner: Claims Operations  |  Review cycle: Annual"),

        (50, 130, 14, "1. Purpose"),
        (50, 152, 11, "This Standard Operating Procedure defines the process for handling"),
        (50, 167, 11, "logistics claims including theft, damage, and liability incidents."),
        (50, 182, 11, "It is a deterministic fixture for assistant pipeline integration tests."),

        (50, 218, 14, "2. Scope"),
        (50, 240, 11, "Applies to all claims submitted through the logistics network."),
        (50, 255, 11, "Covers domestic and international shipments across all carrier types."),

        (50, 291, 14, "3. Responsibilities"),
        (50, 313, 11, "Claims Coordinator: receives and logs all incoming claims within 24 hours."),
        (50, 328, 11, "Field Adjuster: conducts on-site inspection within 72 hours of notification."),
        (50, 343, 11, "Regional Manager: approves settlements exceeding USD 10,000."),
        (50, 358, 11, "Legal Team: reviews claims with litigation risk or third-party liability."),

        (50, 394, 14, "4. Claim Filing Deadlines"),
        (50, 416, 11, "Theft claims must be filed within 30 days of the incident date."),
        (50, 431, 11, "Damage claims: 60 days from delivery confirmation."),
        (50, 446, 11, "Liability claims: 90 days from incident report filing."),
        (50, 461, 11, "Late submissions require written approval from the Regional Manager."),
        (50, 476, 11, "All deadlines are calendar days unless stated otherwise."),

        (50, 512, 14, "5. Documentation Requirements"),
        (50, 534, 11, "Required for all claims: incident report, carrier bill of lading,"),
        (50, 549, 11, "photographic evidence, and customer statement of loss."),
        (50, 564, 11, "Additional for theft: police report within 48 hours of filing."),
        (50, 579, 11, "Additional for damage: third-party inspection report if value > USD 5,000."),
    ]

    for x, y, size, text in blocks_p1:
        p1.insert_text((x, y), text, fontsize=size, fontname="helv")

    # ── Page 2: table + definitions ───────────────────────────────────────────
    p2 = doc.new_page(width=595, height=842)

    p2.insert_text((50, 50), "6. Claim Processing Timeline", fontsize=14, fontname="helv")

    # table header + rows
    table = [
        ("Stage",         "Max Duration", "Responsible Party", "Mandatory"),
        ("Receipt",       "1 day",        "Claims Coordinator", "Yes"),
        ("Verification",  "3 days",       "Field Adjuster",     "Yes"),
        ("Investigation", "7 days",       "Senior Adjuster",    "Conditional"),
        ("Negotiation",   "10 days",      "Regional Manager",   "Yes"),
        ("Settlement",    "5 days",       "Finance Team",       "Yes"),
        ("Closure",       "1 day",        "Claims Coordinator", "Yes"),
    ]

    col_x   = [50, 170, 295, 430]
    row_h   = 20
    y_start = 80

    for row_i, row in enumerate(table):
        y = y_start + row_i * row_h
        is_header = row_i == 0
        for col_i, cell in enumerate(row):
            p2.insert_text(
                (col_x[col_i], y),
                cell,
                fontsize=11 if not is_header else 11,
                fontname="hebo" if is_header else "helv",
            )

    p2.insert_text((50, 240), "7. Escalation Criteria", fontsize=14, fontname="helv")
    p2.insert_text((50, 262), "Claims are escalated to senior management when:", fontsize=11, fontname="helv")
    p2.insert_text((50, 278), "  - Claim value exceeds USD 50,000", fontsize=11, fontname="helv")
    p2.insert_text((50, 293), "  - Third-party legal action is threatened", fontsize=11, fontname="helv")
    p2.insert_text((50, 308), "  - Carrier disputes liability entirely", fontsize=11, fontname="helv")
    p2.insert_text((50, 323), "  - Repeat incidents from the same carrier within 90 days", fontsize=11, fontname="helv")

    p2.insert_text((50, 363), "8. Definitions", fontsize=14, fontname="helv")
    definitions = [
        ("Claim",           "Formal request for compensation due to loss or damage."),
        ("Bill of Lading",  "Carrier-issued shipment receipt and transport contract."),
        ("Adjuster",        "Person responsible for investigating and evaluating claims."),
        ("Settlement",      "Agreed compensation amount between claimant and insurer."),
        ("SOP",             "Standard Operating Procedure — this document type."),
    ]
    y_def = 385
    for term, definition in definitions:
        p2.insert_text((50,  y_def), f"{term}:", fontsize=11, fontname="hebo")
        p2.insert_text((160, y_def), definition,  fontsize=11, fontname="helv")
        y_def += 18

    # ── Page 3: additional text for chunking coverage ─────────────────────────
    p3 = doc.new_page(width=595, height=842)

    p3.insert_text((50, 50), "9. Carrier Performance Review", fontsize=14, fontname="helv")
    long_text = (
        "Carrier performance is reviewed quarterly based on claim frequency, "
        "resolution time, and settlement rate. Carriers exceeding a 5% claim rate "
        "over three consecutive quarters are placed on a probationary watch list. "
        "A formal remediation plan must be submitted within 30 days. Failure to "
        "comply results in carrier contract suspension pending executive review.\n\n"
        "Performance data is sourced from the document management system "
        "and cross-referenced against the carrier's self-reported incident logs. "
        "Discrepancies greater than 10% are flagged automatically for investigation.\n\n"
        "The Claims Operations team publishes an annual summary report by January 31st "
        "covering: total claims filed, total settlements paid, average resolution time, "
        "and top five claim categories by volume and value."
    )
    lines = long_text.split("\n")
    y_txt = 75
    for line in lines:
        if not line.strip():
            y_txt += 10
            continue
        # simple word-wrap at ~90 chars
        words = line.split()
        row = ""
        for word in words:
            if len(row) + len(word) + 1 > 90:
                p3.insert_text((50, y_txt), row.strip(), fontsize=11, fontname="helv")
                y_txt += 16
                row = word + " "
            else:
                row += word + " "
        if row.strip():
            p3.insert_text((50, y_txt), row.strip(), fontsize=11, fontname="helv")
            y_txt += 16

    p3.insert_text((50, y_txt + 20), "10. Document Control", fontsize=14, fontname="helv")
    p3.insert_text((50, y_txt + 44), "This document is maintained by Claims Operations.", fontsize=11, fontname="helv")
    p3.insert_text((50, y_txt + 60), "Next scheduled review: 2027-01-01.", fontsize=11, fontname="helv")
    p3.insert_text((50, y_txt + 76), "All previous versions are archived in the document library.", fontsize=11, fontname="helv")
    p3.insert_text((50, y_txt + 92), "-- END OF DOCUMENT --", fontsize=10, fontname="helv")

    # save with compression
    doc.save(str(output), garbage=4, deflate=True)
    doc.close()

    size_kb = output.stat().st_size / 1024
    print(f"Generated: {output}")
    print(f"  Pages : 3")
    print(f"  Size  : {size_kb:.1f} KB")
    print(f"  Ready for: python tests/integration_test.py")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate test PDF fixture")
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    build_pdf(args.output)


if __name__ == "__main__":
    main()
