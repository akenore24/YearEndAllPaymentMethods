"""
finance_core.config
Central configuration/constants.
"""
from __future__ import annotations
from datetime import datetime

DEFAULT_INPUT_CSV = "expenses.csv"

# outputs (filenames)
DEFAULT_SPACING_OUT = "expenses_raw_spacing_fixed.csv"
DEFAULT_PDF_HIGHEST_TXNS_OUT = "highest_to_l_txns.pdf"

DEFAULT_EXCEL_DETAIL_OUT = "expenses_clean_grouped.xlsx"
DEFAULT_EXCEL_SUMMARY_OUT = "expenses_family_summary.xlsx"
DEFAULT_EXCEL_FAMILIES_OUT = "expenses_family_summary_sorted.xlsx"

DEFAULT_PDF_DETAIL_OUT = "expenses_grouped_families_detail.pdf"
DEFAULT_PDF_SUMMARY_OUT = "expenses_family_summary.pdf"
DEFAULT_PDF_FAMILIES_SORTED_OUT = "expenses_family_totals_sorted.pdf"

DEFAULT_PDF_QUICK_OUT = "expenses_quick_summary.pdf"
DEFAULT_PDF_ORGANIZED_OUT = "organized_report.pdf"

READY_TO_PRINT_XLSX = "ready_to_print.xlsx"
READY_TO_PRINT_PDF = "ready_to_print.pdf"

DEFAULT_PDF_QUICK_18MO_OUT = "expenses_quick_summary_18mo.pdf"

REMOVE_DESC_PREFIX = "ONLINE TRANSFER REF"

WF_CARD_PREFIX = "WELLS FARGO ACTIVE CASH VISA(R) CARD"
WF_CARD_ALIAS = "WFACV"

DATE_FORMATS = (
    "%m/%d/%Y",
    "%m/%d/%y",
    "%Y-%m-%d",
    "%m-%d-%Y",
    "%m-%d-%y",
)

# Your requested 18-month buckets (explicit windows)
BUCKETS_18MO = [
    ("1.0–3 months: Oct 1, 2025 – Dec 31, 2025", datetime(2025, 10, 1), datetime(2025, 12, 31)),
    ("4–6 months: Jul 1, 2025 – Sep 30, 2025", datetime(2025, 7, 1), datetime(2025, 9, 30)),
    ("7–12 months: Jan 1, 2025 – Jun 30, 2025", datetime(2025, 1, 1), datetime(2025, 6, 30)),
    ("13–18 months: Jul 1, 2024 – Dec 31, 2024", datetime(2024, 7, 1), datetime(2024, 12, 31)),
]

# priority pinned families for ready_to_print (ZELLE is unified in family view)
READY_FAMILIES_PRIORITY = [
    "COSTCO WHSE",
    "COSTCO GAS",
    "ONLINE TRANSFER",
    "SHEGER MARKET",
    "PIASSA ETHIO",
    "WALMART",
    "ZELLE",
]
