#!/usr/bin/env python3
"""
#Jan 13, 2026 06:00PM

grand_finance_master.py

ONE FILE that includes:
1) Your full finance_master.py functionality (powered by finance_core/*)
2) wf_transfer_cleaner.py functionality as subcommands:
   - wf_clean  : clean a given WF export CSV
   - wf_to_all : run wf_clean, then run finance ALL on clean output

SMART OPEN (this upgrade):
- wf_to_all --open       -> opens ONLY the PDF files that were actually created in THIS run
- wf_to_all --open-xlsx  -> opens ONLY the Excel files that were actually created in THIS run

Install:
  pip3 install -r requirements.txt
  pip3 install reportlab

Examples:
  python3 grand_finance_master.py wf_to_all expenses.csv --outdir output/csv --summary-pdf wf_transfer_summary.pdf --open --open-xlsx
  python3 grand_finance_master.py wf_to_all --latest --outdir output/csv --summary-pdf wf_transfer_summary.pdf --open-xlsx
"""

from __future__ import annotations

import argparse
import csv
import os
import platform
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, List, Optional, Any, Iterable

# -----------------------------
# finance_master imports (your modular system)
# -----------------------------
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


# ============================================================
# Helpers: robust path resolution + --latest finder + smart open
# ============================================================

def resolve_input_path(path_str: str) -> Path:
    p = Path(path_str).expanduser()
    if p.exists():
        return p.resolve()
    alt = Path(__file__).parent / path_str
    if alt.exists():
        return alt.resolve()
    return p.resolve()


def _default_latest_search_dirs() -> List[Path]:
    dirs: List[Path] = []
    try:
        dirs.append(Path.cwd())
    except Exception:
        pass
    try:
        dirs.append(Path(__file__).resolve().parent)
    except Exception:
        pass
    try:
        home = Path.home()
        for name in ("Downloads", "Desktop", "Documents"):
            pp = home / name
            if pp.exists():
                dirs.append(pp)
    except Exception:
        pass

    seen = set()
    unique: List[Path] = []
    for d in dirs:
        try:
            dd = d.expanduser().resolve()
        except Exception:
            dd = d
        if dd.exists() and dd.is_dir() and dd not in seen:
            unique.append(dd)
            seen.add(dd)
    return unique


def _iter_dirs_limited_depth(base: Path, max_depth: int) -> Iterable[Path]:
    yield base
    if max_depth <= 0:
        return
    level = [base]
    for _ in range(max_depth):
        next_level: List[Path] = []
        for d in level:
            try:
                for sub in d.iterdir():
                    if sub.is_dir():
                        yield sub
                        next_level.append(sub)
            except Exception:
                continue
        level = next_level


def find_latest_csv(patterns: List[str], search_dirs: List[Path], max_depth: int = 2) -> Optional[Path]:
    candidates: List[Path] = []
    for root in search_dirs:
        if not root.exists() or not root.is_dir():
            continue
        for d in _iter_dirs_limited_depth(root, max_depth=max_depth):
            for pat in patterns:
                try:
                    candidates.extend(d.glob(pat))
                except Exception:
                    continue

    candidates = [c for c in candidates if c.is_file() and c.suffix.lower() == ".csv"]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def resolve_wf_input(args: argparse.Namespace) -> Path:
    if getattr(args, "input_csv", None):
        if str(args.input_csv).strip():
            p = resolve_input_path(args.input_csv)
            if not p.exists():
                raise FileNotFoundError(f"WF input CSV not found: {args.input_csv}")
            return p

    if getattr(args, "latest", False):
        patterns = [s.strip() for s in args.latest_pattern.split(",") if s.strip()]

        dirs: List[Path] = []
        for d in (args.latest_dirs or []):
            dp = Path(d).expanduser()
            if dp.exists() and dp.is_dir():
                dirs.append(dp.resolve())

        dirs.extend(_default_latest_search_dirs())

        seen = set()
        final_dirs: List[Path] = []
        for d in dirs:
            if d not in seen:
                final_dirs.append(d)
                seen.add(d)

        latest = find_latest_csv(patterns=patterns, search_dirs=final_dirs, max_depth=args.latest_depth)
        if latest is None:
            dirs_txt = ", ".join(str(d) for d in final_dirs)
            raise FileNotFoundError(
                f"--latest was used but no CSV matched patterns={patterns} in dirs={dirs_txt}"
            )
        return latest.resolve()

    raise ValueError("You must provide a WF CSV file path OR use --latest.")


