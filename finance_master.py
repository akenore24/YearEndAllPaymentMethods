#!/usr/bin/env python3
"""
finance_master.py — DRY CLI (CSV -> Excel/PDF) with modular finance_core.

Install:
  pip3 install -r requirements.txt

Quick starts:
  python3 finance_master.py --help
  python3 finance_master.py all
  python3 finance_master.py spacing
  python3 finance_master.py --in output/csv/expenses_raw_spacing_fixed.csv all

Outputs go to:
  output/csv, output/xlsx, output/pdf
"""
from __future__ import annotations

import argparse
from pathlib import Path

from finance_core.config import (
    DEFAULT_INPUT_CSV,
    DEFAULT_SPACING_OUT,
    DEFAULT_EXCEL_DETAIL_OUT,
    DEFAULT_EXCEL_SUMMARY_OUT,
    DEFAULT_EXCEL_FAMILIES_OUT,
    DEFAULT_PDF_DETAIL_OUT,
    DEFAULT_PDF_SUMMARY_OUT,
    DEFAULT_PDF_FAMILIES_SORTED_OUT,
    DEFAULT_PDF_QUICK_OUT,
    DEFAULT_PDF_ORGANIZED_OUT,
    READY_TO_PRINT_XLSX,
    READY_TO_PRINT_PDF,
    DEFAULT_PDF_QUICK_18MO_OUT,
    DEFAULT_PDF_HIGHEST_TXNS_OUT,
    BUCKETS_18MO,
    READY_FAMILIES_PRIORITY,
)
from finance_core.paths import out_path
from finance_core.utils import mt_timestamp_line, fmt_money, normalize_spaces
from finance_core.io_csv import load_csv_rows, write_csv_rows, ensure_required
from finance_core.cleaning import clean_rows
from finance_core.grouping import group_key, group_key_organized
from finance_core.summaries import (
    sort_rows_for_detail,
    build_summary,
    sort_summary_items,
    apply_zelle_blocking,
    reorder_priority_first,
)
from finance_core.excel_reports import (
    write_excel_detail_grouped,
    write_excel_summary_items,
    write_ready_to_print_excel,
)
from finance_core.pdf_reports import (
    write_pdf_detail,
    write_pdf_summary,
    write_pdf_quick_summary,
    write_ready_to_print_pdf,
)
from finance_core.buckets import write_pdf_quick_summary_18mo


# -----------------------------
# Runners
# -----------------------------
def run_spacing_fix(in_path: Path, out_name: str):
    headers, rows = load_csv_rows(in_path)
    if not headers:
        raise ValueError("No headers found in CSV.")
    fixed = [{h: normalize_spaces(r.get(h, "")) for h in headers} for r in rows]
    out_csv = out_path("csv", out_name)
    write_csv_rows(out_csv, headers, fixed)
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Spacing fixed: {out_csv}")

def run_quick(in_path: Path, limit: int, sort_mode: str, organized: bool):
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    summary = build_summary(cleaned, key_fn=key_fn)
    items = sort_summary_items(summary, sort_mode=sort_mode)[:max(0, int(limit))]
    print(mt_timestamp_line("Generated (MT)"))
    print("✅ The 18 Months Quick Summary:")
    for name, info in items:
        print(f"  - {name}: {info['txns']} txns, {fmt_money(info['total'])}")

def run_quick_pdf(in_path: Path, out_pdf: str, limit: int, sort_mode: str, organized: bool):
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    summary = build_summary(cleaned, key_fn=key_fn)
    items = sort_summary_items(summary, sort_mode=sort_mode)
    pdf_path = out_path("pdf", out_pdf)
    write_pdf_quick_summary(items, pdf_path, sort_mode=sort_mode, limit=limit)
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Quick Summary PDF created: {pdf_path}")

def run_exec_txns_desc(in_path: Path, out_pdf: str, limit: int, organized: bool):
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    summary = build_summary(cleaned, key_fn=key_fn)
    items = sort_summary_items(summary, sort_mode="txns")
    pdf_path = out_path("pdf", out_pdf)
    write_pdf_quick_summary(
        items, pdf_path, sort_mode="txns", limit=limit,
        title_override="Quick Executive Summary — Highest to Lowest Transactions"
    )
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Highest-to-Lowest Executive Summary created: {pdf_path}")

