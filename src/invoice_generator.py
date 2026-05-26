from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


@dataclass
class CompanyProfile:
    name: str = "Acme Finance Pvt Ltd"
    address: str = "123 Business Street, Mumbai"
    email: str = "billing@acmefinance.com"
    phone: str = "+91-00000-00000"


def _format_currency(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _build_invoice_pdf(
    invoice_number: str,
    customer_name: str,
    customer_email: str,
    customer_address: str,
    customer_rows: pd.DataFrame,
    output_path: Path,
    company_profile: CompanyProfile,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(str(output_path), pagesize=A4, title=f"Invoice {invoice_number}")
    styles = getSampleStyleSheet()
    story: List = []

    issue_date = datetime.now().date().isoformat()
    due_date = customer_rows["invoice_due_date"].max().date().isoformat()
    currency = customer_rows["currency"].iloc[0]

    story.append(Paragraph(company_profile.name, styles["Title"]))
    story.append(Paragraph(company_profile.address, styles["Normal"]))
    story.append(Paragraph(f"Email: {company_profile.email} | Phone: {company_profile.phone}", styles["Normal"]))
    story.append(Spacer(1, 16))

    story.append(Paragraph(f"<b>Invoice Number:</b> {invoice_number}", styles["Normal"]))
    story.append(Paragraph(f"<b>Issue Date:</b> {issue_date}", styles["Normal"]))
    story.append(Paragraph(f"<b>Due Date:</b> {due_date}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"<b>Bill To:</b> {customer_name}", styles["Normal"]))
    story.append(Paragraph(customer_email, styles["Normal"]))
    story.append(Paragraph(customer_address if customer_address else "-", styles["Normal"]))
    story.append(Spacer(1, 12))

    table_rows = [["Item", "Qty", "Unit Price", "Tax", "Line Total"]]
    for _, row in customer_rows.iterrows():
        table_rows.append(
            [
                str(row["item_description"]),
                f"{float(row['quantity']):,.2f}",
                _format_currency(float(row["unit_price"]), currency),
                _format_currency(float(row["tax_amount"]), currency),
                _format_currency(float(row["line_total"]), currency),
            ]
        )

    invoice_table = Table(table_rows, hAlign="LEFT")
    invoice_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7c7c7")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ]
        )
    )
    story.append(invoice_table)
    story.append(Spacer(1, 16))

    subtotal = float(customer_rows["line_subtotal"].sum())
    tax_total = float(customer_rows["tax_amount"].sum())
    grand_total = float(customer_rows["line_total"].sum())

    story.append(Paragraph(f"Subtotal: {_format_currency(subtotal, currency)}", styles["Normal"]))
    story.append(Paragraph(f"Tax: {_format_currency(tax_total, currency)}", styles["Normal"]))
    story.append(Paragraph(f"<b>Grand Total: {_format_currency(grand_total, currency)}</b>", styles["Heading3"]))

    doc.build(story)


def generate_invoice_manifest(
    transactions_df: pd.DataFrame,
    output_dir: Path,
    company_profile: CompanyProfile | None = None,
) -> pd.DataFrame:
    if company_profile is None:
        company_profile = CompanyProfile()

    output_dir.mkdir(parents=True, exist_ok=True)
    grouped = transactions_df.groupby(["customer_id", "customer_name", "customer_email"], dropna=False)

    run_stamp = datetime.now().strftime("%Y%m%d")
    manifest_rows = []

    for index, ((customer_id, customer_name, customer_email), customer_rows) in enumerate(grouped, start=1):
        invoice_number = f"INV-{run_stamp}-{index:04d}"
        pdf_path = output_dir / f"{invoice_number}.pdf"
        customer_address = str(customer_rows["customer_address"].iloc[0]) if "customer_address" in customer_rows else ""

        _build_invoice_pdf(
            invoice_number=invoice_number,
            customer_name=str(customer_name),
            customer_email=str(customer_email),
            customer_address=customer_address,
            customer_rows=customer_rows,
            output_path=pdf_path,
            company_profile=company_profile,
        )

        due_date = customer_rows["invoice_due_date"].max().date().isoformat()
        currency = str(customer_rows["currency"].iloc[0])
        manifest_rows.append(
            {
                "invoice_number": invoice_number,
                "customer_id": customer_id,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "currency": currency,
                "subtotal": round(float(customer_rows["line_subtotal"].sum()), 2),
                "tax_total": round(float(customer_rows["tax_amount"].sum()), 2),
                "total_due": round(float(customer_rows["line_total"].sum()), 2),
                "due_date": due_date,
                "invoice_path": str(pdf_path),
            }
        )

    return pd.DataFrame(manifest_rows)