def _open_paths(paths: List[Path]) -> None:
    existing = [p for p in paths if p and p.exists()]
    if not existing:
        print("ℹ️ Nothing to open (no files created or they don't exist).")
        return

    system = platform.system().lower()
    for p in existing:
        try:
            if system == "darwin":
                subprocess.run(["open", str(p)], check=False)
            elif system == "windows":
                os.startfile(str(p))  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(p)], check=False)
        except Exception as e:
            print(f"⚠️ Could not open {p}: {e}")


def _filter_created(created: List[Path], exts: Tuple[str, ...]) -> List[Path]:
    exts_l = tuple(e.lower() for e in exts)
    out: List[Path] = []
    seen = set()
    for p in created:
        if not p:
            continue
        try:
            pp = p.resolve()
        except Exception:
            pp = p
        if pp.suffix.lower() in exts_l and pp.exists() and pp not in seen:
            out.append(pp)
            seen.add(pp)
    return out


# ============================================================
# Part A) finance_master runners (return created outputs)
# ============================================================

def run_spacing_fix(in_path: Path, out_name: str) -> List[Path]:
    headers, rows = load_csv_rows(in_path)
    if not headers:
        raise ValueError("No headers found in CSV.")
    fixed = [{h: normalize_spaces(r.get(h, "")) for h in headers} for r in rows]
    out_csv = Path(out_path("csv", out_name))
    write_csv_rows(out_csv, headers, fixed)
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Spacing fixed: {out_csv}")
    return [out_csv]


def run_quick(in_path: Path, limit: int, sort_mode: str, organized: bool) -> List[Path]:
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    summary = build_summary(cleaned, key_fn=key_fn)
    items = sort_summary_items(summary, sort_mode=sort_mode)[:max(0, int(limit))]
    print(mt_timestamp_line("Generated (MT)"))
    print("✅ Quick Summary:")
    for name, info in items:
        print(f"  - {name}: {info['txns']} txns, {fmt_money(info['total'])}")
    return []


def run_quick_pdf(in_path: Path, out_pdf: str, limit: int, sort_mode: str, organized: bool) -> List[Path]:
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    summary = build_summary(cleaned, key_fn=key_fn)
    items = sort_summary_items(summary, sort_mode=sort_mode)
    pdf_path = Path(out_path("pdf", out_pdf))
    write_pdf_quick_summary(items, pdf_path, sort_mode=sort_mode, limit=limit)
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Quick Summary PDF created: {pdf_path}")
    return [pdf_path]


def run_exec_txns_desc(in_path: Path, out_pdf: str, limit: int, organized: bool) -> List[Path]:
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    summary = build_summary(cleaned, key_fn=key_fn)
    items = sort_summary_items(summary, sort_mode="txns")
    pdf_path = Path(out_path("pdf", out_pdf))
    write_pdf_quick_summary(
        items,
        pdf_path,
        sort_mode="txns",
        limit=limit,
        title_override="Quick Executive Summary — Highest to Lowest Transactions",
    )
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Highest-to-Lowest Executive Summary created: {pdf_path}")
    return [pdf_path]


def run_quick_pdf_18mo(in_path: Path, out_pdf: str, limit: int, sort_mode: str, organized: bool) -> List[Path]:
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    pdf_path = Path(out_path("pdf", out_pdf))
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
    return [pdf_path]


def run_pipeline(
    in_path: Path,
    excel_detail_out: str,
    excel_summary_out: str,
    pdf_detail_out: str,
    pdf_summary_out: str,
    summary_sort: str,
) -> List[Path]:
    headers, rows = load_csv_rows(in_path)
    if not headers:
        raise ValueError("No headers found in CSV.")
    ensure_required(headers, ["Description", "Amount"])

    cleaned, _removed = clean_rows(rows)
    detail_rows = sort_rows_for_detail(cleaned, key_fn=group_key)
    summary = build_summary(detail_rows, key_fn=group_key)

    excel_detail_path = Path(out_path("xlsx", excel_detail_out))
    excel_summary_path = Path(out_path("xlsx", excel_summary_out))
    pdf_detail_path = Path(out_path("pdf", pdf_detail_out))
    pdf_summary_path = Path(out_path("pdf", pdf_summary_out))

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

    return [excel_detail_path, excel_summary_path, pdf_detail_path, pdf_summary_path]


