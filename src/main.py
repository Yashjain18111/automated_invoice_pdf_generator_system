from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from shutil import move
from typing import Dict, List, Optional

import pandas as pd

from dashboard import generate_dashboard
from email_service import SMTPConfig, build_email_queue, send_emails
from invoice_generator import CompanyProfile, generate_invoice_manifest
from summary_generator import export_reports
from tax_engine import TaxSettings, calculate_financials
from validator import ValidationResult, load_transactions, validate_transactions

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_INPUT_DIR = ROOT_DIR / "data" / "input"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DATA_FAILED_DIR = ROOT_DIR / "data" / "failed"
INVOICES_DIR = ROOT_DIR / "invoices"
TEMPLATES_DIR = ROOT_DIR / "templates"
REPORTS_DIR = ROOT_DIR / "reports"
LOGS_DIR = ROOT_DIR / "logs"


@dataclass
class PipelineConfig:
    tax_settings: TaxSettings
    company_profile: CompanyProfile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated Invoice & PDF Generator System")
    parser.add_argument("--input-file", type=str, help="Path to a specific CSV/XLSX input file.")
    parser.add_argument("--default-tax-rate", type=float, default=0.18, help="Default tax rate when missing.")
    parser.add_argument("--default-due-days", type=int, default=30, help="Default due days when missing.")
    parser.add_argument("--send-emails", action="store_true", help="Generate and send invoice emails.")
    parser.add_argument("--live-send", action="store_true", help="Actually send emails via SMTP.")
    parser.add_argument("--smtp-host", type=str, default="", help="SMTP host for live send.")
    parser.add_argument("--smtp-port", type=int, default=587, help="SMTP port for live send.")
    parser.add_argument("--smtp-username", type=str, default="", help="SMTP username.")
    parser.add_argument("--smtp-password", type=str, default="", help="SMTP password.")
    parser.add_argument("--sender-email", type=str, default="billing@example.com", help="Sender email address.")
    return parser.parse_args()


def setup_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )


