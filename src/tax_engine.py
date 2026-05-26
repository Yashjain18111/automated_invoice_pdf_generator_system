from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class TaxSettings:
    default_tax_rate: float = 0.18
    default_due_in_days: int = 30


def calculate_financials(df: pd.DataFrame, settings: Optional[TaxSettings] = None) -> pd.DataFrame:
    if settings is None:
        settings = TaxSettings()

    working = df.copy()

    working["quantity"] = pd.to_numeric(working["quantity"], errors="coerce").fillna(0).clip(lower=0)
    working["unit_price"] = pd.to_numeric(working["unit_price"], errors="coerce").fillna(0).clip(lower=0)
    working["tax_rate"] = pd.to_numeric(working["tax_rate"], errors="coerce").fillna(settings.default_tax_rate).clip(lower=0)
    working["due_in_days"] = (
        pd.to_numeric(working["due_in_days"], errors="coerce").fillna(settings.default_due_in_days).astype(int)
    )

    working["line_subtotal"] = (working["quantity"] * working["unit_price"]).round(2)
    working["tax_amount"] = (working["line_subtotal"] * working["tax_rate"]).round(2)
    working["line_total"] = (working["line_subtotal"] + working["tax_amount"]).round(2)
    working["invoice_due_date"] = working["transaction_date"] + pd.to_timedelta(working["due_in_days"], unit="D")

    return working