def run_pdf_families(in_path: Path, out_pdf: str, zelle_block: str, sort_mode: str) -> List[Path]:
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    summary = build_summary(cleaned, key_fn=group_key)
    items = sort_summary_items(summary, sort_mode=sort_mode)
    items = apply_zelle_blocking(items, zelle_block=zelle_block)
    pdf_path = Path(out_path("pdf", out_pdf))
    write_pdf_summary(items, pdf_path, title="Families Summary")
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ PDF created: {pdf_path}")
    return [pdf_path]


def run_excel_families(in_path: Path, out_xlsx: str, zelle_block: str, sort_mode: str) -> List[Path]:
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    summary = build_summary(cleaned, key_fn=group_key)
    items = sort_summary_items(summary, sort_mode=sort_mode)
    items = apply_zelle_blocking(items, zelle_block=zelle_block)
    xlsx_path = Path(out_path("xlsx", out_xlsx))
    write_excel_summary_items(items, xlsx_path, title="Family Summary Sorted")
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Excel created: {xlsx_path}")
    return [xlsx_path]


def run_organized_pdf(in_path: Path, out_pdf: str, top_total: int) -> List[Path]:
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    summary = build_summary(cleaned, key_fn=group_key_organized)
    items_total = sort_summary_items(summary, sort_mode="total")[:max(0, int(top_total))]
    pdf_path = Path(out_path("pdf", out_pdf))
    write_pdf_summary(items_total, pdf_path, title="Organized Report (Top by Total)")
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Organized PDF created: {pdf_path}")
    return [pdf_path]


def run_ready_to_print(in_path: Path, top_other: int) -> List[Path]:
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)

    families_summary = build_summary(cleaned, key_fn=group_key_organized)
    families_items = sort_summary_items(families_summary, sort_mode="total")
    families_items = reorder_priority_first(families_items, READY_FAMILIES_PRIORITY)

    if top_other is not None and top_other >= 0:
        priority_set = set(READY_FAMILIES_PRIORITY)
        kept_priority = [(n, i) for (n, i) in families_items if n in priority_set]
        others = [(n, i) for (n, i) in families_items if n not in priority_set]
        families_items = kept_priority + (others[:top_other] if top_other else [])

    zelle_people_summary = build_summary(cleaned, key_fn=group_key)
    zelle_people_all = sort_summary_items(zelle_people_summary, sort_mode="total")
    zelle_people_items = [(n, i) for (n, i) in zelle_people_all if n.upper().startswith("ZELLE - ")]

    xlsx_path = Path(out_path("xlsx", READY_TO_PRINT_XLSX))
    pdf_path = Path(out_path("pdf", READY_TO_PRINT_PDF))
    write_ready_to_print_excel(families_items, zelle_people_items, xlsx_path)
    write_ready_to_print_pdf(families_items, zelle_people_items, pdf_path)

    print(mt_timestamp_line("Generated (MT)"))
    print("✅ Ready-to-print outputs created:")
    print(f"   - {xlsx_path}")
    print(f"   - {pdf_path}")

    return [xlsx_path, pdf_path]


def run_all(in_path: Path) -> List[Path]:
    print(mt_timestamp_line("Generated (MT)"))
    print("🚀 Running ALL reports...")

    created: List[Path] = []
    created += run_pipeline(
        in_path=in_path,
        excel_detail_out=DEFAULT_EXCEL_DETAIL_OUT,
        excel_summary_out=DEFAULT_EXCEL_SUMMARY_OUT,
        pdf_detail_out=DEFAULT_PDF_DETAIL_OUT,
        pdf_summary_out=DEFAULT_PDF_SUMMARY_OUT,
        summary_sort="txns",
    )
    created += run_ready_to_print(in_path, top_other=25)
    created += run_quick_pdf(in_path, out_pdf=DEFAULT_PDF_QUICK_OUT, limit=60, sort_mode="txns", organized=False)
    created += run_quick_pdf_18mo(in_path, out_pdf=DEFAULT_PDF_QUICK_18MO_OUT, limit=15, sort_mode="total", organized=True)
    created += run_exec_txns_desc(in_path, out_pdf=DEFAULT_PDF_HIGHEST_TXNS_OUT, limit=25, organized=True)

    print("✅ ALL reports completed.")
    print("📂 Outputs created under output/ (csv/xlsx/pdf).")
    return created


