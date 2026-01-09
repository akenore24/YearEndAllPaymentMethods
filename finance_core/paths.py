"""
finance_core.paths
Output folder helpers.
"""
from __future__ import annotations
from pathlib import Path

OUTPUT_DIR = Path("output")
OUT_CSV_DIR = OUTPUT_DIR / "csv"
OUT_XLSX_DIR = OUTPUT_DIR / "xlsx"
OUT_PDF_DIR = OUTPUT_DIR / "pdf"

def ensure_output_dirs() -> None:
    OUT_CSV_DIR.mkdir(parents=True, exist_ok=True)
    OUT_XLSX_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PDF_DIR.mkdir(parents=True, exist_ok=True)

def out_path(kind: str, filename: str) -> Path:
    ensure_output_dirs()
    k = kind.lower()
    if k == "csv":
        return OUT_CSV_DIR / filename
    if k == "xlsx":
        return OUT_XLSX_DIR / filename
    if k == "pdf":
        return OUT_PDF_DIR / filename
    raise ValueError(f"Unknown output kind: {kind}")
