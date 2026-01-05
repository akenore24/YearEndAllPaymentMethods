#!/usr/bin/env python3
"""
family_totals_pdf_sorted.py

Applies the same grouping procedure to ALL transactions:
- Fix spacing
- Strip bank narration prefixes (PURCHASE AUTHORIZED ON MM/DD ...)
- Build a stable family key so variations match the same group
- ZELLE is grouped by person (ZELLE - NAME)
- Output a PDF summary sorted by TOTAL (high -> low)
- Optionally keep ALL ZELLE groups together as one block

Input (same folder):
  expenses.csv  (or change INPUT_CSV below)

Output:
  expenses_family_totals_sorted.pdf
"""

import csv
import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


# -----------------------------
# Config
# -----------------------------
INPUT_CSV = "expenses.csv"
OUTPUT_PDF = "expenses_family_totals_sorted.pdf"

REMOVE_DESC_PREFIX = "ONLINE TRANSFER REF"

# Put ZELLE block together?
ZELLE_BLOCK_FIRST = True  # set False to put ZELLE block last


# -----------------------------
# Helpers
# -----------------------------
def normalize_spaces(text: str) -> str:
    return " ".join((text or "").split()).strip()


def parse_amount(value) -> float:
    """Handles: '$1,234.56', '1234.56', '(123.45)'"""
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


def fmt_money(n: float) -> str:
    return f"${n:,.2f}"