# ============================================================
# Part B) compare_quick_pdf (two CSVs -> one comparison PDF)
# ============================================================

def _require_reportlab():
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        return letter, inch, colors, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, getSampleStyleSheet
    except Exception as e:
        raise RuntimeError(
            "Missing dependency: reportlab\n"
            "Install with: pip3 install reportlab\n"
            f"Details: {e}"
        )

def _summary_map_from_csv(in_path: Path, organized: bool) -> Dict[str, Tuple[int, float]]:
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    summary = build_summary(cleaned, key_fn=key_fn)
    items = sort_summary_items(summary, sort_mode="name")
    return {name: (info["txns"], info["total"]) for name, info in items}

def _write_comparison_pdf(
    out_pdf_path: Path,
    label12: str,
    label18: str,
    rows: List[Tuple[str, int, float, int, float, float]],
    title: str = "Expenses Quick Summary Comparison (12m vs 18m)",
):
    letter, inch, colors, SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, getSampleStyleSheet = _require_reportlab()
    styles = getSampleStyleSheet()

    out_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out_pdf_path),
        pagesize=letter,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Paragraph(f"Left: {label12} | Right: {label18}", styles["Normal"]))
    story.append(Spacer(1, 0.15 * inch))

    header = ["Group", "12m Txns", "12m Total", "18m Txns", "18m Total", "Δ Total (18m-12m)"]
    table_data = [header]
    for g, tx12, tot12, tx18, tot18, delta in rows:
        table_data.append([g, str(tx12), fmt_money(tot12), str(tx18), fmt_money(tot18), fmt_money(delta)])

    tbl = Table(table_data, colWidths=[2.35 * inch, 0.75 * inch, 1.0 * inch, 0.75 * inch, 1.0 * inch, 1.15 * inch])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ]
        )
    )
    story.append(tbl)
    doc.build(story)

def run_compare_quick_pdf(in12: Path, in18: Path, out_pdf: str, organized: bool, sort_mode: str, limit: int) -> List[Path]:
    m12 = _summary_map_from_csv(in12, organized=organized)
    m18 = _summary_map_from_csv(in18, organized=organized)
    all_groups = sorted(set(m12) | set(m18))

    rows: List[Tuple[str, int, float, int, float, float]] = []
    for g in all_groups:
        tx12, tot12 = m12.get(g, (0, 0.0))
        tx18, tot18 = m18.get(g, (0, 0.0))
        delta = tot18 - tot12
        rows.append((g, tx12, tot12, tx18, tot18, delta))

    if sort_mode == "delta_abs":
        rows.sort(key=lambda r: abs(r[5]), reverse=True)
    elif sort_mode == "delta":
        rows.sort(key=lambda r: r[5], reverse=True)
    elif sort_mode == "total12":
        rows.sort(key=lambda r: r[2], reverse=True)
    elif sort_mode == "total18":
        rows.sort(key=lambda r: r[4], reverse=True)
    else:
        rows.sort(key=lambda r: r[0])

    if limit and limit > 0:
        rows = rows[:limit]

    pdf_path = Path(out_path("pdf", out_pdf))
    _write_comparison_pdf(pdf_path, in12.stem, in18.stem, rows)
    print(mt_timestamp_line("Generated (MT)"))
    print(f"✅ Comparison PDF created: {pdf_path}")
    return [pdf_path]


# ============================================================
# Part C) wf_transfer_cleaner (embedded as wf_clean + wf_to_all)
# ============================================================

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

_SPACE_REGEX = re.compile(r"\s+")

def wf_normalize_spacing(s: str) -> str:
    if not s:
        return ""
    return _SPACE_REGEX.sub(" ", s).strip()

def wf_normalize_row_spacing(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: wf_normalize_spacing(v) if isinstance(v, str) else v for k, v in row.items()}

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

def wf_find_description_field(headers: List[str]) -> str:
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

def wf_find_amount_field(headers: List[str]) -> Optional[str]:
    lower_to_real = {h.lower(): h for h in headers}
    for cand in AMOUNT_CANDIDATES:
        key = cand.lower()
        if key in lower_to_real:
            return lower_to_real[key]
    for h in headers:
        hl = h.lower()
        if "amount" in hl:
            return h
        if hl in ("amt", "transactionamt", "transaction_amt"):
            return h
    return None

_AMOUNT_CLEAN_REGEX = re.compile(r"[^0-9.\-()]+")

