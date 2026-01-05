#!/usr/bin/env python3
"""
Jan 05, 2026
Abinet Kenore
finance_master.py — DRY + Organized ✅

Input:
- Place this file AND your CSV in the same folder.
- Default CSV name: expenses.csv
- CSV headers expected (at least): Date, Description, Amount
  (Payee, Payment Method are used if present)

Installs:
  pip3 install openpyxl reportlab

Commands:
  python3 finance_master.py spacing
  python3 finance_master.py quick --limit 40
  python3 finance_master.py quick_pdf --limit 60
  python3 finance_master.py pipeline
  python3 finance_master.py pdf_families --sort total --zelle-block first
  python3 finance_master.py excel_families --sort txns --zelle-block last
  python3 finance_master.py organized_pdf --top-total 25 --top-txns 25
"""

import csv
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any


# -----------------------------
# Defaults / Config
# -----------------------------
DEFAULT_INPUT_CSV = "expenses.csv"

DEFAULT_SPACING_OUT = "expenses_raw_spacing_fixed.csv"

DEFAULT_EXCEL_DETAIL_OUT = "expenses_clean_grouped.xlsx"
DEFAULT_EXCEL_SUMMARY_OUT = "expenses_family_summary.xlsx"
DEFAULT_EXCEL_FAMILIES_OUT = "expenses_family_summary_sorted.xlsx"

DEFAULT_PDF_DETAIL_OUT = "expenses_grouped_families_detail.pdf"
DEFAULT_PDF_SUMMARY_OUT = "expenses_family_summary.pdf"
DEFAULT_PDF_FAMILIES_SORTED_OUT = "expenses_family_totals_sorted.pdf"

DEFAULT_PDF_QUICK_OUT = "expenses_quick_summary.pdf"
DEFAULT_PDF_ORGANIZED_OUT = "organized_report.pdf"

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


# -----------------------------
# Optional dependencies (nice errors)
# -----------------------------
def require_openpyxl():
    try:
        from openpyxl import Workbook  # noqa
        from openpyxl.styles import Font  # noqa
        return Workbook, Font
    except Exception:
        raise SystemExit("Missing dependency: openpyxl\nInstall with: pip3 install openpyxl\n")


def require_reportlab():
    try:
        from reportlab.lib.pagesizes import letter  # noqa
        from reportlab.lib.units import inch  # noqa
        from reportlab.lib import colors  # noqa
        from reportlab.lib.styles import getSampleStyleSheet  # noqa
        from reportlab.platypus import (  # noqa
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        )
        return (letter, inch, colors, getSampleStyleSheet,
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak)
    except Exception:
        raise SystemExit("Missing dependency: reportlab\nInstall with: pip3 install reportlab\n")


# -----------------------------
# Helpers
# -----------------------------
def normalize_spaces(text: str) -> str:
    return " ".join((text or "").split()).strip()


def fmt_money(n: float) -> str:
    return f"${n:,.2f}"


def parse_amount(value) -> float:
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0

    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()

    s = s.replace("$", "").replace(",", "")
    try:
        n = float(s)
        return -n if neg else n
    except ValueError:
        return 0.0


