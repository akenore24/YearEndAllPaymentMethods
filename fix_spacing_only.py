
#!/usr/bin/env python3
"""
fix_spacing_only.py

Purpose:
- Read RAW bank CSV
- Fix inconsistent spacing in text cells (collapse whitespace)
- Output a NEW CSV with the same columns and row order

This does NOT:
- group
- sort
- remove rows
- change amounts/dates

Input (same folder):
  expenses.csv

Output (same folder):
  expenses_raw_spacing_fixed.csv
"""

import csv
from pathlib import Path


INPUT_CSV = "expenses.csv"
OUTPUT_CSV = "expenses_raw_spacing_fixed.csv"


def normalize_spaces(text: str) -> str:
    """Collapse all whitespace (spaces/tabs/newlines) into a single space."""
    return " ".join((text or "").split()).strip()


def is_texty(value) -> bool:
    """Return True if this value should be treated as text and normalized."""
    # In CSV everything is text, but keep it simple:
    # Normalize strings; leave None alone.
    return value is not None


def main():
    base_dir = Path(__file__).parent
    in_path = base_dir / INPUT_CSV
    out_path = base_dir / OUTPUT_CSV

    if not in_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {in_path}")

    with open(in_path, newline="", encoding="utf-8") as fin:
        reader = csv.DictReader(fin)
        if not reader.fieldnames:
            raise ValueError("No headers found in CSV (fieldnames is empty).")

        fieldnames = reader.fieldnames
        rows = list(reader)

    # Fix spacing in every cell (safe + reversible)
    fixed_rows = []
    for r in rows:
        fixed = {}
        for col in fieldnames:
            val = r.get(col, "")
            fixed[col] = normalize_spaces(val) if is_texty(val) else val
        fixed_rows.append(fixed)

    with open(out_path, "w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(fixed_rows)

    print("✅ Spacing fixed (raw cleanup only)")
    print(f"📥 Input : {in_path.name}")
    print(f"📤 Output: {out_path.name}")


if __name__ == "__main__":
    main()