def run_quick_pdf_18mo(in_path: Path, out_pdf: str, limit: int, sort_mode: str, organized: bool):
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    pdf_path = out_path("pdf", out_pdf)
    write_pdf_quick_summary_18mo(
        rows=cleaned,
        pdf_path=pdf_path,
        buckets=BUCKETS_18MO,
        key_fn=key_fn,
        sort_mode=sort_mode,
        limit=limit,
    )
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ 18-month Executive Quick Summary PDF created: {pdf_path}")

def run_pipeline(in_path: Path,
                 excel_detail_out: str,
                 excel_summary_out: str,
                 pdf_detail_out: str,
                 pdf_summary_out: str,
                 summary_sort: str):
    headers, rows = load_csv_rows(in_path)
    if not headers:
        raise ValueError("No headers found in CSV.")
    ensure_required(headers, ["Description", "Amount"])

    cleaned, _removed = clean_rows(rows)
    detail_rows = sort_rows_for_detail(cleaned, key_fn=group_key)
    summary = build_summary(detail_rows, key_fn=group_key)

    excel_detail_path = out_path("xlsx", excel_detail_out)
    excel_summary_path = out_path("xlsx", excel_summary_out)
    pdf_detail_path = out_path("pdf", pdf_detail_out)
    pdf_summary_path = out_path("pdf", pdf_summary_out)

    write_excel_detail_grouped(headers, detail_rows, excel_detail_path, key_fn=group_key)
    items = sort_summary_items(summary, sort_mode=summary_sort)
    write_excel_summary_items(items, excel_summary_path, title="Family Summary")

    write_pdf_detail(detail_rows, pdf_detail_path, key_fn=group_key)
    write_pdf_summary(items, pdf_summary_path, title="The 18 months Expense Summary")

    print(mt_timestamp_line("Generated (MT)"))
    print("✅ Pipeline complete:")
    print(f"   - {excel_detail_path}")
    print(f"   - {excel_summary_path}")
    print(f"   - {pdf_detail_path}")
    print(f"   - {pdf_summary_path}")

def run_pdf_families(in_path: Path, out_pdf: str, zelle_block: str, sort_mode: str):
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    summary = build_summary(cleaned, key_fn=group_key)
    items = sort_summary_items(summary, sort_mode=sort_mode)
    items = apply_zelle_blocking(items, zelle_block=zelle_block)
    pdf_path = out_path("pdf", out_pdf)
    write_pdf_summary(items, pdf_path, title="Families Summary")
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ PDF created: {pdf_path}")

def run_excel_families(in_path: Path, out_xlsx: str, zelle_block: str, sort_mode: str):
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    summary = build_summary(cleaned, key_fn=group_key)
    items = sort_summary_items(summary, sort_mode=sort_mode)
    items = apply_zelle_blocking(items, zelle_block=zelle_block)
    xlsx_path = out_path("xlsx", out_xlsx)
    write_excel_summary_items(items, xlsx_path, title="Family Summary Sorted")
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Excel created: {xlsx_path}")

def run_organized_pdf(in_path: Path, out_pdf: str, top_total: int):
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    summary = build_summary(cleaned, key_fn=group_key_organized)
    items_total = sort_summary_items(summary, sort_mode="total")[:max(0, int(top_total))]
    pdf_path = out_path("pdf", out_pdf)
    write_pdf_summary(items_total, pdf_path, title="Organized Report (Top by Total)")
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Organized PDF created: {pdf_path}")