def wf_parse_amount(value: Any) -> float:
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0
    s = _AMOUNT_CLEAN_REGEX.sub("", s)
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    try:
        n = float(s)
    except ValueError:
        return 0.0
    return -abs(n) if neg else n

_ON_DATE_REGEX = re.compile(r"\bON\s+\d{2}/\d{2}/\d{2}\b", re.IGNORECASE)

def wf_split_multi_transactions_in_desc(desc: str) -> List[str]:
    desc = wf_normalize_spacing(desc)
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

KENORE_REGEX = re.compile(r"\bKENORE\b", re.IGNORECASE)

@dataclass(frozen=True)
class WfRemovalRule:
    key: str
    label: str
    pattern: re.Pattern
    requires_name: bool = False

WF_RULE_WAY2SAVE = WfRemovalRule(
    key="way2save_internal_transfer",
    label="Internal transfer: Way2Save Savings",
    pattern=re.compile(r"\bONLINE\s+TRANSFER\b.*\bWAY2SAVE\b.*\bSAVINGS\b", re.IGNORECASE),
    requires_name=True,
)
WF_RULE_WF_ACTIVE_CASH = WfRemovalRule(
    key="wf_active_cash_payment",
    label="Payment: WF Active Cash Visa",
    pattern=re.compile(r"\bONLINE\s+TRANSFER\b.*\bTO\b.*\bWELLS\s+FARGO\b.*\bACTIVE\s+CASH\b.*\bVISA\b.*\bCARD\b", re.IGNORECASE),
)
WF_RULE_WF_REFLECT = WfRemovalRule(
    key="wf_reflect_payment",
    label="Payment: WF Reflect Visa",
    pattern=re.compile(r"\bONLINE\s+TRANSFER\b.*\bTO\b.*\bWELLS\s+FARGO\b.*\bREFLECT\b.*\bVISA\b.*\bCARD\b", re.IGNORECASE),
)
WF_RULES: List[WfRemovalRule] = [WF_RULE_WAY2SAVE, WF_RULE_WF_ACTIVE_CASH, WF_RULE_WF_REFLECT]

def wf_classify(desc: str, require_name_filter: bool) -> Optional[WfRemovalRule]:
    if not desc:
        return None
    for rule in WF_RULES:
        if not rule.pattern.search(desc):
            continue
        if rule.requires_name and require_name_filter and not KENORE_REGEX.search(desc):
            continue
        return rule
    return None

@dataclass
class WfStats:
    kept_rows: int = 0
    kept_amount: float = 0.0
    removed_rows_by_key: Dict[str, int] = None  # type: ignore
    removed_amount_by_key: Dict[str, float] = None  # type: ignore

    def __post_init__(self):
        if self.removed_rows_by_key is None:
            self.removed_rows_by_key = {r.key: 0 for r in WF_RULES}
        if self.removed_amount_by_key is None:
            self.removed_amount_by_key = {r.key: 0.0 for r in WF_RULES}

    @property
    def total_removed_rows(self) -> int:
        return sum(self.removed_rows_by_key.values())

    @property
    def total_removed_amount(self) -> float:
        return sum(self.removed_amount_by_key.values())

def wf_money(n: float) -> str:
    return f"${n:,.2f}"

