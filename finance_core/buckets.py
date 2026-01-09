"""
finance_core.buckets
18-month executive bucket report.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple
from .parsing import parse_date
from .utils import fmt_money, mt_timestamp_line
from .pdf_reports import require_reportlab
from .summaries import build_summary, sort_summary_items

def _pdf_doc(pdf_path: Path, margin_in: float = 0.55):
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
    return (doc, styles, inch, colors, Paragraph, Spacer, Table, TableStyle)

def _style(TableStyle, colors):
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    ])

def filter_rows_by_date_range(rows: List[Dict[str, Any]], start: datetime, end: datetime) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = parse_date(r.get("Date"))
        if d and start <= d <= end:
            out.append(r)
    return out

def write_pdf_quick_summary_18mo(
    rows: List[Dict[str, Any]],
    pdf_path: Path,
    buckets: List[Tuple[str, datetime, datetime]],
    key_fn: Callable[[str], str],
    sort_mode: str = "total",
    limit: int = 15,
):
    doc, styles, inch, colors, Paragraph, Spacer, Table, TableStyle = _pdf_doc(pdf_path, margin_in=0.55)

    story = []
    story.append(Paragraph("Quick Executive Summary — 18-Month Buckets", styles["Title"]))
    story.append(Spacer(1, 0.06 * inch))
    story.append(Paragraph(mt_timestamp_line("Generated (MT)"), styles["Normal"]))
    story.append(Spacer(1, 0.10 * inch))

    for (label, start, end) in buckets:
        bucket_rows = filter_rows_by_date_range(rows, start, end)
        story.append(Paragraph(f"<b>{label}</b>", styles["Heading3"]))
        story.append(Spacer(1, 0.02 * inch))

        if not bucket_rows:
            story.append(Paragraph("No transactions found in this range.", styles["Normal"]))
            story.append(Spacer(1, 0.10 * inch))
            continue

        summary = build_summary(bucket_rows, key_fn=key_fn)
        items = sort_summary_items(summary, sort_mode=sort_mode)[:max(0, int(limit))]

        bucket_txns = sum(info["txns"] for info in summary.values())
        bucket_total = sum(info["total"] for info in summary.values())

        story.append(Paragraph(f"Txns: <b>{bucket_txns}</b> &nbsp;&nbsp; Total: <b>{fmt_money(bucket_total)}</b>", styles["Normal"]))
        story.append(Spacer(1, 0.03 * inch))

        table_data = [["Group", "Txns", "Total"]]
        for name, info in items:
            table_data.append([name, str(info["txns"]), fmt_money(info["total"])])

        tbl = Table(table_data, colWidths=[3.15 * inch, 0.65 * inch, 1.25 * inch], repeatRows=1)
        tbl.setStyle(_style(TableStyle, colors))
        story.append(tbl)
        story.append(Spacer(1, 0.10 * inch))

    doc.build(story)
