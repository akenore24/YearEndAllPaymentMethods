"""
finance_core.pdf_reports
PDF creation (reportlab).
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, List, Tuple
from .utils import fmt_money, mt_timestamp_line
from .parsing import parse_amount, parse_date

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

def _pdf_doc(pdf_path: Path, margin_in: float = 0.75):
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

def _style_summary_table(TableStyle, colors):
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ])

def _style_detail_table(TableStyle, colors):
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ])

def write_pdf_quick_summary(items_sorted: List[Tuple[str, Dict[str, Any]]], pdf_path: Path,
                           sort_mode: str, limit: int = 50,
                           title_override: str | None = None) -> None:
    doc, styles, _letter, inch, colors, Paragraph, Spacer, Table, TableStyle, _PageBreak = _pdf_doc(pdf_path, margin_in=0.75)

    items_sorted = items_sorted[:max(0, int(limit))]
    title = title_override or ("Quick Summary — Sorted by Total (High → Low)" if sort_mode == "total"
                              else "Quick Summary — Sorted by Transactions (High → Low)")

    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(mt_timestamp_line("Generated (MT)"), styles["Normal"]))
    story.append(Spacer(1, 0.12 * inch))

    table_data = [["Group", "Txns", "Total"]]
    for name, info in items_sorted:
        table_data.append([name, str(info["txns"]), fmt_money(info["total"])])

    tbl = Table(table_data, colWidths=[3.6 * inch, 0.8 * inch, 1.4 * inch], repeatRows=1)
    tbl.setStyle(_style_summary_table(TableStyle, colors))
    story.append(tbl)

    doc.build(story)

def write_pdf_summary(items_sorted: List[Tuple[str, Dict[str, Any]]], pdf_path: Path, title: str) -> None:
    doc, styles, _letter, inch, colors, Paragraph, Spacer, Table, TableStyle, _PageBreak = _pdf_doc(pdf_path, margin_in=0.75)

    story = []
    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(mt_timestamp_line("Generated (MT)"), styles["Normal"]))
    story.append(Spacer(1, 0.18 * inch))

    table_data = [["Group", "Txns", "Total"]]
    gtx, gtot = 0, 0.0
    for name, info in items_sorted:
        table_data.append([name, str(info["txns"]), fmt_money(info["total"])])
        gtx += info["txns"]
        gtot += info["total"]
    table_data.append(["GRAND TOTAL", str(gtx), fmt_money(gtot)])

    tbl = Table(table_data, colWidths=[3.8 * inch, 0.8 * inch, 1.4 * inch], repeatRows=1)
    st = _style_summary_table(TableStyle, colors)
    st.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    st.add("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke)
    tbl.setStyle(st)

    story.append(tbl)
    doc.build(story)

def write_pdf_detail(rows: List[Dict[str, Any]], pdf_path: Path, key_fn: Callable[[str], str]) -> None:
    doc, styles, _letter, inch, colors, Paragraph, Spacer, Table, TableStyle, PageBreak = _pdf_doc(pdf_path, margin_in=0.6)

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        g = key_fn(r.get("Description") or "")
        groups.setdefault(g, []).append(r)

    story = []
    story.append(Paragraph("Expenses — Detailed Grouped Report", styles["Title"]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(mt_timestamp_line("Generated (MT)"), styles["Normal"]))
    story.append(Spacer(1, 0.18 * inch))

    for gname in sorted(groups.keys()):
        grows = groups[gname]
        grows.sort(key=lambda r: ((r.get("Description") or "").upper(), parse_date(r.get("Date")) or datetime.max))
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

        tbl = Table(table_data,
                    colWidths=[0.9 * inch, 3.1 * inch, 1.4 * inch, 1.6 * inch, 0.9 * inch],
                    repeatRows=1)
        tbl.setStyle(_style_detail_table(TableStyle, colors))
        story.append(tbl)
        story.append(PageBreak())

    doc.build(story)

def write_ready_to_print_pdf(
    families_items: List[Tuple[str, Dict[str, Any]]],
    zelle_people_items: List[Tuple[str, Dict[str, Any]]],
    pdf_path: Path,
) -> None:
    doc, styles, _letter, inch, colors, Paragraph, Spacer, Table, TableStyle, PageBreak = _pdf_doc(pdf_path, margin_in=0.75)

    def table_from(items):
        data = [["Group", "Txns", "Total"]]
        gtx, gtot = 0, 0.0
        for name, info in items:
            data.append([name, str(info["txns"]), fmt_money(info["total"])])
            gtx += info["txns"]
            gtot += info["total"]
        data.append(["GRAND TOTAL", str(gtx), fmt_money(gtot)])
        tbl = Table(data, colWidths=[3.8 * inch, 0.8 * inch, 1.4 * inch], repeatRows=1)
        st = _style_summary_table(TableStyle, colors)
        st.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
        st.add("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke)
        tbl.setStyle(st)
        return tbl

    story = []
    story.append(Paragraph("Ready to Print — Expense Summary", styles["Title"]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(mt_timestamp_line("Generated (MT)"), styles["Normal"]))
    story.append(Spacer(1, 0.18 * inch))

    story.append(Paragraph("Families Summary", styles["Heading2"]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(table_from(families_items))

    story.append(PageBreak())
    story.append(Paragraph("Zelle Transfers by Person", styles["Heading2"]))
    story.append(Spacer(1, 0.08 * inch))
    if zelle_people_items:
        story.append(table_from(zelle_people_items))
    else:
        story.append(Paragraph("No Zelle transfers found.", styles["Normal"]))

    doc.build(story)
