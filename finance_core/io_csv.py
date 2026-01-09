"""
finance_core.io_csv
CSV reading/writing + column validation.
"""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Any, Dict, List, Tuple

def load_csv_rows(csv_path: Path) -> Tuple[List[str], List[Dict[str, Any]]]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames or []
    return headers, rows

def write_csv_rows(out_path: Path, headers: List[str], rows: List[Dict[str, Any]]) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)

def ensure_required(headers: List[str], required: List[str]) -> None:
    missing = [h for h in required if h not in headers]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
