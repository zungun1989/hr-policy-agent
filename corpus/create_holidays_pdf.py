"""
Generate corpus/holidays.pdf from holiday calendar content.
Run once: python corpus/create_holidays_pdf.py
"""
import os
import sys

def create_pdf():
    try:
        from fpdf import FPDF
    except ImportError:
        print("fpdf2 not installed, skipping PDF generation")
        return

    holidays_2025 = [
        ("January 1, 2025", "New Year's Day"),
        ("January 20, 2025", "Martin Luther King Jr. Day"),
        ("February 17, 2025", "Presidents' Day"),
        ("May 26, 2025", "Memorial Day"),
        ("June 19, 2025", "Juneteenth"),
        ("July 4, 2025", "Independence Day"),
        ("September 1, 2025", "Labor Day"),
        ("November 27, 2025", "Thanksgiving Day"),
        ("November 28, 2025", "Day After Thanksgiving"),
        ("December 24, 2025", "Christmas Eve (half day)"),
        ("December 25, 2025", "Christmas Day"),
        ("December 31, 2025", "New Year's Eve (half day)"),
    ]

    holidays_2026 = [
        ("January 1, 2026", "New Year's Day"),
        ("January 19, 2026", "Martin Luther King Jr. Day"),
        ("February 16, 2026", "Presidents' Day"),
        ("May 25, 2026", "Memorial Day"),
        ("June 19, 2026", "Juneteenth"),
        ("July 4, 2026", "Independence Day (observed July 3)"),
        ("September 7, 2026", "Labor Day"),
        ("November 26, 2026", "Thanksgiving Day"),
        ("November 27, 2026", "Day After Thanksgiving"),
        ("December 24, 2026", "Christmas Eve (half day)"),
        ("December 25, 2026", "Christmas Day"),
        ("December 31, 2026", "New Year's Eve (half day)"),
    ]

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Acme Corp - Company Holiday Calendar", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Document ID: POL-011 | Effective: January 1, 2025", ln=True, align="C")
    pdf.ln(6)

    # Policy text
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "1. Overview", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6,
        "Acme Corp observes the following paid company holidays each year. All full-time and "
        "part-time employees (20+ hours/week) are entitled to these holidays at full pay. "
        "Contractors and temporary workers are not entitled to paid holidays under this calendar "
        "unless specified in their contract.\n\n"
        "When a holiday falls on a Saturday, it is observed on the preceding Friday. "
        "When a holiday falls on a Sunday, it is observed on the following Monday. "
        "Half-day holidays (Christmas Eve and New Year's Eve) end at 1:00 PM local time."
    )
    pdf.ln(4)

    # 2025 calendar
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "2. 2025 Holiday Calendar", ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(220, 230, 242)
    pdf.cell(70, 7, "Date", border=1, fill=True)
    pdf.cell(110, 7, "Holiday", border=1, fill=True, ln=True)
    pdf.set_font("Helvetica", "", 11)
    for date, name in holidays_2025:
        pdf.cell(70, 7, date, border=1)
        pdf.cell(110, 7, name, border=1, ln=True)
    pdf.ln(6)

    # 2026 calendar
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "3. 2026 Holiday Calendar", ln=True)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_fill_color(220, 230, 242)
    pdf.cell(70, 7, "Date", border=1, fill=True)
    pdf.cell(110, 7, "Holiday", border=1, fill=True, ln=True)
    pdf.set_font("Helvetica", "", 11)
    for date, name in holidays_2026:
        pdf.cell(70, 7, date, border=1)
        pdf.cell(110, 7, name, border=1, ln=True)
    pdf.ln(6)

    # Floating holidays
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "4. Floating Holidays", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6,
        "Each full-time employee receives 2 floating holidays per calendar year. Floating holidays "
        "may be used on any day with manager approval and are subject to the same advance notice "
        "rules as PTO (see PTO Policy, POL-001). Floating holidays do not carry over and are "
        "forfeited if unused by December 31."
    )
    pdf.ln(4)

    # Religious observance
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "5. Religious and Cultural Observances", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6,
        "Acme Corp respects the diverse religious and cultural backgrounds of its employees. "
        "Employees who wish to observe religious or cultural holidays not listed in this calendar "
        "may use PTO or floating holidays for that purpose. Reasonable accommodations will be made "
        "where practicable. Contact HR at hr@acmecorp.com to discuss accommodations."
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "I", 10)
    pdf.cell(0, 6, "Questions: hr@acmecorp.com | Last updated: November 2024", ln=True)

    out_path = os.path.join(os.path.dirname(__file__), "holidays.pdf")
    pdf.output(out_path)
    print(f"Created {out_path}")


if __name__ == "__main__":
    create_pdf()