def ensure_directories() -> None:
    for path in [
        DATA_INPUT_DIR,
        DATA_PROCESSED_DIR,
        DATA_FAILED_DIR,
        INVOICES_DIR,
        TEMPLATES_DIR,
        REPORTS_DIR,
        LOGS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def resolve_input_file(raw_path: str) -> Path:
    candidate = Path(raw_path)
    return candidate if candidate.is_absolute() else (ROOT_DIR / candidate)


def discover_input_files(specific_file: Optional[Path] = None) -> List[Path]:
    if specific_file is not None:
        return [specific_file]

    files: List[Path] = []
    for extension in ("*.csv", "*.xlsx", "*.xls"):
        files.extend(DATA_INPUT_DIR.glob(extension))
    return sorted(files)


def move_to_archive(file_path: Path, archive_dir: Path) -> None:
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = archive_dir / file_path.name
    if destination.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = archive_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"
    move(str(file_path), str(destination))


def write_validation_errors(input_file: Path, validation_result: ValidationResult) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = REPORTS_DIR / f"{input_file.stem}_validation_errors_{timestamp}.txt"
    output_path.write_text("\n".join(validation_result.errors), encoding="utf-8")
    return output_path


def build_smtp_config(args: argparse.Namespace) -> SMTPConfig:
    return SMTPConfig(
        host=args.smtp_host if args.smtp_host else "localhost",
        port=args.smtp_port,
        username=args.smtp_username or None,
        password=args.smtp_password or None,
        sender_email=args.sender_email,
        use_tls=True,
    )


def process_file(
    input_file: Path,
    config: PipelineConfig,
    send_email_jobs: bool,
    live_send: bool,
    smtp_config: Optional[SMTPConfig],
) -> Dict[str, str]:
    logging.info("Processing file: %s", input_file)
    processed_at = datetime.now().isoformat(timespec="seconds")
    summary: Dict[str, str] = {
        "processed_at": processed_at,
        "input_file": str(input_file),
        "status": "unknown",
        "records_received": "0",
        "records_processed": "0",
        "records_failed": "0",
        "invoices_generated": "0",
        "email_status": "not_requested",
        "message": "",
    }

    try:
        raw_df = load_transactions(input_file)
        summary["records_received"] = str(len(raw_df))

        validation = validate_transactions(raw_df)
        if not validation.is_valid:
            error_file = write_validation_errors(input_file, validation)
            move_to_archive(input_file, DATA_FAILED_DIR)
            summary["status"] = "failed_validation"
            summary["records_failed"] = str(len(raw_df))
            summary["message"] = f"Validation failed. See {error_file}"
            logging.warning("Validation failed for %s. Errors written to %s", input_file, error_file)
            return summary

        processed_df = calculate_financials(validation.dataframe, settings=config.tax_settings)
        invoice_manifest_df = generate_invoice_manifest(
            transactions_df=processed_df,
            output_dir=INVOICES_DIR,
            company_profile=config.company_profile,
        )
        customer_summary_df, report_paths, metrics = export_reports(
            processed_df=processed_df,
            invoice_manifest_df=invoice_manifest_df,
            reports_dir=REPORTS_DIR,
            input_stem=input_file.stem,
        )

        dashboard_path = REPORTS_DIR / f"{input_file.stem}_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        generate_dashboard(customer_summary_df=customer_summary_df, metrics=metrics, output_path=dashboard_path)

        email_queue_df, email_queue_path = build_email_queue(
            invoice_manifest_df=invoice_manifest_df,
            template_path=TEMPLATES_DIR / "email_template.html",
            reports_dir=REPORTS_DIR,
        )

        summary["email_status"] = "queue_created"
        if send_email_jobs:
            if live_send and smtp_config is None:
                raise ValueError("SMTP config is required for live email sending.")
            email_results_df = send_emails(
                email_queue_df=email_queue_df,
                smtp_config=smtp_config if smtp_config else build_smtp_config(argparse.Namespace()),
                dry_run=not live_send,
            )
            email_results_path = REPORTS_DIR / f"{input_file.stem}_email_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            email_results_df.to_csv(email_results_path, index=False)
            summary["email_status"] = "live_sent" if live_send else "dry_run_ready"
            report_paths["email_results"] = email_results_path

        move_to_archive(input_file, DATA_PROCESSED_DIR)

        summary["status"] = "processed"
        summary["records_processed"] = str(len(processed_df))
        summary["invoices_generated"] = str(len(invoice_manifest_df))
        summary["message"] = (
            f"Reports: {report_paths['customer_summary']}, {report_paths['invoice_manifest']}; "
            f"Dashboard: {dashboard_path}; Email queue: {email_queue_path}"
        )
        logging.info("Successfully processed %s", input_file)
        return summary

    except Exception as exc:  # noqa: BLE001
        logging.exception("Processing failed for %s", input_file)
        if input_file.exists():
            move_to_archive(input_file, DATA_FAILED_DIR)
        summary["status"] = "failed_runtime"
        summary["records_failed"] = summary["records_received"]
        summary["message"] = str(exc)
        return summary


def append_processing_history(records: List[Dict[str, str]]) -> None:
    history_path = LOGS_DIR / "processing_history.csv"
    new_history_df = pd.DataFrame(records)

    if history_path.exists():
        existing_history_df = pd.read_csv(history_path)
        combined_df = pd.concat([existing_history_df, new_history_df], ignore_index=True)
    else:
        combined_df = new_history_df

    combined_df.to_csv(history_path, index=False)


def main() -> None:
    args = parse_args()
    ensure_directories()
    setup_logging()

    if args.live_send and not args.send_emails:
        logging.warning("--live-send was provided without --send-emails. Ignoring live send.")

    if args.live_send and not args.smtp_host:
        raise SystemExit("--smtp-host is required when using --live-send.")

    config = PipelineConfig(
        tax_settings=TaxSettings(
            default_tax_rate=args.default_tax_rate,
            default_due_in_days=args.default_due_days,
        ),
        company_profile=CompanyProfile(),
    )

    smtp_config = build_smtp_config(args) if args.send_emails else None
    specific_file = resolve_input_file(args.input_file) if args.input_file else None
    input_files = discover_input_files(specific_file=specific_file)

    if not input_files:
        logging.info("No input files found in %s", DATA_INPUT_DIR)
        return

    run_records: List[Dict[str, str]] = []
    for input_file in input_files:
        result = process_file(
            input_file=input_file,
            config=config,
            send_email_jobs=args.send_emails,
            live_send=args.live_send and args.send_emails,
            smtp_config=smtp_config,
        )
        run_records.append(result)

    append_processing_history(run_records)
    logging.info("Run complete. %d file(s) processed.", len(run_records))


if __name__ == "__main__":
    main()

