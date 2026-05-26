from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import smtplib
from jinja2 import Template


@dataclass
class SMTPConfig:
    host: str
    port: int = 587
    username: Optional[str] = None
    password: Optional[str] = None
    sender_email: Optional[str] = None
    use_tls: bool = True


def build_email_queue(
    invoice_manifest_df: pd.DataFrame,
    template_path: Path,
    reports_dir: Path,
) -> Tuple[pd.DataFrame, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    template = Template(template_path.read_text(encoding="utf-8"))
    queue_rows = []

    for row in invoice_manifest_df.to_dict(orient="records"):
        body = template.render(
            customer_name=row["customer_name"],
            invoice_number=row["invoice_number"],
            currency=row["currency"],
            total_due=f"{row['total_due']:.2f}",
            due_date=row["due_date"],
        )
        queue_rows.append(
            {
                "invoice_number": row["invoice_number"],
                "recipient_email": row["customer_email"],
                "subject": f"Invoice {row['invoice_number']} | Due {row['due_date']}",
                "body": body,
                "attachment": row["invoice_path"],
                "status": "pending",
                "sent_at": "",
            }
        )

    queue_df = pd.DataFrame(queue_rows)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    queue_path = reports_dir / f"email_queue_{timestamp}.csv"
    queue_df.to_csv(queue_path, index=False)
    return queue_df, queue_path


def send_emails(
    email_queue_df: pd.DataFrame,
    smtp_config: SMTPConfig,
    dry_run: bool = True,
) -> pd.DataFrame:
    results_df = email_queue_df.copy()

    if dry_run:
        results_df["status"] = "ready_to_send"
        results_df["sent_at"] = datetime.now().isoformat(timespec="seconds")
        return results_df

    sender = smtp_config.sender_email or smtp_config.username
    if not sender:
        raise ValueError("sender_email or smtp username must be set for live email sending.")

    with smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30) as smtp:
        if smtp_config.use_tls:
            smtp.starttls()
        if smtp_config.username and smtp_config.password:
            smtp.login(smtp_config.username, smtp_config.password)

        for row_index, row in results_df.iterrows():
            status = "sent"
            sent_at = datetime.now().isoformat(timespec="seconds")
            try:
                msg = EmailMessage()
                msg["From"] = sender
                msg["To"] = str(row["recipient_email"])
                msg["Subject"] = str(row["subject"])
                msg.set_content(str(row["body"]))

                attachment_path = Path(str(row["attachment"]))
                if attachment_path.exists():
                    with attachment_path.open("rb") as file_handle:
                        msg.add_attachment(
                            file_handle.read(),
                            maintype="application",
                            subtype="pdf",
                            filename=attachment_path.name,
                        )

                smtp.send_message(msg)
            except Exception as exc:  # noqa: BLE001
                status = f"failed: {exc}"
                sent_at = datetime.now().isoformat(timespec="seconds")

            results_df.at[row_index, "status"] = status
            results_df.at[row_index, "sent_at"] = sent_at

    return results_df