def wf_process_csv(
    input_csv: Path,
    out_clean: Path,
    out_report: Path,
    out_spacing: Optional[Path],
    dry_run: bool,
    no_name_filter: bool,
) -> Tuple[List[str], str, WfStats]:
    stats = WfStats()
    with input_csv.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if not headers:
            raise ValueError("CSV has no headers (first row must contain column names).")

        desc_field = wf_find_description_field(headers)
        amount_field = wf_find_amount_field(headers)

        spacing_rows_all: List[Dict[str, Any]] = []
        kept_rows: List[Dict[str, Any]] = []
        removed_rows: List[Dict[str, Any]] = []

        for row in reader:
            row = wf_normalize_row_spacing(row)
            spacing_rows_all.append(row)

            base_amount = wf_parse_amount(row.get(amount_field)) if amount_field else 0.0
            original_desc = row.get(desc_field, "") or ""
            chunks = wf_split_multi_transactions_in_desc(original_desc)

            for chunk in chunks:
                virtual_row = dict(row)
                virtual_row[desc_field] = chunk

                rule = wf_classify(chunk, require_name_filter=(not no_name_filter))
                if rule:
                    stats.removed_rows_by_key[rule.key] += 1
                    stats.removed_amount_by_key[rule.key] += base_amount
                    removed_rows.append({**virtual_row, "RemovalReason": rule.label})
                else:
                    stats.kept_rows += 1
                    stats.kept_amount += base_amount
                    kept_rows.append(virtual_row)

    if dry_run:
        return headers, desc_field, stats

    if out_spacing is not None:
        out_spacing.parent.mkdir(parents=True, exist_ok=True)
        with out_spacing.open("w", newline="", encoding="utf-8") as f_out:
            w = csv.DictWriter(f_out, fieldnames=headers)
            w.writeheader()
            w.writerows(spacing_rows_all)

    out_clean.parent.mkdir(parents=True, exist_ok=True)
    with out_clean.open("w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=headers)
        w.writeheader()
        w.writerows(kept_rows)

    out_report.parent.mkdir(parents=True, exist_ok=True)
    report_headers = headers[:] + (["RemovalReason"] if "RemovalReason" not in headers else [])
    with out_report.open("w", newline="", encoding="utf-8") as f_out:
        w = csv.DictWriter(f_out, fieldnames=report_headers)
        w.writeheader()
        w.writerows(removed_rows)

    return headers, desc_field, stats

def wf_write_summary_pdf(pdf_path: Path, input_csv: Path, stats: WfStats) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    width, height = letter

    left = 0.75 * inch
    top = height - 0.75 * inch
    line = 0.28 * inch

    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, top, "WF Transfer Cleaner — Summary Report")

    c.setFont("Helvetica", 10)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.drawString(left, top - 0.35 * inch, f"Generated: {ts} (local)")
    c.drawString(left, top - 0.55 * inch, f"Input file: {input_csv.name}")

    y = top - 1.05 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Category")
    c.drawRightString(width - left, y, "Rows / Total Amount")
    y -= 0.2 * inch
    c.setFont("Helvetica", 11)

    for rule in WF_RULES:
        rows = stats.removed_rows_by_key.get(rule.key, 0)
        amt = stats.removed_amount_by_key.get(rule.key, 0.0)
        c.drawString(left, y, rule.label)
        c.drawRightString(width - left, y, f"{rows}   /   {wf_money(amt)}")
        y -= line

    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "TOTAL REMOVED")
    c.drawRightString(width - left, y, f"{stats.total_removed_rows}   /   {wf_money(stats.total_removed_amount)}")
    y -= 0.35 * inch

    c.drawString(left, y, "ROWS LEFT (KEPT)")
    c.drawRightString(width - left, y, f"{stats.kept_rows}   /   {wf_money(stats.kept_amount)}")

    c.showPage()
    c.save()

def wf_print_snapshot(stats: WfStats) -> None:
    print("\n📌 Removal snapshot")
    print("-" * 52)
    for r in WF_RULES:
        rc = stats.removed_rows_by_key.get(r.key, 0)
        amt = stats.removed_amount_by_key.get(r.key, 0.0)
        print(f"{r.label:32s} {rc:6d}   {wf_money(amt):>14s}")
    print("-" * 52)
    print(f"{'TOTAL REMOVED':32s} {stats.total_removed_rows:6d}   {wf_money(stats.total_removed_amount):>14s}")
    print(f"{'ROWS LEFT (KEPT)':32s} {stats.kept_rows:6d}   {wf_money(stats.kept_amount):>14s}\n")

def run_wf_clean(args: argparse.Namespace) -> List[Path]:
    input_csv = resolve_input_path(args.input_csv)
    if not input_csv.exists():
        raise FileNotFoundError(f"WF input CSV not found: {args.input_csv}")

    out_clean = Path(args.out_clean).expanduser()
    out_report = Path(args.out_report).expanduser()
    out_spacing = None if args.no_out_spacing else Path(args.out_spacing).expanduser()

    if not out_clean.is_absolute():
        out_clean = input_csv.with_name(out_clean.name)
    if not out_report.is_absolute():
        out_report = input_csv.with_name(out_report.name)
    if out_spacing is not None and not out_spacing.is_absolute():
        out_spacing = input_csv.with_name(out_spacing.name)

    _headers, _desc, stats = wf_process_csv(
        input_csv=input_csv,
        out_clean=out_clean,
        out_report=out_report,
        out_spacing=out_spacing,
        dry_run=args.dry_run,
        no_name_filter=args.no_name_filter,
    )

    created: List[Path] = []
    print("✅ WF Clean Done")
    print(f"Input: {input_csv}")
    wf_print_snapshot(stats)

    if args.summary_pdf:
        pdf_path = Path(args.summary_pdf).expanduser()
        if not pdf_path.is_absolute():
            pdf_path = input_csv.with_name(pdf_path.name)
        wf_write_summary_pdf(pdf_path, input_csv, stats)
        print(f"🧾 Summary PDF created: {pdf_path}")
        created.append(pdf_path)

    if not args.dry_run:
        created.extend([out_clean, out_report])
        if out_spacing is not None:
            created.append(out_spacing)

    return created


