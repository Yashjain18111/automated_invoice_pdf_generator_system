from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd


def build_customer_summary(processed_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        processed_df.groupby(["customer_id", "customer_name", "customer_email", "currency"], dropna=False)
        .agg(
            transaction_count=("transaction_id", "count"),
            subtotal=("line_subtotal", "sum"),
            tax_total=("tax_amount", "sum"),
            total_due=("line_total", "sum"),
            latest_due_date=("invoice_due_date", "max"),
        )
        .reset_index()
    )

    for amount_column in ["subtotal", "tax_total", "total_due"]:
        summary[amount_column] = summary[amount_column].round(2)

    summary["latest_due_date"] = summary["latest_due_date"].dt.date.astype(str)
    summary = summary.sort_values(by="total_due", ascending=False).reset_index(drop=True)
    return summary


def export_reports(
    processed_df: pd.DataFrame,
    invoice_manifest_df: pd.DataFrame,
    reports_dir: Path,
    input_stem: str,
) -> Tuple[pd.DataFrame, Dict[str, Path], Dict[str, float]]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    customer_summary_df = build_customer_summary(processed_df)
    customer_summary_path = reports_dir / f"{input_stem}_customer_summary_{timestamp}.csv"
    invoice_manifest_path = reports_dir / f"{input_stem}_invoice_manifest_{timestamp}.csv"
    metrics_path = reports_dir / f"{input_stem}_metrics_{timestamp}.csv"

    customer_summary_df.to_csv(customer_summary_path, index=False)
    invoice_manifest_df.to_csv(invoice_manifest_path, index=False)

    metrics = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_records": float(len(processed_df)),
        "total_customers": float(customer_summary_df["customer_id"].nunique()),
        "total_invoices": float(len(invoice_manifest_df)),
        "gross_amount": round(float(processed_df["line_subtotal"].sum()), 2),
        "total_tax": round(float(processed_df["tax_amount"].sum()), 2),
        "total_amount_due": round(float(processed_df["line_total"].sum()), 2),
    }
    pd.DataFrame([metrics]).to_csv(metrics_path, index=False)

    output_paths = {
        "customer_summary": customer_summary_path,
        "invoice_manifest": invoice_manifest_path,
        "metrics": metrics_path,
    }
    return customer_summary_df, output_paths, metrics

