from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


def generate_dashboard(
    customer_summary_df: pd.DataFrame,
    metrics: Dict[str, float],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table_html = customer_summary_df.to_html(index=False, classes="summary-table")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Invoice Automation Dashboard</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 24px;
      color: #1f2937;
      background: #f9fafb;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 20px;
    }}
    .card {{
      background: white;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 14px;
      box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }}
    .label {{
      color: #6b7280;
      font-size: 13px;
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.4px;
    }}
    .value {{
      font-size: 21px;
      font-weight: bold;
    }}
    .summary-table {{
      width: 100%;
      border-collapse: collapse;
      background: white;
      border: 1px solid #e5e7eb;
    }}
    .summary-table th, .summary-table td {{
      border: 1px solid #e5e7eb;
      padding: 10px;
      text-align: left;
      font-size: 13px;
    }}
    .summary-table th {{
      background: #f3f4f6;
    }}
  </style>
</head>
<body>
  <h1>Invoice Automation Dashboard</h1>
  <div class="grid">
    <div class="card"><div class="label">Records</div><div class="value">{int(metrics.get("total_records", 0))}</div></div>
    <div class="card"><div class="label">Customers</div><div class="value">{int(metrics.get("total_customers", 0))}</div></div>
    <div class="card"><div class="label">Invoices</div><div class="value">{int(metrics.get("total_invoices", 0))}</div></div>
    <div class="card"><div class="label">Gross Amount</div><div class="value">{metrics.get("gross_amount", 0):,.2f}</div></div>
    <div class="card"><div class="label">Tax</div><div class="value">{metrics.get("total_tax", 0):,.2f}</div></div>
    <div class="card"><div class="label">Amount Due</div><div class="value">{metrics.get("total_amount_due", 0):,.2f}</div></div>
  </div>
  <h2>Customer Summary</h2>
  {table_html}
</body>
</html>
"""

    output_path.write_text(html, encoding="utf-8")
    return output_path