def run_ready_to_print(in_path: Path, top_other: int):
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)

    # Families summary (ZELLE unified)
    families_summary = build_summary(cleaned, key_fn=group_key_organized)
    families_items = sort_summary_items(families_summary, sort_mode="total")
    families_items = reorder_priority_first(families_items, READY_FAMILIES_PRIORITY)

    # keep all priority + top N others
    if top_other is not None and top_other >= 0:
        priority_set = set(READY_FAMILIES_PRIORITY)
        kept_priority = [(n, i) for (n, i) in families_items if n in priority_set]
        others = [(n, i) for (n, i) in families_items if n not in priority_set]
        families_items = kept_priority + (others[:top_other] if top_other else [])

    # Zelle by person (ZELLE - Person)
    zelle_people_summary = build_summary(cleaned, key_fn=group_key)
    zelle_people_all = sort_summary_items(zelle_people_summary, sort_mode="total")
    zelle_people_items = [(n, i) for (n, i) in zelle_people_all if n.upper().startswith("ZELLE - ")]

    xlsx_path = out_path("xlsx", READY_TO_PRINT_XLSX)
    pdf_path = out_path("pdf", READY_TO_PRINT_PDF)
    write_ready_to_print_excel(families_items, zelle_people_items, xlsx_path)
    write_ready_to_print_pdf(families_items, zelle_people_items, pdf_path)

    print(mt_timestamp_line("Generated (MT)"))
    print("✅ Ready-to-print outputs created:")
    print(f"   - {xlsx_path}")
    print(f"   - {pdf_path}")

def run_all(in_path: Path):
    print(mt_timestamp_line("Generated (MT)"))
    print("🚀 Running ALL reports...")

    run_pipeline(
        in_path=in_path,
        excel_detail_out=DEFAULT_EXCEL_DETAIL_OUT,
        excel_summary_out=DEFAULT_EXCEL_SUMMARY_OUT,
        pdf_detail_out=DEFAULT_PDF_DETAIL_OUT,
        pdf_summary_out=DEFAULT_PDF_SUMMARY_OUT,
        summary_sort="txns",
    )
    run_ready_to_print(in_path, top_other=25)
    run_quick_pdf(in_path, out_pdf=DEFAULT_PDF_QUICK_OUT, limit=60, sort_mode="txns", organized=False)
    run_quick_pdf_18mo(in_path, out_pdf=DEFAULT_PDF_QUICK_18MO_OUT, limit=15, sort_mode="total", organized=True)
    run_exec_txns_desc(in_path, out_pdf=DEFAULT_PDF_HIGHEST_TXNS_OUT, limit=25, organized=True)

    print("✅ ALL reports completed.")
    print("📂 Outputs created under output/ (csv/xlsx/pdf).")
    
    # Jan 13, 2026
    