def run_wf_to_all(args: argparse.Namespace) -> List[Path]:
    wf_csv = resolve_wf_input(args)

    outdir = Path(args.outdir).expanduser()
    if not outdir.is_absolute():
        outdir = (Path(__file__).parent / outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    out_clean = outdir / (args.out_clean or "clean.csv")
    out_report = outdir / (args.out_report or "transfers_report.csv")
    out_spacing = None if args.no_out_spacing else (outdir / (args.out_spacing or "clean_spacing.csv"))

    _headers, _desc, stats = wf_process_csv(
        input_csv=wf_csv,
        out_clean=out_clean,
        out_report=out_report,
        out_spacing=out_spacing,
        dry_run=args.dry_run,
        no_name_filter=args.no_name_filter,
    )

    created: List[Path] = []
    print(mt_timestamp_line("Generated (MT)"))
    print("✅ WF -> Clean completed")
    print(f"WF input: {wf_csv}")
    wf_print_snapshot(stats)

    if args.summary_pdf:
        pdf_path = Path(args.summary_pdf).expanduser()
        if not pdf_path.is_absolute():
            pdf_path = outdir / pdf_path.name
        wf_write_summary_pdf(pdf_path, wf_csv, stats)
        print(f"🧾 Summary PDF created: {pdf_path}")
        created.append(pdf_path)

    if args.dry_run:
        print("🧪 Dry run — stopping before finance outputs (no CSV written).")
        if args.open:
            _open_paths(_filter_created(created, (".pdf",)))
        if args.open_xlsx:
            _open_paths(_filter_created(created, (".xlsx",)))
        return created

    # track WF outputs written
    created.extend([out_clean, out_report])
    if out_spacing is not None:
        created.append(out_spacing)

    print("📌 Using cleaned file for finance_master ALL:")
    print(f"   {out_clean}")

    created.extend(run_all(out_clean))

    # SMART OPEN: only open what this run created
    if args.open:
        pdfs = _filter_created(created, (".pdf",))
        if pdfs:
            print(f"📂 Opening {len(pdfs)} PDF(s) created this run...")
        _open_paths(pdfs)

    if args.open_xlsx:
        xlsxs = _filter_created(created, (".xlsx",))
        if xlsxs:
            print(f"📂 Opening {len(xlsxs)} Excel file(s) created this run...")
        _open_paths(xlsxs)

    return created


# ============================================================
# CLI
# ============================================================

def main():
    p = argparse.ArgumentParser(description="Grand Finance Master: finance_master + wf_transfer_cleaner (one CLI).")
    p.add_argument("--in", dest="input_csv", default=DEFAULT_INPUT_CSV, help="Default input CSV for finance commands.")

    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("spacing", help="Fix inconsistent spacing in raw CSV (no grouping, no deletions).")
    s.add_argument("--out", default=DEFAULT_SPACING_OUT)

    q = sub.add_parser("quick", help="Print quick summary to console.")
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--sort", choices=["txns", "total"], default="txns")
    q.add_argument("--organized", action="store_true")

    qp = sub.add_parser("quick_pdf", help="Create a 1-page Quick Summary PDF.")
    qp.add_argument("--out", default=DEFAULT_PDF_QUICK_OUT)
    qp.add_argument("--limit", type=int, default=60)
    qp.add_argument("--sort", choices=["txns", "total"], default="txns")
    qp.add_argument("--organized", action="store_true")

    htl = sub.add_parser("exec_txns_desc", help="Executive summary sorted by txns (high → low).")
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

    cmp_ = sub.add_parser("compare_quick_pdf", help="Compare TWO CSV files (12m vs 18m) -> one PDF.")
    cmp_.add_argument("--in12", required=True)
    cmp_.add_argument("--in18", required=True)
    cmp_.add_argument("--out", default="expenses_quick_summary_comparison.pdf")
    cmp_.add_argument("--organized", action="store_true")
    cmp_.add_argument("--sort", choices=["delta_abs", "delta", "total12", "total18", "name"], default="delta_abs")
    cmp_.add_argument("--limit", type=int, default=120)

    wf = sub.add_parser("wf_clean", help="Wells Fargo transfer cleaner.")
    wf.add_argument("input_csv")
    wf.add_argument("--dry-run", action="store_true")
    wf.add_argument("--no-name-filter", action="store_true")
    wf.add_argument("--out-clean", default="clean.csv")
    wf.add_argument("--out-report", default="transfers_report.csv")
    wf.add_argument("--out-spacing", default="clean_spacing.csv")
    wf.add_argument("--no-out-spacing", action="store_true")
    wf.add_argument("--summary-pdf", default="")

    wta = sub.add_parser("wf_to_all", help="WF export -> wf_clean -> finance ALL on clean.csv")
    wta.add_argument("input_csv", nargs="?", default="")
    wta.add_argument("--latest", action="store_true")
    wta.add_argument(
        "--latest-pattern",
        default="*wf*.csv,*WF*.csv,*wells*fargo*.csv,*Wells*Fargo*.csv,*WELLS*FARGO*.csv,*fargo*.csv,*FARGO*.csv,*wells*.csv,*WELLS*.csv",
    )
    wta.add_argument("--latest-dirs", nargs="*", default=[])
    wta.add_argument("--latest-depth", type=int, default=2)

    wta.add_argument("--dry-run", action="store_true")
    wta.add_argument("--no-name-filter", action="store_true")
    wta.add_argument("--outdir", default="output/csv")
    wta.add_argument("--out-clean", default="clean.csv")
    wta.add_argument("--out-report", default="transfers_report.csv")
    wta.add_argument("--out-spacing", default="clean_spacing.csv")
    wta.add_argument("--no-out-spacing", action="store_true")
    wta.add_argument("--summary-pdf", default="")

    # ✅ THIS IS YOUR REQUESTED UPGRADE
    wta.add_argument("--open", action="store_true", help="Open PDFs created in THIS run (smart).")
    wta.add_argument("--open-xlsx", dest="open_xlsx", action="store_true", help="Open Excel files created in THIS run (smart).")

    args = p.parse_args()

    if args.cmd == "wf_clean":
        run_wf_clean(args)
        return

    if args.cmd == "wf_to_all":
        run_wf_to_all(args)
        return

    if args.cmd == "compare_quick_pdf":
        in12 = resolve_input_path(args.in12)
        in18 = resolve_input_path(args.in18)
        if not in12.exists():
            raise FileNotFoundError(f"12m CSV not found: {args.in12}")
        if not in18.exists():
            raise FileNotFoundError(f"18m CSV not found: {args.in18}")
        run_compare_quick_pdf(in12, in18, args.out, args.organized, args.sort, args.limit)
        return

    in_path = resolve_input_path(args.input_csv)
    if not in_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {args.input_csv}")

    if args.cmd == "spacing":
        run_spacing_fix(in_path, args.out)
    elif args.cmd == "quick":
        run_quick(in_path, args.limit, args.sort, args.organized)
    elif args.cmd == "quick_pdf":
        run_quick_pdf(in_path, args.out, args.limit, args.sort, args.organized)
    elif args.cmd == "exec_txns_desc":
        run_exec_txns_desc(in_path, args.out, args.limit, args.organized)
    elif args.cmd == "quick_pdf_18mo":
        run_quick_pdf_18mo(in_path, args.out, args.limit, args.sort, args.organized)
    elif args.cmd == "pipeline":
        run_pipeline(in_path, args.excel_detail_out, args.excel_summary_out, args.pdf_detail_out, args.pdf_summary_out, args.summary_sort)
    elif args.cmd == "pdf_families":
        run_pdf_families(in_path, args.out, args.zelle_block, args.sort)
    elif args.cmd == "excel_families":
        run_excel_families(in_path, args.out, args.zelle_block, args.sort)
    elif args.cmd == "organized_pdf":
        run_organized_pdf(in_path, args.out, args.top_total)
    elif args.cmd == "ready_to_print":
        run_ready_to_print(in_path, args.top_other)
    elif args.cmd == "all":
        run_all(in_path)


if __name__ == "__main__":
    main()