# -----------------------------
# Step 1: Clean description (strip narration prefixes)
# -----------------------------
def clean_description(raw: str) -> str:
    """
    Normalize spacing + remove common narration prefixes so the merchant portion
    is consistent and can match other rows.

    Examples:
      "PURCHASE AUTHORIZED ON 09/08 7-ELEVEN Aurora CO" -> "7-ELEVEN Aurora CO"
      "PURCHASE AUTHORIZED ON 03/28 COSTCO GAS #1652 DENVER" -> "COSTCO GAS #1652 DENVER"
    """
    d = normalize_spaces(raw)
    if not d:
        return ""

    # PURCHASE AUTHORIZED ON MM/DD <merchant...>
    m = re.match(r"^PURCHASE\s+AUTHORIZED\s+ON\s+\d{2}/\d{2}\s+(.*)$", d, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # ATM WITHDRAWAL AUTHORIZED ON MM/DD <location...>
    m = re.match(r"^ATM\s+WITHDRAWAL\s+AUTHORIZED\s+ON\s+\d{2}/\d{2}\s+(.*)$", d, flags=re.IGNORECASE)
    if m:
        return ("ATM WITHDRAWAL " + m.group(1).strip()).strip()

    # Deposited/cashed check noise standardization
    if re.match(r"^DEPOSITED\s+OR\s+CASHED\s+CHECK", d, flags=re.IGNORECASE):
        return "DEPOSITED OR CASHED CHECK"

    return d


# -----------------------------
# Step 2: ZELLE parsing
# -----------------------------
def extract_zelle_person(desc_upper: str) -> str:
    """
    Extract Zelle recipient from:
      "ZELLE TO ABAGEZ DANIEL ON 04/30 REF #..."
    """
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

    person = normalize_spaces(person)
    return person if person else "UNKNOWN"


# -----------------------------
# Step 3: Merchant core extraction (applies procedure to ALL)
# -----------------------------
def merchant_core(description: str) -> str:
    """
    Create a stable family/group label from a cleaned description.

    Rule:
    - Use explicit family rules where helpful
    - Otherwise fallback to a consistent "core" (first 1-2 tokens)
    """
    d = normalize_spaces(description).upper()
    if not d:
        return "OTHER"

    # Explicit families (keep expanding as you like)
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
    if d.startswith("GOOGLE *GOOGLE ONE") or d.startswith("GOOGLE"):
        return "GOOGLE"
    if d.startswith("STATE FARM"):
        return "STATE FARM"
    if d.startswith("ATM WITHDRAWAL"):
        return "ATM WITHDRAWAL"
    if d.startswith("DEPT EDUCATION") or "STUDENT LN" in d:
        return "STUDENT LOAN"

    # Generic fallback core (works for ALL remaining merchants)
    tokens = d.split()
    if not tokens:
        return "OTHER"

    # If second token is store number/code, group by first token
    if len(tokens) >= 2 and (tokens[1].isdigit() or re.fullmatch(r"#\d+", tokens[1])):
        return tokens[0]

    # Default: first two tokens (BEST BUY, CITY OF, ADVANCE AUTO, etc.)
    return " ".join(tokens[:2]) if len(tokens) >= 2 else tokens[0]


def family_key(cleaned_description: str) -> str:
    """
    Final family key applied to ALL rows:
    - ZELLE -> ZELLE - PERSON
    - otherwise -> merchant_core
    """
    d = normalize_spaces(cleaned_description).upper()
    if d.startswith("ZELLE TO"):
        return f"ZELLE - {extract_zelle_person(d)}"
    return merchant_core(d)


def is_zelle_group(group_name: str) -> bool:
    return group_name.upper().startswith("ZELLE - ")


# -----------------------------
# Load + Summarize + PDF
# -----------------------------
def load_rows(csv_path: Path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize(rows):
    """
    Applies procedure to ALL rows and returns:
      summary[group] = {"txns": int, "total": float}
      removed_count = int
    """
    summary = {}
    removed_count = 0

    for r in rows:
        desc_raw = r.get("Description", "")
        desc = clean_description(desc_raw)

        # Remove ONLINE TRANSFER REF... rows (your rule)
        if desc.upper().startswith(REMOVE_DESC_PREFIX.upper()):
            removed_count += 1
            continue

        group = family_key(desc)
        amt = parse_amount(r.get("Amount"))

        if group not in summary:
            summary[group] = {"txns": 0, "total": 0.0}
        summary[group]["txns"] += 1
        summary[group]["total"] += amt

    return summary, removed_count


def build_pdf(pdf_path: Path, summary: dict, removed_count: int):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    story = []
    story.append(Paragraph("Family Totals (Total high→low, same procedure applied to all)", styles["Title"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        f"Removed rows starting with <b>{REMOVE_DESC_PREFIX}</b>: <b>{removed_count}</b>",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    items = list(summary.items())

    # Sorting:
    # 1) ZELLE block together (optional)
    # 2) Total high -> low
    # 3) Name A -> Z ties
    if ZELLE_BLOCK_FIRST:
        zelle_rank = lambda name: 0 if is_zelle_group(name) else 1
    else:
        zelle_rank = lambda name: 1 if is_zelle_group(name) else 0

    items_sorted = sorted(
        items,
        key=lambda kv: (
            zelle_rank(kv[0]),
            -kv[1]["total"],
            kv[0],
        )
    )

    table_data = [["Family / Group", "Txns", "Total"]]
    grand_txns = 0
    grand_total = 0.0

    for name, info in items_sorted:
        table_data.append([name, str(info["txns"]), fmt_money(info["total"])])
        grand_txns += info["txns"]
        grand_total += info["total"]

    table_data.append(["GRAND TOTAL", str(grand_txns), fmt_money(grand_total)])

    tbl = Table(table_data, colWidths=[3.8 * inch, 0.8 * inch, 1.4 * inch], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
    ]))

    story.append(tbl)
    doc.build(story)


def main():
    base = Path(__file__).parent
    in_path = base / INPUT_CSV
    out_path = base / OUTPUT_PDF

    if not in_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {in_path}")

    rows = load_rows(in_path)
    summary, removed = summarize(rows)
    build_pdf(out_path, summary, removed)

    print("✅ PDF created")
    print(f"📥 Input : {in_path.name}")
    print(f"📤 Output: {out_path.name}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
family_totals_pdf_sorted.py

Goal:
- Group transactions by "family" (merchant group)
- Keep all ZELLE groups together (next to each other)
- Sort families by TOTAL (high -> low)
- Output a PDF summary

Input (same folder):
  expenses.csv   (or expenses_raw_spacing_fixed.csv if you prefer)

Output (same folder):
  expenses_family_totals_sorted.pdf
"""

import csv
import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


# -----------------------------
# Config
# -----------------------------
INPUT_CSV = "expenses.csv"  # change to "expenses_raw_spacing_fixed.csv" if you want
OUTPUT_PDF = "expenses_family_totals_sorted.pdf"

REMOVE_DESC_PREFIX = "ONLINE TRANSFER REF"


# -----------------------------
# Helpers
# -----------------------------
def normalize_spaces(text: str) -> str:
    return " ".join((text or "").split()).strip()


def parse_amount(value) -> float:
    """Handles: '$1,234.56', '1234.56', '(123.45)'"""
    if value is None:
        return 0.0
    s = str(value).strip()
    if not s:
        return 0.0

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()

    s = s.replace("$", "").replace(",", "")
    try:
        n = float(s)
        return -n if negative else n
    except ValueError:
        return 0.0


def fmt_money(n: float) -> str:
    return f"${n:,.2f}"


def clean_description(raw: str) -> str:
    """
    Fix inconsistent spacing + strip common bank narration prefixes so the real merchant remains.
    """
    d = normalize_spaces(raw)
    if not d:
        return ""

    # PURCHASE AUTHORIZED ON MM/DD <merchant...>
    m = re.match(r"^PURCHASE\s+AUTHORIZED\s+ON\s+\d{2}/\d{2}\s+(.*)$", d, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # ATM WITHDRAWAL AUTHORIZED ON MM/DD <location...>
    m = re.match(r"^ATM\s+WITHDRAWAL\s+AUTHORIZED\s+ON\s+\d{2}/\d{2}\s+(.*)$", d, flags=re.IGNORECASE)
    if m:
        return ("ATM WITHDRAWAL " + m.group(1).strip()).strip()

    return d


def extract_zelle_person(desc_upper: str) -> str:
    """
    Extract Zelle recipient from:
      "ZELLE TO ABAGEZ DANIEL ON 04/30 REF #..."
    """
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

    person = normalize_spaces(person)
    return person if person else "UNKNOWN"


def merchant_core(description: str) -> str:
    """
    Build a stable family key so variations still match.
    """
    d = normalize_spaces(description).upper()
    if not d:
        return "OTHER"

    # explicit families (extend anytime)
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
    if d.startswith("ATM WITHDRAWAL"):
        return "ATM WITHDRAWAL"

    # fallback: first two tokens
    tokens = d.split()
    if not tokens:
        return "OTHER"

    if len(tokens) >= 2 and (tokens[1].isdigit() or re.fullmatch(r"#\d+", tokens[1] or "")):
        return tokens[0]

    return " ".join(tokens[:2]) if len(tokens) >= 2 else tokens[0]


def family_key(description: str) -> str:
    """
    Family grouping:
    - ZELLE stays separated per person for detail, but we can also keep them together by sorting.
    """
    d = normalize_spaces(description).upper()
    if d.startswith("ZELLE TO"):
        return f"ZELLE - {extract_zelle_person(d)}"
    return merchant_core(d)


def is_zelle_group(group_name: str) -> bool:
    return group_name.upper().startswith("ZELLE - ")


# -----------------------------
# Build summary + PDF
# -----------------------------
def load_rows(csv_path: Path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize(rows):
    """
    Returns:
      summary: dict[group] = {"txns": int, "total": float}
      removed_count: int
    """
    summary = {}
    removed_count = 0

    for r in rows:
        desc = clean_description(r.get("Description"))
        if desc.upper().startswith(REMOVE_DESC_PREFIX.upper()):
            removed_count += 1
            continue

        g = family_key(desc)
        amt = parse_amount(r.get("Amount"))

        if g not in summary:
            summary[g] = {"txns": 0, "total": 0.0}

        summary[g]["txns"] += 1
        summary[g]["total"] += amt

    return summary, removed_count


def build_pdf(pdf_path: Path, summary: dict, removed_count: int):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    story = []
    story.append(Paragraph("Family Totals (Zelle together, Total high→low)", styles["Title"]))
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        f"Removed rows starting with <b>{REMOVE_DESC_PREFIX}</b>: <b>{removed_count}</b>",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ✅ Sort rule:
    # 1) Put ALL ZELLE groups together (as a block)
    # 2) Within each block: Total high→low
    # 3) Tie-breaker: Name A→Z
    items = list(summary.items())
    items_sorted = sorted(
        items,
        key=lambda kv: (
            0 if is_zelle_group(kv[0]) else 1,      # ZELLE block first (change to 1 if you want Zelle last)
            -kv[1]["total"],                        # total high -> low
            kv[0]                                   # name A -> Z ties
        )
    )

    table_data = [["Family / Group", "Txns", "Total"]]
    grand_txns = 0
    grand_total = 0.0

    for name, info in items_sorted:
        table_data.append([name, str(info["txns"]), fmt_money(info["total"])])
        grand_txns += info["txns"]
        grand_total += info["total"]

    table_data.append(["GRAND TOTAL", str(grand_txns), fmt_money(grand_total)])

    tbl = Table(table_data, colWidths=[3.8 * inch, 0.8 * inch, 1.4 * inch], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
    ]))

    story.append(tbl)
    doc.build(story)


def main():
    base = Path(__file__).parent
    in_path = base / INPUT_CSV
    out_path = base / OUTPUT_PDF

    if not in_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {in_path}")

    rows = load_rows(in_path)
    summary, removed_count = summarize(rows)
    build_pdf(out_path, summary, removed_count)

    print("✅ PDF created")
    print(f"📥 Input : {in_path.name}")
    print(f"📤 Output: {out_path.name}")


if __name__ == "__main__":
    main()


