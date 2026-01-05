# Finance Master

Finance Master converts raw bank CSV exports (such as **YearEndAllPaymentMethods**) into clean,
organized Excel and PDF reports that show **how often you shop at each store** and **how much you spend there over a year**.

## Why This Project Exists
Banks export transactions as long CSV files that are hard to analyze.
This project answers questions like:
- How many times did I shop at a specific store this year?
- Which merchants appear most frequently?
- Where did most of my money go?

All processing is local. No data leaves your machine.

## Features
- Cleans raw CSV exports (spacing, narration noise)
- Normalizes merchant descriptions
- Groups transactions by merchant family
- Counts transactions per store
- Calculates total spend per group
- Generates:
  - Excel summaries
  - Quick PDF summaries
  - Fully organized PDF reports

## Installation
```bash
pip3 install -r requirements.txt
```

## Usage
```bash
python3 finance_master.py organized_pdf
```

## Outputs
Generated files include:
- organized_report.pdf
- expenses_quick_summary.pdf
- expenses_family_summary.xlsx

## Privacy
Your financial data stays local. Nothing is uploaded.