# -----------------------------
# CLI
# -----------------------------
def main():
    p = argparse.ArgumentParser(description="Finance Master: clean + group + Excel/PDF outputs (GitHub-ready).")
    p.add_argument("--in", dest="input_csv", default=DEFAULT_INPUT_CSV, help="Input CSV filename (same folder).")

    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("spacing", help="Fix inconsistent spacing in raw CSV (no grouping, no deletions).")
    s.add_argument("--out", default=DEFAULT_SPACING_OUT, help="Output CSV filename.")

    q = sub.add_parser("quick", help="Print quick summary to console.")
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--sort", choices=["txns", "total"], default="txns")
    q.add_argument("--organized", action="store_true", help="Use organized grouping (ALL ZELLE together).")

    qp = sub.add_parser("quick_pdf", help="Create a 1-page Quick Summary PDF.")
    qp.add_argument("--out", default=DEFAULT_PDF_QUICK_OUT)
    qp.add_argument("--limit", type=int, default=60)
    qp.add_argument("--sort", choices=["txns", "total"], default="txns")
    qp.add_argument("--organized", action="store_true")

    htl = sub.add_parser("exec_txns_desc", help="Executive summary sorted by transaction count (high → low).")
    htl.add_argument("--out", default=DEFAULT_PDF_HIGHEST_TXNS_OUT)
    htl.add_argument("--limit", type=int, default=25)
    htl.add_argument("--organized", action="store_true")

    q18 = sub.add_parser("quick_pdf_18mo", help="Executive summary PDF split into 18-month buckets.")
    q18.add_argument("--out", default=DEFAULT_PDF_QUICK_18MO_OUT)
    q18.add_argument("--limit", type=int, default=15)
    q18.add_argument("--sort", choices=["txns", "total"], default="total")
    q18.add_argument("--organized", action="store_true")

    pl = sub.add_parser("pipeline", help="Excel detail+summary + PDF detail+summary.")
    pl.add_argument("--excel-detail-out", default=DEFAULT_EXCEL_DETAIL_OUT)
    pl.add_argument("--excel-summary-out", default=DEFAULT_EXCEL_SUMMARY_OUT)
    pl.add_argument("--pdf-detail-out", default=DEFAULT_PDF_DETAIL_OUT)
    pl.add_argument("--pdf-summary-out", default=DEFAULT_PDF_SUMMARY_OUT)
    pl.add_argument("--summary-sort", choices=["txns", "total"], default="txns")

    pf = sub.add_parser("pdf_families", help="PDF families summary (sorted).")
    pf.add_argument("--out", default=DEFAULT_PDF_FAMILIES_SORTED_OUT)
    pf.add_argument("--zelle-block", choices=["first", "last", "none"], default="first")
    pf.add_argument("--sort", choices=["total", "txns"], default="total")

    ef = sub.add_parser("excel_families", help="Excel families summary (sorted).")
    ef.add_argument("--out", default=DEFAULT_EXCEL_FAMILIES_OUT)
    ef.add_argument("--zelle-block", choices=["first", "last", "none"], default="first")
    ef.add_argument("--sort", choices=["total", "txns"], default="total")

    op = sub.add_parser("organized_pdf", help="Organized PDF (Top by Total).")
    op.add_argument("--out", default=DEFAULT_PDF_ORGANIZED_OUT)
    op.add_argument("--top-total", type=int, default=25)

    rtp = sub.add_parser("ready_to_print", help="Create ready_to_print.xlsx and ready_to_print.pdf.")
    rtp.add_argument("--top-other", type=int, default=25)

    sub.add_parser("all", help="Run EVERYTHING: pipeline + ready_to_print + quick PDFs.")

    args = p.parse_args()

    in_path = Path(args.input_csv)
    if not in_path.exists():
        # allow paths like output/csv/file.csv
        in_path = Path(__file__).parent / args.input_csv
    if not in_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {args.input_csv}")

    if args.cmd == "spacing":
        run_spacing_fix(in_path, args.out)
    elif args.cmd == "quick":
        run_quick(in_path, limit=args.limit, sort_mode=args.sort, organized=args.organized)
    elif args.cmd == "quick_pdf":
        run_quick_pdf(in_path, out_pdf=args.out, limit=args.limit, sort_mode=args.sort, organized=args.organized)
    elif args.cmd == "exec_txns_desc":
        run_exec_txns_desc(in_path, out_pdf=args.out, limit=args.limit, organized=args.organized)
    elif args.cmd == "quick_pdf_18mo":
        run_quick_pdf_18mo(in_path, out_pdf=args.out, limit=args.limit, sort_mode=args.sort, organized=args.organized)
    elif args.cmd == "pipeline":
        run_pipeline(
            in_path=in_path,
            excel_detail_out=args.excel_detail_out,
            excel_summary_out=args.excel_summary_out,
            pdf_detail_out=args.pdf_detail_out,
            pdf_summary_out=args.pdf_summary_out,
            summary_sort=args.summary_sort,
        )
    elif args.cmd == "pdf_families":
        run_pdf_families(in_path, out_pdf=args.out, zelle_block=args.zelle_block, sort_mode=args.sort)
    elif args.cmd == "excel_families":
        run_excel_families(in_path, out_xlsx=args.out, zelle_block=args.zelle_block, sort_mode=args.sort)
    elif args.cmd == "organized_pdf":
        run_organized_pdf(in_path, out_pdf=args.out, top_total=args.top_total)
    elif args.cmd == "ready_to_print":
        run_ready_to_print(in_path, top_other=args.top_other)
    elif args.cmd == "all":
        run_all(in_path)

if __name__ == "__main__":
    main()