def parse_date(value: str):
    s = ("" if value is None else str(value)).strip()
    if not s:
        return None
    s = s.split()[0]
    if "T" in s:
        s = s.split("T")[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def normalize_payment_method(value: str) -> str:
    value = (value or "").strip()
    if value.upper().startswith(WF_CARD_PREFIX):
        suffix = value[len(WF_CARD_PREFIX):].strip()
        return f"{WF_CARD_ALIAS}{suffix}"
    return value


# -----------------------------
# Description cleaning (remove narration prefixes)
# -----------------------------
def clean_description(raw: str) -> str:
    d = normalize_spaces(raw)
    if not d:
        return ""

    # "PURCHASE AUTHORIZED ON 09/08 7-ELEVEN Aurora" -> "7-ELEVEN Aurora"
    m = re.match(r"^PURCHASE\s+AUTHORIZED\s+ON\s+\d{2}/\d{2}\s+(.*)$", d, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # "ATM WITHDRAWAL AUTHORIZED ON 01/15 ..." -> "ATM WITHDRAWAL ..."
    m = re.match(r"^ATM\s+WITHDRAWAL\s+AUTHORIZED\s+ON\s+\d{2}/\d{2}\s+(.*)$", d, flags=re.IGNORECASE)
    if m:
        return ("ATM WITHDRAWAL " + m.group(1).strip()).strip()

    if re.match(r"^DEPOSITED\s+OR\s+CASHED\s+CHECK", d, flags=re.IGNORECASE):
        return "DEPOSITED OR CASHED CHECK"

    return d


# -----------------------------
# Grouping rules (family keys)
# -----------------------------
def extract_zelle_person(desc_upper: str) -> str:
    d = normalize_spaces(desc_upper)
    if not d.startswith("ZELLE TO"):
        return "UNKNOWN"
    rest = d[len("ZELLE TO"):].strip()
    if " ON " in rest:
        person = rest.split(" ON ", 1)[0].strip()
    elif " REF " in rest:
        person = rest.split(" REF ", 1)[0].strip()
    else:
        person = " ".join(rest.split()[:3]).strip()
    return normalize_spaces(person) or "UNKNOWN"


def merchant_core(description: str) -> str:
    """Stable merchant family core (non-Zelle)."""
    d = normalize_spaces(description).upper()
    if not d:
        return "OTHER"

    # explicit families
    if d.startswith("AMAZON"):
        return "AMAZON"
    if d.startswith("7-ELEVEN"):
        return "7-ELEVEN"
    if d.startswith("COSTCO GAS"):
        return "COSTCO GAS"
    if d.startswith("COSTCO WHSE") or d.startswith("COSTCO WHOLESALE"):
        return "COSTCO WHSE"
    if d.startswith("WAL-MART") or d.startswith("WM SUPERCENTER"):
        return "WALMART"
    if d.startswith("KING SOOPERS"):
        return "KING SOOPERS"
    if d.startswith("SPROUTS"):
        return "SPROUTS"
    if d.startswith("WHOLEFDS") or d.startswith("WHOLE FOODS"):
        return "WHOLE FOODS"
    if d.startswith("COMCAST") or d.startswith("XFINITY"):
        return "COMCAST/XFINITY"
    if d.startswith("APPLE.COM/BILL"):
        return "APPLE.COM/BILL"
    if d.startswith("STATE FARM"):
        return "STATE FARM"
    if d.startswith("ATM WITHDRAWAL"):
        return "ATM WITHDRAWAL"
    if d.startswith("DEPT EDUCATION") or "STUDENT LN" in d:
        return "STUDENT LOAN"
    if d.startswith("PENNYMAC"):
        return "PENNYMAC"

    tokens = d.split()
    if not tokens:
        return "OTHER"
    if len(tokens) >= 2 and (tokens[1].isdigit() or re.fullmatch(r"#\d+", tokens[1] or "")):
        return tokens[0]
    return " ".join(tokens[:2]) if len(tokens) >= 2 else tokens[0]


def group_key(description: str) -> str:
    """Default grouping: ZELLE per person; else merchant_core."""
    d = normalize_spaces(description).upper()
    if not d:
        return "OTHER"
    if d.startswith("ZELLE TO"):
        return f"ZELLE - {extract_zelle_person(d)}"
    return merchant_core(d)


def group_key_organized(description: str) -> str:
    """Organized grouping: ALL ZELLE into one group; else merchant_core."""
    d = normalize_spaces(description).upper()
    if not d:
        return "OTHER"
    if d.startswith("ZELLE TO"):
        return "ZELLE"
    return merchant_core(d)


def is_zelle_group(name: str) -> bool:
    return name.upper().startswith("ZELLE - ")


# -----------------------------
# CSV IO
# -----------------------------
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


# -----------------------------
# Core cleaning
# -----------------------------
def clean_rows(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    - Fix Description narration + spacing
    - Remove rows with Description starting with ONLINE TRANSFER REF
    - Normalize Payment Method (WFACV...)
    """
    cleaned = []
    removed = 0

    for r in rows:
        r["Description"] = clean_description(r.get("Description"))
        if (r.get("Description") or "").upper().startswith(REMOVE_DESC_PREFIX.upper()):
            removed += 1
            continue
        r["Payment Method"] = normalize_payment_method(r.get("Payment Method"))
        cleaned.append(r)

    return cleaned, removed


# -----------------------------
# Sorting + Summaries (DRY)
# -----------------------------
def sort_rows_for_detail(rows: List[Dict[str, Any]], key_fn) -> List[Dict[str, Any]]:
    rows.sort(
        key=lambda r: (
            key_fn(r.get("Description") or ""),
            (r.get("Description") or "").upper(),
            parse_date(r.get("Date")) or datetime.max,
        )
    )
    return rows


def build_summary(rows: List[Dict[str, Any]], key_fn) -> Dict[str, Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        g = key_fn(r.get("Description") or "")
        amt = parse_amount(r.get("Amount"))
        if g not in summary:
            summary[g] = {"txns": 0, "total": 0.0}
        summary[g]["txns"] += 1
        summary[g]["total"] += amt
    return summary


def sort_summary_items(summary: Dict[str, Dict[str, Any]], sort_mode: str) -> List[Tuple[str, Dict[str, Any]]]:
    items = list(summary.items())
    if sort_mode == "total":
        return sorted(items, key=lambda kv: (-kv[1]["total"], -kv[1]["txns"], kv[0]))
    return sorted(items, key=lambda kv: (-kv[1]["txns"], kv[0], -kv[1]["total"]))


def apply_zelle_blocking(items_sorted: List[Tuple[str, Dict[str, Any]]], zelle_block: str):
    if zelle_block == "none":
        return items_sorted
    zelle_items = [kv for kv in items_sorted if is_zelle_group(kv[0])]
    other_items = [kv for kv in items_sorted if not is_zelle_group(kv[0])]
    return (zelle_items + other_items) if zelle_block == "first" else (other_items + zelle_items)


# -----------------------------
# Quick Summary text
# -----------------------------
def quick_summary_text(summary: dict, removed_count: int = 0, limit: int = 50, sort_mode: str = "txns") -> str:
    items_sorted = sort_summary_items(summary, sort_mode=sort_mode)[:max(0, int(limit))]
    parts = [f"Group: {name} Txns: {info['txns']} Total: {fmt_money(info['total'])}" for name, info in items_sorted]
    text = ", ".join(parts)
    if removed_count:
        text += f". Removed {removed_count} rows starting with '{REMOVE_DESC_PREFIX}'."
    return text


def print_quick_summary_from_csv(csv_path: Path, limit: int = 50, sort_mode: str = "txns", organized: bool = False):
    _headers, rows = load_csv_rows(csv_path)
    cleaned, removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    summary = build_summary(cleaned, key_fn=key_fn)
    print("✅ Quick Summary:")
    print(quick_summary_text(summary, removed_count=removed, limit=limit, sort_mode=sort_mode))


# -----------------------------
# Excel
# -----------------------------
def write_excel_detail_grouped(headers, rows, xlsx_path: Path, key_fn):
    Workbook, Font = require_openpyxl()
    BOLD = Font(bold=True)

    ensure_required(headers, ["Description", "Amount"])
    amount_idx = headers.index("Amount") + 1
    desc_idx = headers.index("Description") + 1

    wb = Workbook()
    ws = wb.active
    ws.title = "Grouped Detail"

    ws.append(headers)
    for c in range(1, len(headers) + 1):
        ws.cell(row=1, column=c).font = BOLD

    def append_total(group_name, total_value, txn_count):
        row = [""] * len(headers)
        row[desc_idx - 1] = f"TOTAL ({group_name}) — {txn_count} txns"
        row[amount_idx - 1] = total_value
        ws.append(row)
        rr = ws.max_row
        ws.cell(row=rr, column=desc_idx).font = BOLD
        ws.cell(row=rr, column=amount_idx).font = BOLD
        ws.append([""] * len(headers))  # separator row

    current_group = None
    group_total = 0.0
    group_count = 0

    for r in rows:
        g = key_fn(r.get("Description") or "")
        if current_group is not None and g != current_group:
            append_total(current_group, group_total, group_count)
            group_total = 0.0
            group_count = 0

        current_group = g
        group_total += parse_amount(r.get("Amount"))
        group_count += 1
        ws.append([r.get(h, "") for h in headers])

    if current_group is not None:
        append_total(current_group, group_total, group_count)

    for i in range(2, ws.max_row + 1):
        ws.cell(row=i, column=amount_idx).number_format = '"$"#,##0.00'

    wb.save(xlsx_path)


def write_excel_summary(summary: dict, xlsx_path: Path, sort_mode: str, zelle_block: str = "none"):
    Workbook, Font = require_openpyxl()
    BOLD = Font(bold=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Family Summary"

    ws.append(["Group", "Txns", "Total"])
    for c in range(1, 4):
        ws.cell(row=1, column=c).font = BOLD

    items_sorted = sort_summary_items(summary, sort_mode=sort_mode)
    items_sorted = apply_zelle_blocking(items_sorted, zelle_block=zelle_block)

    grand_txns = 0
    grand_total = 0.0

    for name, info in items_sorted:
        ws.append([name, info["txns"], info["total"]])
        grand_txns += info["txns"]
        grand_total += info["total"]

    ws.append(["GRAND TOTAL", grand_txns, grand_total])
    last = ws.max_row
    ws.cell(row=last, column=1).font = BOLD
    ws.cell(row=last, column=2).font = BOLD
    ws.cell(row=last, column=3).font = BOLD

    for r in range(2, ws.max_row + 1):
        ws.cell(row=r, column=3).number_format = '"$"#,##0.00'

    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 16

    wb.save(xlsx_path)


# -----------------------------
# PDF (DRY table helpers)
# -----------------------------
def pdf_doc(pdf_path: Path, margin_in: float = 0.75):
    (letter, inch, colors, getSampleStyleSheet,
     SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak) = require_reportlab()
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=margin_in * inch,
        rightMargin=margin_in * inch,
        topMargin=margin_in * inch,
        bottomMargin=margin_in * inch,
    )
    styles = getSampleStyleSheet()
    return (doc, styles, letter, inch, colors, Paragraph, Spacer, Table, TableStyle, PageBreak)


def style_summary_table(TableStyle, colors):
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ])


def style_detail_table(TableStyle, colors):
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ])


# -----------------------------
# PDF: Quick Summary (easy-to-read table)
# -----------------------------
def write_pdf_quick_summary(summary: dict, pdf_path: Path, removed_count: int = 0,
                            limit: int = 50, sort_mode: str = "txns"):
    doc, styles, _letter, inch, colors, Paragraph, Spacer, Table, TableStyle, _PageBreak = pdf_doc(pdf_path, margin_in=0.75)

    items_sorted = sort_summary_items(summary, sort_mode=sort_mode)[:max(0, int(limit))]
    title = "Quick Summary — Sorted by Total (High → Low)" if sort_mode == "total" else "Quick Summary — Sorted by Transactions (High → Low)"

    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.18 * inch))

    if removed_count:
        story.append(Paragraph(
            f"Removed rows starting with <b>{REMOVE_DESC_PREFIX}</b>: <b>{removed_count}</b>",
            styles["Normal"]
        ))
        story.append(Spacer(1, 0.12 * inch))

    table_data = [["Group", "Txns", "Total"]]
    for name, info in items_sorted:
        table_data.append([name, str(info["txns"]), fmt_money(info["total"])])

    tbl = Table(table_data, colWidths=[3.6 * inch, 0.8 * inch, 1.4 * inch], repeatRows=1)
    tbl.setStyle(style_summary_table(TableStyle, colors))
    story.append(tbl)

    doc.build(story)


# -----------------------------
# PDF: Summary (table)
# -----------------------------
def write_pdf_summary(summary: dict, pdf_path: Path, removed_count: int,
                      sort_mode: str, zelle_block: str):
    doc, styles, _letter, inch, colors, Paragraph, Spacer, Table, TableStyle, _PageBreak = pdf_doc(pdf_path, margin_in=0.75)

    items_sorted = sort_summary_items(summary, sort_mode=sort_mode)
    items_sorted = apply_zelle_blocking(items_sorted, zelle_block=zelle_block)

    title = "Expense Summary (Total high→low)" if sort_mode == "total" else "Expense Summary (Txns high→low)"

    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        f"Removed rows starting with <b>{REMOVE_DESC_PREFIX}</b>: <b>{removed_count}</b>",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    table_data = [["Group", "Txns", "Total"]]
    grand_txns = 0
    grand_total = 0.0

    for name, info in items_sorted:
        table_data.append([name, str(info["txns"]), fmt_money(info["total"])])
        grand_txns += info["txns"]
        grand_total += info["total"]

    table_data.append(["GRAND TOTAL", str(grand_txns), fmt_money(grand_total)])

    tbl = Table(table_data, colWidths=[3.8 * inch, 0.8 * inch, 1.4 * inch], repeatRows=1)
    st = style_summary_table(TableStyle, colors)
    st.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    st.add("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke)
    tbl.setStyle(st)

    story.append(tbl)
    doc.build(story)


# -----------------------------
# PDF: Detailed grouped report
# -----------------------------
def write_pdf_detail(rows, pdf_path: Path, removed_count: int, key_fn):
    doc, styles, _letter, inch, colors, Paragraph, Spacer, Table, TableStyle, PageBreak = pdf_doc(pdf_path, margin_in=0.6)

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        g = key_fn(r.get("Description") or "")
        groups.setdefault(g, []).append(r)

    story = []
    story.append(Paragraph("Expenses — Detailed Grouped Report", styles["Title"]))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(
        f"Removed rows starting with <b>{REMOVE_DESC_PREFIX}</b>: <b>{removed_count}</b>",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.18 * inch))

    grand_total = 0.0

    for gname in sorted(groups.keys()):
        grows = groups[gname]
        grows.sort(key=lambda r: (
            (r.get("Description") or "").upper(),
            parse_date(r.get("Date")) or datetime.max
        ))

        gtotal = sum(parse_amount(r.get("Amount")) for r in grows)
        grand_total += gtotal

        story.append(Paragraph(
            f"<b>Group:</b> {gname} &nbsp;&nbsp; <b>Txns:</b> {len(grows)} &nbsp;&nbsp; <b>Total:</b> {fmt_money(gtotal)}",
            styles["Heading2"]
        ))
        story.append(Spacer(1, 0.08 * inch))

        table_data = [["Date", "Description", "Payee", "Payment Method", "Amount"]]
        for r in grows:
            table_data.append([
                (r.get("Date") or "").strip(),
                (r.get("Description") or "").strip(),
                (r.get("Payee") or "").strip(),
                (r.get("Payment Method") or "").strip(),
                fmt_money(parse_amount(r.get("Amount"))),
            ])

        tbl = Table(table_data,
                    colWidths=[0.9 * inch, 3.1 * inch, 1.4 * inch, 1.6 * inch, 0.9 * inch],
                    repeatRows=1)
        tbl.setStyle(style_detail_table(TableStyle, colors))

        story.append(tbl)
        story.append(PageBreak())

    story.append(Paragraph("Grand Total", styles["Heading1"]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(f"<b>{fmt_money(grand_total)}</b>", styles["Normal"]))

    doc.build(story)


# -----------------------------
# PDF: Organized Report (Summary page + Details)
# -----------------------------
def write_pdf_organized_report(rows, pdf_path: Path, removed_count: int,
                              top_n_total: int = 25, top_n_txns: int = 25):
    doc, styles, _letter, inch, colors, Paragraph, Spacer, Table, TableStyle, PageBreak = pdf_doc(pdf_path, margin_in=0.6)

    # summary (organized grouping)
    summary = build_summary(rows, key_fn=group_key_organized)
    items = list(summary.items())
    by_total = sorted(items, key=lambda kv: (-kv[1]["total"], -kv[1]["txns"], kv[0]))[:max(0, int(top_n_total))]
    by_txns = sorted(items, key=lambda kv: (-kv[1]["txns"], -kv[1]["total"], kv[0]))[:max(0, int(top_n_txns))]

    grand_txns = sum(v["txns"] for v in summary.values())
    grand_total = sum(v["total"] for v in summary.values())

    story = []
    story.append(Paragraph("Organized Report (Grouped by Family)", styles["Title"]))
    story.append(Spacer(1, 0.10 * inch))
    story.append(Paragraph(
        f"Removed rows starting with <b>{REMOVE_DESC_PREFIX}</b>: <b>{removed_count}</b>",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.06 * inch))
    story.append(Paragraph(
        f"<b>Grand Totals:</b> {grand_txns} txns &nbsp;&nbsp; <b>{fmt_money(grand_total)}</b>",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.16 * inch))

    # Top by total
    story.append(Paragraph(f"Top {len(by_total)} Groups by Total (High → Low)", styles["Heading2"]))
    table_total = [["Group", "Txns", "Total"]]
    for name, info in by_total:
        table_total.append([name, str(info["txns"]), fmt_money(info["total"])])
    tbl_total = Table(table_total, colWidths=[3.6 * inch, 0.8 * inch, 1.4 * inch], repeatRows=1)
    tbl_total.setStyle(style_summary_table(TableStyle, colors))
    story.append(tbl_total)
    story.append(Spacer(1, 0.20 * inch))

    # Top by txns
    story.append(Paragraph(f"Top {len(by_txns)} Groups by Transactions (High → Low)", styles["Heading2"]))
    table_txns = [["Group", "Txns", "Total"]]
    for name, info in by_txns:
        table_txns.append([name, str(info["txns"]), fmt_money(info["total"])])
    tbl_txns = Table(table_txns, colWidths=[3.6 * inch, 0.8 * inch, 1.4 * inch], repeatRows=1)
    tbl_txns.setStyle(style_summary_table(TableStyle, colors))
    story.append(tbl_txns)

    story.append(PageBreak())

    # details (organized)
    write_detail_story = []

    # reuse the detailed generator logic but inside this one doc/story
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        g = group_key_organized(r.get("Description") or "")
        groups.setdefault(g, []).append(r)

    for gname in sorted(groups.keys()):
        grows = groups[gname]
        grows.sort(key=lambda r: (
            (r.get("Description") or "").upper(),
            parse_date(r.get("Date")) or datetime.max
        ))
        gtotal = sum(parse_amount(r.get("Amount")) for r in grows)

        story.append(Paragraph(
            f"<b>Group:</b> {gname} &nbsp;&nbsp; <b>Txns:</b> {len(grows)} &nbsp;&nbsp; <b>Total:</b> {fmt_money(gtotal)}",
            styles["Heading2"]
        ))
        story.append(Spacer(1, 0.08 * inch))

        table_data = [["Date", "Description", "Payee", "Payment Method", "Amount"]]
        for r in grows:
            table_data.append([
                (r.get("Date") or "").strip(),
                (r.get("Description") or "").strip(),
                (r.get("Payee") or "").strip(),
                (r.get("Payment Method") or "").strip(),
                fmt_money(parse_amount(r.get("Amount"))),
            ])

        tbl = Table(
            table_data,
            colWidths=[0.9 * inch, 3.1 * inch, 1.4 * inch, 1.6 * inch, 0.9 * inch],
            repeatRows=1
        )
        tbl.setStyle(style_detail_table(TableStyle, colors))
        story.append(tbl)
        story.append(PageBreak())

    doc.build(story)


# -----------------------------
# Runners
# -----------------------------
def run_spacing_fix(in_path: Path, out_name: str):
    headers, rows = load_csv_rows(in_path)
    if not headers:
        raise ValueError("No headers found in CSV.")
    fixed = []
    for r in rows:
        rr = {h: normalize_spaces(r.get(h, "")) for h in headers}
        fixed.append(rr)
    out_path = in_path.parent / out_name
    write_csv_rows(out_path, headers, fixed)
    print(f"✅ Spacing fixed: {out_path.name}")


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

    cleaned, removed = clean_rows(rows)
    detail_rows = sort_rows_for_detail(cleaned, key_fn=group_key)
    summary = build_summary(detail_rows, key_fn=group_key)

    write_excel_detail_grouped(headers, detail_rows, in_path.parent / excel_detail_out, key_fn=group_key)
    write_excel_summary(summary, in_path.parent / excel_summary_out, sort_mode=summary_sort, zelle_block="none")

    write_pdf_detail(detail_rows, in_path.parent / pdf_detail_out, removed_count=removed, key_fn=group_key)
    write_pdf_summary(summary, in_path.parent / pdf_summary_out,
                      removed_count=removed, sort_mode=summary_sort, zelle_block="none")

    print("✅ Pipeline complete:")
    print(f"   - {excel_detail_out}")
    print(f"   - {excel_summary_out}")
    print(f"   - {pdf_detail_out}")
    print(f"   - {pdf_summary_out}")


def run_pdf_families(in_path: Path, out_pdf: str, zelle_block: str, sort_mode: str):
    _headers, rows = load_csv_rows(in_path)
    cleaned, removed = clean_rows(rows)
    summary = build_summary(cleaned, key_fn=group_key)
    write_pdf_summary(summary, in_path.parent / out_pdf, removed_count=removed, sort_mode=sort_mode, zelle_block=zelle_block)
    print(f"✅ PDF created: {out_pdf}")


def run_excel_families(in_path: Path, out_xlsx: str, zelle_block: str, sort_mode: str):
    _headers, rows = load_csv_rows(in_path)
    cleaned, _removed = clean_rows(rows)
    summary = build_summary(cleaned, key_fn=group_key)
    write_excel_summary(summary, in_path.parent / out_xlsx, sort_mode=sort_mode, zelle_block=zelle_block)
    print(f"✅ Excel created: {out_xlsx}")


def run_quick_pdf(in_path: Path, out_pdf: str, limit: int = 50, sort_mode: str = "txns", organized: bool = False):
    _headers, rows = load_csv_rows(in_path)
    cleaned, removed = clean_rows(rows)
    key_fn = group_key_organized if organized else group_key
    summary = build_summary(cleaned, key_fn=key_fn)
    write_pdf_quick_summary(summary, in_path.parent / out_pdf, removed_count=removed, limit=limit, sort_mode=sort_mode)
    print(f"✅ Quick Summary PDF created: {out_pdf}")


def run_organized_report_pdf(in_path: Path, out_pdf: str, top_total: int = 25, top_txns: int = 25):
    _headers, rows = load_csv_rows(in_path)
    cleaned, removed = clean_rows(rows)
    write_pdf_organized_report(cleaned, in_path.parent / out_pdf, removed_count=removed, top_n_total=top_total, top_n_txns=top_txns)
    print(f"✅ Organized report PDF created: {out_pdf}")


# -----------------------------
# CLI
# -----------------------------
def main():
    p = argparse.ArgumentParser(description="Finance Master: clean + group + Excel/PDF outputs (DRY).")
    p.add_argument("--in", dest="input_csv", default=DEFAULT_INPUT_CSV,
                   help="Input CSV filename (in same folder).")

    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("spacing", help="Fix inconsistent spacing in raw CSV (no grouping, no deletions).")
    s.add_argument("--out", default=DEFAULT_SPACING_OUT, help="Output CSV filename.")

    pl = sub.add_parser("pipeline", help="Excel detail+summary + PDF detail+summary (default grouping).")
    pl.add_argument("--excel-detail-out", default=DEFAULT_EXCEL_DETAIL_OUT)
    pl.add_argument("--excel-summary-out", default=DEFAULT_EXCEL_SUMMARY_OUT)
    pl.add_argument("--pdf-detail-out", default=DEFAULT_PDF_DETAIL_OUT)
    pl.add_argument("--pdf-summary-out", default=DEFAULT_PDF_SUMMARY_OUT)
    pl.add_argument("--summary-sort", choices=["txns", "total"], default="txns")

    pf = sub.add_parser("pdf_families", help="PDF summary sorted by TOTAL/TXNS, with ZELLE block control.")
    pf.add_argument("--out", default=DEFAULT_PDF_FAMILIES_SORTED_OUT)
    pf.add_argument("--zelle-block", choices=["first", "last", "none"], default="first")
    pf.add_argument("--sort", choices=["total", "txns"], default="total")

    ef = sub.add_parser("excel_families", help="Excel summary sorted by TOTAL/TXNS, with ZELLE block control.")
    ef.add_argument("--out", default=DEFAULT_EXCEL_FAMILIES_OUT)
    ef.add_argument("--zelle-block", choices=["first", "last", "none"], default="first")
    ef.add_argument("--sort", choices=["total", "txns"], default="total")

    q = sub.add_parser("quick", help="Print quick summary text (default grouping).")
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--sort", choices=["txns", "total"], default="txns")
    q.add_argument("--organized", action="store_true", help="Use organized grouping (ALL ZELLE together).")

    qp = sub.add_parser("quick_pdf", help="Create a 1-page Quick Summary PDF (easy-to-read table).")
    qp.add_argument("--out", default=DEFAULT_PDF_QUICK_OUT)
    qp.add_argument("--limit", type=int, default=60)
    qp.add_argument("--sort", choices=["txns", "total"], default="txns")
    qp.add_argument("--organized", action="store_true", help="Use organized grouping (ALL ZELLE together).")

    op = sub.add_parser("organized_pdf", help="Create organized_report.pdf with summary page + detailed pages (ALL ZELLE together).")
    op.add_argument("--out", default=DEFAULT_PDF_ORGANIZED_OUT)
    op.add_argument("--top-total", type=int, default=25)
    op.add_argument("--top-txns", type=int, default=25)

    args = p.parse_args()

    base = Path(__file__).parent
    in_path = base / args.input_csv
    if not in_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {in_path}")

    if args.cmd == "spacing":
        run_spacing_fix(in_path, args.out)

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

    elif args.cmd == "quick":
        print_quick_summary_from_csv(in_path, limit=args.limit, sort_mode=args.sort, organized=args.organized)

    elif args.cmd == "quick_pdf":
        run_quick_pdf(in_path, out_pdf=args.out, limit=args.limit, sort_mode=args.sort, organized=args.organized)

    elif args.cmd == "organized_pdf":
        run_organized_report_pdf(in_path, out_pdf=args.out, top_total=args.top_total, top_txns=args.top_txns)


if __name__ == "__main__":
    main()
