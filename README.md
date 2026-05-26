# Automated Invoice & PDF Generator System
Finance-oriented automation system that ingests transaction files, validates them, calculates tax and totals, generates PDF invoices, exports reporting summaries, and prepares email-ready invoice jobs.

## Features
- CSV/XLSX transaction ingestion
- Validation workflow with failed-file handling
- Tax + due-date calculations
- Branded PDF invoice generation per customer
- Customer summary + invoice manifest exports
- HTML dashboard export
- Email queue generation and optional SMTP sending
- Processing history tracking

## Project structure
- `data/input`: incoming transaction files
- `data/processed`: successfully processed files
- `data/failed`: failed validation/processing files
- `invoices`: generated PDF invoices
- `templates`: invoice/email templates
- `reports`: summary exports, dashboard, email queue/results
- `logs`: runtime logs and processing history
- `src`: Python source modules

## Input schema
Required columns:
- `transaction_id`
- `transaction_date`
- `customer_id`
- `customer_name`
- `customer_email`
- `item_description`
- `quantity`
- `unit_price`

Optional columns:
- `tax_rate` (decimal, e.g. `0.18`)
- `due_in_days` (integer, default `30`)
- `currency` (default `USD`)
- `customer_address`

## Setup
1. Create/activate virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Drop input files in `data/input`.

## Run
- Process all input files:
  - `python src/main.py`
- Process one specific file:
  - `python src/main.py --input-file data/input/transactions.csv`
- Enable email queue send in dry-run mode:
  - `python src/main.py --send-emails`
- Live SMTP send:
  - `python src/main.py --send-emails --live-send --smtp-host smtp.example.com --sender-email billing@example.com`

## Output artifacts
- PDFs: `invoices/*.pdf`
- Summaries: `reports/*_customer_summary_*.csv`
- Invoice manifest: `reports/*_invoice_manifest_*.csv`
- Dashboard: `reports/*_dashboard_*.html`
- Email queue/results: `reports/*_email_queue_*.csv`, `reports/*_email_results_*.csv`
- History: `logs/processing_history.csv`

