#!/usr/bin/env python3
"""
finance_master_bucket_runner.py

Runs finance_master.py commands for BOTH:
- last 12 months (derived from an 18-month CSV)
- full 18 months (original CSV)

Then renames outputs so they’re clearly labeled:
  12m_<outputfilename>
  18m_<outputfilename>

✅ Fix included: avoids duplicate command prefixes (e.g. no more:
   12m_quick_pdf_quick_pdf_expenses_quick_summary.pdf)

How it works (no changes needed in finance_master.py):
- Creates a 12-month slice CSV from your 18-month CSV
- Runs finance_master.py commands via subprocess
- Snapshots output dir before/after each command
- Renames only newly created/changed files

Usage:
  python3 finance_master_bucket_runner.py /path/to/18_months.csv
  python3 finance_master_bucket_runner.py /path/to/18_months.csv --dry-run
  python3 finance_master_bucket_runner.py /path/to/18_months.csv --finance-master /path/to/finance_master.py
  python3 finance_master_bucket_runner.py /path/to/18_months.csv --outdir output
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# Commands to run (in order)
# -----------------------------
COMMANDS = [
    "quick_pdf",
    "exec_txns_desc",
    "quick_pdf_18mo",
    "pipeline",
    "pdf_families",
    "excel_families",
    "organized_pdf",
    "ready_to_print",
    "all",
]

# Candidate date column names (adjust if yours differs)
DATE_CANDIDATES = [
    "Date", "DATE",
    "Transaction Date", "TRANSACTION DATE",
    "Posted Date", "POSTED DATE",
]


# -----------------------------
# Date parsing / slicing helpers
# -----------------------------
def parse_mmddyyyy(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def find_date_field(headers: List[str]) -> str:
    lower_to_real = {h.lower(): h for h in headers}
    for cand in DATE_CANDIDATES:
        if cand.lower() in lower_to_real:
            return lower_to_real[cand.lower()]

    for h in headers:
        if "date" in h.lower():
            return h

    raise ValueError(f"Could not find a date column. Headers: {headers}")


def month_delta_days(months: int) -> int:
    # Approx rolling months: 30.44 days per month
    return int(round(months * 30.44))


@dataclass
class SliceResult:
    sliced_csv: Path
    total_rows: int
    kept_rows: int
    date_min: Optional[datetime]
    date_max: Optional[datetime]


def write_last_n_months_csv(input_csv: Path, months: int, out_csv: Path) -> SliceResult:
    with input_csv.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if not headers:
            raise ValueError("CSV has no headers.")

        date_field = find_date_field(headers)

        rows: List[Dict[str, str]] = []
        dates: List[datetime] = []

        for row in reader:
            dt = parse_mmddyyyy(row.get(date_field, ""))
            if dt:
                dates.append(dt)
            rows.append(row)

    if not dates:
        raise ValueError("No parseable dates found in the date column.")

    max_date = max(dates)
    cutoff = max_date - timedelta(days=month_delta_days(months))

    kept: List[Dict[str, str]] = []
    kept_dates: List[datetime] = []
    for row in rows:
        dt = parse_mmddyyyy(row.get(date_field, ""))
        if dt and dt >= cutoff:
            kept.append(row)
            kept_dates.append(dt)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=headers)
        w.writeheader()
        w.writerows(kept)

    return SliceResult(
        sliced_csv=out_csv,
        total_rows=len(rows),
        kept_rows=len(kept),
        date_min=min(kept_dates) if kept_dates else None,
        date_max=max(kept_dates) if kept_dates else None,
    )


# -----------------------------
# Output snapshot / diff helpers
# -----------------------------
def snapshot_files(outdir: Path) -> Dict[str, float]:
    files: Dict[str, float] = {}
    if not outdir.exists():
        return files
    for p in outdir.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(outdir))
            files[rel] = p.stat().st_mtime
    return files


def diff_new_files(before: Dict[str, float], after: Dict[str, float]) -> List[str]:
    newish: List[str] = []
    for rel, mtime in after.items():
        if rel not in before:
            newish.append(rel)
        else:
            if mtime > before[rel] + 1e-6:
                newish.append(rel)
    return sorted(set(newish))


def safe_slug(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in s)


# -----------------------------
# finance_master runner + renamer
# -----------------------------
def run_finance_master_command(
    finance_master_py: Path,
    csv_path: Path,
    command: str,
    outdir: Path,
    bucket_label: str,
    dry_run: bool,
) -> None:
    """
    Runs finance_master.py with a few common CLI patterns:
      A) finance_master.py <command> <csv>
      B) finance_master.py <command> --csv <csv>
      C) finance_master.py <command> (if it auto-detects clean.csv or similar)

    Then renames newly created/changed outputs:
      - Always prefix with bucket label: 12m_ or 18m_
      - Avoid repeating the command if the output filename already starts with it
    """
    outdir.mkdir(parents=True, exist_ok=True)
    before = snapshot_files(outdir)

    attempts = [
        [sys.executable, str(finance_master_py), command, str(csv_path)],
        [sys.executable, str(finance_master_py), command, "--csv", str(csv_path)],
        [sys.executable, str(finance_master_py), command],
    ]

    if dry_run:
        print(f"🧪 DRY RUN: would run '{command}' on {csv_path.name}")
        return

    last_err: Optional[Exception] = None
    for cmd in attempts:
        try:
            subprocess.run(cmd, check=True)
            last_err = None
            break
        except subprocess.CalledProcessError as e:
            last_err = e

    if last_err is not None:
        raise RuntimeError(
            f"finance_master.py failed for command '{command}'.\n"
            f"Tried:\n  - " + "\n  - ".join(" ".join(x) for x in attempts) +
            f"\nLast error: {last_err}"
        )

    after = snapshot_files(outdir)
    new_files = diff_new_files(before, after)

    # ✅ SMART RENAME (no duplicate command tag)
    base_prefix = safe_slug(bucket_label)
    cmd_slug = safe_slug(command)

    for rel in new_files:
        src = outdir / rel
        if not src.exists() or not src.is_file():
            continue

        src_name = src.name

        # If filename already starts with "<command>_", don't re-add command
        if src_name.lower().startswith(cmd_slug.lower() + "_"):
            dest_name = f"{base_prefix}_{src_name}"
        else:
            dest_name = f"{base_prefix}_{cmd_slug}_{src_name}"

        dest = src.with_name(dest_name)

        # Avoid collisions
        if dest.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = src.with_name(f"{base_prefix}_{cmd_slug}_{stamp}_{src_name}")

        src.rename(dest)

    print(f"✅ {bucket_label}: '{command}' tagged {len(new_files)} output file(s).")


def run_bucket(
    label: str,
    csv_path: Path,
    finance_master_py: Path,
    outdir: Path,
    dry_run: bool,
) -> None:
    print("\n==============================")
    print(f"🏷  BUCKET: {label}")
    print(f"📄 CSV:    {csv_path}")
    print("==============================")

    for cmd in COMMANDS:
        run_finance_master_command(
            finance_master_py=finance_master_py,
            csv_path=csv_path,
            command=cmd,
            outdir=outdir,
            bucket_label=label,
            dry_run=dry_run,
        )


# -----------------------------
# CLI
# -----------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="finance_master_bucket_runner.py",
        description="Run finance_master.py reports for 12m + 18m from one 18-month CSV and label outputs.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Example:\n"
            "  python3 finance_master_bucket_runner.py 18m.csv\n\n"
            "Creates:\n"
            "  - _bucket_tmp/last12m.csv\n"
            "Runs reports on both buckets and prefixes outputs with 12m_ / 18m_.\n"
        ),
    )
    p.add_argument("csv_18m", help="Path to your 18-month CSV export")
    p.add_argument("--finance-master", default="finance_master.py", help="Path to finance_master.py (default: ./finance_master.py)")
    p.add_argument("--outdir", default="output", help="Output directory used by finance_master.py (default: output)")
    p.add_argument("--dry-run", action="store_true", help="Print what would run; do not execute anything")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    csv_18m = Path(args.csv_18m).expanduser().resolve()
    if not csv_18m.exists():
        print(f"ERROR: CSV not found: {csv_18m}")
        return 1

    finance_master_py = Path(args.finance_master).expanduser().resolve()
    if not finance_master_py.exists():
        print(f"ERROR: finance_master.py not found: {finance_master_py}")
        return 1

    outdir = Path(args.outdir).expanduser().resolve()

    # Create 12m slice
    temp_dir = csv_18m.parent / "_bucket_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    csv_12m = temp_dir / "last12m.csv"

    slice_result = write_last_n_months_csv(csv_18m, months=12, out_csv=csv_12m)
    print("✅ Built 12-month slice CSV")
    print(f"   Total rows in 18m CSV: {slice_result.total_rows}")
    print(f"   Rows in 12m slice:     {slice_result.kept_rows}")
    if slice_result.date_min and slice_result.date_max:
        print(f"   Date range (12m):      {slice_result.date_min.date()} → {slice_result.date_max.date()}")

    # Run both buckets
    run_bucket("12m", csv_12m, finance_master_py, outdir, dry_run=args.dry_run)
    run_bucket("18m", csv_18m, finance_master_py, outdir, dry_run=args.dry_run)

    print("\n✅ All buckets complete.")
    print(f"📁 Tagged outputs are in: {outdir}")
    print(f"🗂 Temp slice CSV stored in: {temp_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

