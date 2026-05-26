from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import pandas as pd

REQUIRED_COLUMNS = [
    "transaction_id",
    "transaction_date",
    "customer_id",
    "customer_name",
    "customer_email",
    "item_description",
    "quantity",
    "unit_price",
]


@dataclass
class ValidationResult:
    dataframe: pd.DataFrame
    errors: List[str]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def load_transactions(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_path, engine="openpyxl")
    raise ValueError(f"Unsupported file format: {suffix}")


def validate_transactions(df: pd.DataFrame) -> ValidationResult:
    errors: List[str] = []
    working = df.copy()

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in working.columns]
    if missing_columns:
        errors.append(f"Missing required columns: {', '.join(missing_columns)}")
        return ValidationResult(dataframe=working, errors=errors)

    for column in ["transaction_id", "customer_id", "customer_name", "customer_email", "item_description"]:
        working[column] = working[column].apply(lambda value: str(value).strip() if pd.notna(value) else value)
        blank_mask = working[column].isna() | (working[column] == "")
        if blank_mask.any():
            row_positions = [str(index + 2) for index in working[blank_mask].index.tolist()]
            errors.append(f"Column '{column}' has blank values at rows: {', '.join(row_positions)}")

    for numeric_column in ["quantity", "unit_price"]:
        working[numeric_column] = pd.to_numeric(working[numeric_column], errors="coerce")
        invalid_numeric = working[numeric_column].isna()
        if invalid_numeric.any():
            row_positions = [str(index + 2) for index in working[invalid_numeric].index.tolist()]
            errors.append(f"Column '{numeric_column}' has invalid numeric values at rows: {', '.join(row_positions)}")
        if (working[numeric_column] < 0).any():
            row_positions = [str(index + 2) for index in working[working[numeric_column] < 0].index.tolist()]
            errors.append(f"Column '{numeric_column}' has negative values at rows: {', '.join(row_positions)}")

    working["transaction_date"] = pd.to_datetime(working["transaction_date"], errors="coerce")
    invalid_dates = working["transaction_date"].isna()
    if invalid_dates.any():
        row_positions = [str(index + 2) for index in working[invalid_dates].index.tolist()]
        errors.append(f"Invalid transaction_date values at rows: {', '.join(row_positions)}")

    email_mask = ~working["customer_email"].astype(str).str.contains("@", na=False)
    if email_mask.any():
        row_positions = [str(index + 2) for index in working[email_mask].index.tolist()]
        errors.append(f"Invalid customer_email format at rows: {', '.join(row_positions)}")

    if "tax_rate" not in working.columns:
        working["tax_rate"] = 0.18
    else:
        working["tax_rate"] = pd.to_numeric(working["tax_rate"], errors="coerce").fillna(0.18)
        if (working["tax_rate"] < 0).any():
            row_positions = [str(index + 2) for index in working[working["tax_rate"] < 0].index.tolist()]
            errors.append(f"Negative tax_rate values at rows: {', '.join(row_positions)}")

    if "due_in_days" not in working.columns:
        working["due_in_days"] = 30
    else:
        working["due_in_days"] = pd.to_numeric(working["due_in_days"], errors="coerce").fillna(30).astype(int)
        if (working["due_in_days"] < 0).any():
            row_positions = [str(index + 2) for index in working[working["due_in_days"] < 0].index.tolist()]
            errors.append(f"Negative due_in_days values at rows: {', '.join(row_positions)}")

    if "currency" not in working.columns:
        working["currency"] = "USD"
    else:
        working["currency"] = working["currency"].fillna("USD").astype(str).str.upper()

    if "customer_address" not in working.columns:
        working["customer_address"] = ""
    else:
        working["customer_address"] = working["customer_address"].fillna("").astype(str)

    return ValidationResult(dataframe=working, errors=errors)

