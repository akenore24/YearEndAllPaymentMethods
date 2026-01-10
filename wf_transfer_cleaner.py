#!/usr/bin/env python3
"""
wf_transfer_cleaner.py

Cleans Wells Fargo CSV exports by:
1) Normalizing inconsistent spacing across ALL text fields
2) Splitting "double transactions" stuck in one description cell using "ON mm/dd/yy"
3) Removing non-expense transactions (logged with reasons):
   - Internal transfer: Way2Save Savings
   - Payment: WF Active Cash Visa
   - Payment: WF Reflect Visa
4) Writing outputs:
   - clean.csv (kept)
   - transfers_report.csv (removed + reason)
   - clean_spacing.csv (optional baseline, pre-removal)

NEW:
- --summary-pdf <file.pdf>
  Generates a ready-to-print PDF summary with:
  • rows removed by category
  • total amount removed by category
  • rows left (kept) and total kept amount
  • totals and timestamp

Usage examples:
  python3 wf_transfer_cleaner.py export.csv
  python3 wf_transfer_cleaner.py export.csv --dry-run
  python3 wf_transfer_cleaner.py export.csv --no-name-filter
  python3 wf_transfer_cleaner.py export.csv --summary-pdf wf_transfer_summary.pdf
  python3 wf_transfer_cleaner.py export.csv --no-out-spacing --summary-pdf summary.pdf
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# PDF
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


# -----------------------------
# Normalization
# -----------------------------
_SPACE_REGEX = re.compile(r"\s+")

def normalize_spacing(s: str) -> str:
    if not s:
        return ""
    return _SPACE_REGEX.sub(" ", s).strip()


def normalize_row_spacing(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: normalize_spacing(v) if isinstance(v, str) else v for k, v in row.items()}


# -----------------------------
# Column detection: Description + Amount
# -----------------------------
DESCRIPTION_CANDIDATES = [
    "Description", "Transaction Description", "Details", "Memo", "Payee", "Name",
    "DESCRIPTION", "TRANSACTION DESCRIPTION", "DETAILS", "MEMO", "PAYEE", "NAME",
]

AMOUNT_CANDIDATES = [
    "Amount", "AMOUNT",
    "Transaction Amount", "TRANSACTION AMOUNT",
    "Debit", "DEBIT",
    "Credit", "CREDIT",
]

def find_description_field(headers: List[str]) -> str:
    lower_to_real = {h.lower(): h for h in headers}
    for cand in DESCRIPTION_CANDIDATES:
        key = cand.lower()
        if key in lower_to_real:
            return lower_to_real[key]
    for h in headers:
        hl = h.lower()
        if any(x in hl for x in ("desc", "memo", "detail", "payee")):
            return h
    raise ValueError(f"No description-like column found. Headers: {headers}")


def find_amount_field(headers: List[str]) -> Optional[str]:
    lower_to_real = {h.lower(): h for h in headers}
    for cand in AMOUNT_CANDIDATES:
        key = cand.lower()
        if key in lower_to_real:
            return lower_to_real[key]

    # fallback heuristic
    for h in headers:
        hl = h.lower()
        if "amount" in hl:
            return h
        if hl in ("amt", "transactionamt", "transaction_amt"):
            return h
    return None


_AMOUNT_CLEAN_REGEX = re.compile(r"[^0-9.\-()]+")

def parse_amount(value: Any) -> float:
    """
    Parses amounts like:
      "$1,234.56"
      "-12.34"
      "(12.34)"  -> -12.34
      "12.34"
    If parse fails, returns 0.0 (safe).
    """
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0

    # Remove currency symbols/commas/letters
    s = _AMOUNT_CLEAN_REGEX.sub("", s)

    # Parentheses indicate negative in many exports
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]

    try:
        n = float(s)
    except ValueError:
        return 0.0

    return -abs(n) if neg else n


# -----------------------------
# Split stuck-together transactions
# -----------------------------
_ON_DATE_REGEX = re.compile(r"\bON\s+\d{2}/\d{2}/\d{2}\b", re.IGNORECASE)

def split_multi_transactions_in_desc(desc: str) -> List[str]:
    """
    Splits:
      "... ON 12/11/25 ONLINE TRANSFER ... ON 10/31/24"
    into:
      ["... ON 12/11/25", "ONLINE TRANSFER ... ON 10/31/24"]
    """
    desc = normalize_spacing(desc)
    if not desc:
        return [""]

    matches = list(_ON_DATE_REGEX.finditer(desc))
    if len(matches) <= 1:
        return [desc]

    parts: List[str] = []
    start = 0
    for m in matches:
        end = m.end()
        chunk = desc[start:end].strip()
        if chunk:
            parts.append(chunk)
        start = end

    tail = desc[start:].strip()
    if tail:
        parts.append(tail)

    return parts


# -----------------------------
# Removal rules
# -----------------------------
KENORE_REGEX = re.compile(r"\bKENORE\b", re.IGNORECASE)

@dataclass(frozen=True)
class RemovalRule:
    key: str
    label: str
    pattern: re.Pattern
    requires_name: bool = False


RULE_WAY2SAVE = RemovalRule(
    key="way2save_internal_transfer",
    label="Internal transfer: Way2Save Savings",
    pattern=re.compile(r"\bONLINE\s+TRANSFER\b.*\bWAY2SAVE\b.*\bSAVINGS\b", re.IGNORECASE),
    requires_name=True,
)

RULE_WF_ACTIVE_CASH = RemovalRule(
    key="wf_active_cash_payment",
    label="Payment: WF Active Cash Visa",
    pattern=re.compile(
        r"\bONLINE\s+TRANSFER\b.*\bTO\b.*\bWELLS\s+FARGO\b.*\bACTIVE\s+CASH\b.*\bVISA\b.*\bCARD\b",
        re.IGNORECASE,
    ),
)

RULE_WF_REFLECT = RemovalRule(
    key="wf_reflect_payment",
    label="Payment: WF Reflect Visa",
    pattern=re.compile(
        r"\bONLINE\s+TRANSFER\b.*\bTO\b.*\bWELLS\s+FARGO\b.*\bREFLECT\b.*\bVISA\b.*\bCARD\b",
        re.IGNORECASE,
    ),
)

RULES: List[RemovalRule] = [RULE_WAY2SAVE, RULE_WF_ACTIVE_CASH, RULE_WF_REFLECT]


def classify(desc: str, require_name_filter: bool) -> Optional[RemovalRule]:
    if not desc:
        return None

    for rule in RULES:
        if not rule.pattern.search(desc):
            continue

        if rule.requires_name and require_name_filter:
            if not KENORE_REGEX.search(desc):
                continue

        return rule

    return None


# -----------------------------
# Stats container
# -----------------------------
@dataclass
class Stats:
    kept_rows: int = 0
    kept_amount: float = 0.0
    removed_rows_by_key: Dict[str, int] = None  # type: ignore
    removed_amount_by_key: Dict[str, float] = None  # type: ignore

    def __post_init__(self):
        if self.removed_rows_by_key is None:
            self.removed_rows_by_key = {r.key: 0 for r in RULES}
        if self.removed_amount_by_key is None:
            self.removed_amount_by_key = {r.key: 0.0 for r in RULES}

    @property
    def total_removed_rows(self) -> int:
        return sum(self.removed_rows_by_key.values())

    @property
    def total_removed_amount(self) -> float:
        return sum(self.removed_amount_by_key.values())


# -----------------------------
# Core processing
# -----------------------------
def process_csv(
    input_csv: Path,
    out_clean: Path,
    out_report: Path,
    out_spacing: Optional[Path],
    dry_run: bool,
    no_name_filter: bool,
) -> Tuple[List[str], str, Stats, List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Returns:
      headers, desc_field, stats, spacing_rows_all, kept_rows, removed_rows(with reason)
    """
    stats = Stats()

    with input_csv.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if not headers:
            raise ValueError("CSV has no headers (first row must contain column names).")

        desc_field = find_description_field(headers)
        amount_field = find_amount_field(headers)

        spacing_rows_all: List[Dict[str, Any]] = []
        kept_rows: List[Dict[str, Any]] = []
        removed_rows: List[Dict[str, Any]] = []

        for row in reader:
            row = normalize_row_spacing(row)
            spacing_rows_all.append(row)

            base_amount = parse_amount(row.get(amount_field)) if amount_field else 0.0

            original_desc = row.get(desc_field, "") or ""
            chunks = split_multi_transactions_in_desc(original_desc)

            if len(chunks) == 1:
                desc = chunks[0]
                row[desc_field] = desc

                rule = classify(desc, require_name_filter=(not no_name_filter))
                if rule:
                    stats.removed_rows_by_key[rule.key] += 1
                    stats.removed_amount_by_key[rule.key] += base_amount
                    removed_rows.append({**row, "RemovalReason": rule.label})
                else:
                    stats.kept_rows += 1
                    stats.kept_amount += base_amount
                    kept_rows.append(row)
                continue

            # Multiple chunks: duplicate row per chunk (virtual rows).
            # Amount is duplicated across chunks (bank export usually indicates two separate items merged;
            # if that ever becomes inaccurate, we can split amounts, but that's not available in your text.)
            for chunk in chunks:
                virtual_row = dict(row)
                virtual_row[desc_field] = chunk

                rule = classify(chunk, require_name_filter=(not no_name_filter))
                if rule:
                    stats.removed_rows_by_key[rule.key] += 1
                    stats.removed_amount_by_key[rule.key] += base_amount
                    removed_rows.append({**virtual_row, "RemovalReason": rule.label})
                else:
                    stats.kept_rows += 1
                    stats.kept_amount += base_amount
                    kept_rows.append(virtual_row)

    if dry_run:
        return headers, desc_field, stats, spacing_rows_all, kept_rows, removed_rows

    # Write spacing baseline first (optional)
    if out_spacing is not None:
        with out_spacing.open("w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=headers)
            writer.writeheader()
            writer.writerows(spacing_rows_all)

    # Write clean.csv (kept)
    with out_clean.open("w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=headers)
        writer.writeheader()
        writer.writerows(kept_rows)

    # Write transfers_report.csv (removed + reason)
    report_headers = headers[:] + (["RemovalReason"] if "RemovalReason" not in headers else [])
    with out_report.open("w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=report_headers)
        writer.writeheader()
        writer.writerows(removed_rows)

    return headers, desc_field, stats, spacing_rows_all, kept_rows, removed_rows


# -----------------------------
# PDF Summary
# -----------------------------
def money(n: float) -> str:
    return f"${n:,.2f}"


def write_summary_pdf(pdf_path: Path, input_csv: Path, stats: Stats) -> None:
    """
    Ready-to-print PDF: simple, clean, one page summary.
    """
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter

    left = 0.75 * inch
    top = height - 0.75 * inch
    line = 0.28 * inch

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, top, "WF Transfer Cleaner — Summary Report")

    c.setFont("Helvetica", 10)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.drawString(left, top - 0.35 * inch, f"Generated: {ts} (local)")
    c.drawString(left, top - 0.55 * inch, f"Input file: {input_csv.name}")

    y = top - 1.05 * inch

    # Table header
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Category")
    c.drawRightString(width - left, y, "Rows / Total Amount")
    y -= 0.2 * inch

    c.setFont("Helvetica", 11)

    # Rows per category (removed)
    for rule in RULES:
        rows = stats.removed_rows_by_key.get(rule.key, 0)
        amt = stats.removed_amount_by_key.get(rule.key, 0.0)
        c.drawString(left, y, rule.label)
        c.drawRightString(width - left, y, f"{rows}   /   {money(amt)}")
        y -= line

    # Divider
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "TOTAL REMOVED")
    c.drawRightString(width - left, y, f"{stats.total_removed_rows}   /   {money(stats.total_removed_amount)}")
    y -= 0.35 * inch

    # Kept
    c.drawString(left, y, "ROWS LEFT (KEPT)")
    c.drawRightString(width - left, y, f"{stats.kept_rows}   /   {money(stats.kept_amount)}")
    y -= 0.45 * inch

    # Footer note
    c.setFont("Helvetica", 9)
    c.drawString(left, y, "Notes:")
    y -= 0.18 * inch
    c.drawString(left, y, "- Amount totals come from the CSV amount column (auto-detected).")
    y -= 0.18 * inch
    c.drawString(left, y, "- Removed rows are logged in transfers_report.csv with a RemovalReason for auditing.")

    c.showPage()
    c.save()


# -----------------------------
# CLI
# -----------------------------
def print_snapshot(stats: Stats) -> None:
    print("\n📌 Removal snapshot")
    print("-" * 52)
    for r in RULES:
        rc = stats.removed_rows_by_key.get(r.key, 0)
        amt = stats.removed_amount_by_key.get(r.key, 0.0)
        print(f"{r.label:32s} {rc:6d}   {money(amt):>14s}")
    print("-" * 52)
    print(f"{'TOTAL REMOVED':32s} {stats.total_removed_rows:6d}   {money(stats.total_removed_amount):>14s}")
    print(f"{'ROWS LEFT (KEPT)':32s} {stats.kept_rows:6d}   {money(stats.kept_amount):>14s}\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="wf_transfer_cleaner.py",
        description="Normalize spacing, split merged descriptions, remove internal transfers + WF Visa payments.",
        epilog=(
            "Examples:\n"
            "  wf_transfer_cleaner.py export.csv --dry-run\n"
            "  wf_transfer_cleaner.py export.csv --summary-pdf summary.pdf\n"
            "  wf_transfer_cleaner.py export.csv --no-out-spacing --no-name-filter\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    p.add_argument("input_csv", help="Input CSV export file path")
    p.add_argument("--dry-run", action="store_true", help="Analyze only; write no output files")
    p.add_argument("--no-name-filter", action="store_true", help="Do not require 'KENORE' for Way2Save transfer matching")
    p.add_argument("--out-clean", default="clean.csv", help="Final cleaned output CSV filename (default: clean.csv)")
    p.add_argument("--out-report", default="transfers_report.csv", help="Removed rows report filename (default: transfers_report.csv)")
    p.add_argument("--out-spacing", default="clean_spacing.csv", help="Spacing baseline filename (default: clean_spacing.csv)")
    p.add_argument("--no-out-spacing", action="store_true", help="Disable writing the spacing baseline file")

    p.add_argument(
        "--summary-pdf",
        default="",
        help="Create a ready-to-print summary PDF at the given path/filename",
    )

    return p.parse_args()


def main() -> int:
    args = parse_args()

    input_csv = Path(args.input_csv).expanduser().resolve()
    if not input_csv.exists():
        print(f"ERROR: File not found: {input_csv}")
        return 1

    out_clean = input_csv.with_name(args.out_clean)
    out_report = input_csv.with_name(args.out_report)
    out_spacing = None if args.no_out_spacing else input_csv.with_name(args.out_spacing)

    headers, desc_field, stats, spacing_rows_all, kept_rows, removed_rows = process_csv(
        input_csv=input_csv,
        out_clean=out_clean,
        out_report=out_report,
        out_spacing=out_spacing,
        dry_run=args.dry_run,
        no_name_filter=args.no_name_filter,
    )

    print("✅ Done")
    print(f"Input: {input_csv}")
    print_snapshot(stats)

    # PDF can be generated on dry-run too (it’s just a report)
    if args.summary_pdf:
        pdf_path = Path(args.summary_pdf).expanduser()
        if not pdf_path.is_absolute():
            # default to input file folder if relative
            pdf_path = input_csv.with_name(pdf_path.name)
        write_summary_pdf(pdf_path=pdf_path, input_csv=input_csv, stats=stats)
        print(f"🧾 Summary PDF created: {pdf_path}")

    if args.dry_run:
        print("🧪 Dry run — no CSV files written")
    else:
        if out_spacing is not None:
            print(f"📄 Spacing baseline: {out_spacing}")
        print(f"📄 Final clean:      {out_clean}")
        print(f"📊 Removed report:   {out_report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
