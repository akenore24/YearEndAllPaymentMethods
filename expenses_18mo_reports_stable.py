#!/usr/bin/env python3
"""expenses_18mo_reports_v7.py

What this script does
- Reads your 18-month expenses CSV with columns:
  Master Category, Subcategory, Date, Location, Payee, Description, Payment Method, Amount
- Generates ready-to-print PDFs (tables)
- Uses your "Deduplicated, Simplified Description Patterns (Organized)" as the authoritative pattern groups
- NEW: Auto-flags UNCATEGORIZED descriptions (no pattern match)
  • Writes CSV of uncategorized rows
  • Writes a PDF summary (top uncategorized descriptions ranked by Txns then ABS)

Output structure (auto-created)
  output/
    reports/
      ...pdf files...
      uncategorized_rows.csv

Commands
  python3 expenses_18mo_reports_v7.py expenses.csv ready_to_print
  python3 expenses_18mo_reports_v7.py expenses.csv exec_summary
  python3 expenses_18mo_reports_v7.py expenses.csv mastercat
  python3 expenses_18mo_reports_v7.py expenses.csv patterns
  python3 expenses_18mo_reports_v7.py expenses.csv payees
  python3 expenses_18mo_reports_v7.py expenses.csv uncategorized
  python3 expenses_18mo_reports_v7.py expenses.csv all

Notes on totals
- Total (NET): sum of Amount (positives + negatives)
- Total (ABS): sum of abs(Amount) (treats refunds/credits as spending magnitude)
"""

import argparse
import os
import re
from pathlib import Path
from datetime import datetime

import pandas as pd
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet


# -----------------------
# Authoritative simplified patterns (user-confirmed)
# -----------------------
# IMPORTANT: Everything is uppercased during normalization.
# IMPORTANT: WHOLE FOOD / WHOLEFDS is treated as FOOD (Category 7) per your direction.
SIMPLIFIED_PATTERNS = {
    "1) GAS / AUTO / TRANSPORTATION": [
        "COSTCO GAS",
        "SHELL OIL",
        "CONOCO - SEI",
        "CONOCO",
        "MURPHY",
        "PHILLIPS 66 - GOOD 2 GO",
        "PHILLIPS 66",
        "GOOD 2 GO",
        "FIRESTONE",
        "JIFFY LUBE",
        "VIOC",
        "ADVANCE AUTO PARTS",
        "ADVANCE AUTO",
        "CO DRIVER SERVI EMV",
        "CO MOTOR VEH SERV EMV",
        "LN*DENVER CO DMV KIOSK",
        "DEN PUBLIC PARKING",
        "PUBLIC WORKS-PRKG METR",
        "DU - PARKING MOBILE APP",
        "E 470 EXPRESS TOLLS",
        "E 470",
        "LYFT",
        # car wash / auto service (shows up like "COBBLESTONE 90")
        "COBBLESTONE",
        # insurance that appears in auto context
        "STATE FARM",
        "AIR CARE COLORADO STAPLETON",
    ],
    "2) CABLE / UTILITIES / PHONE": [
        "COMCAST-XFINITY CABLE SVCS",
        "COMCAST CABLE",
        "COMCAST",
        "XCEL ENERGY-PSCO XCELENERGY",
        "XCEL",  # alias -> canonicalized in reports
        "EUNIFYPAY PAINTED P",
        "USPS PO",
        "XFINITY MOBILE",
        "RAZA GLOBAL INC",
        "VZWRLSS*PRPAY AUTOPAY",
        "IDT BOSS INTL CALLING",
        "GOOGLE *GOOGLE ONE",
    ],
    "3) HOUSING / RENT / HOME-RELATED": [
        "THE COLLIER COMPANIES",
        "PRIMELENDING ACH BORPMT",
        "PRIMELENDING",
        "PRMG WEB PAY",
        "PENNYMAC CASH",
        "WT FED",
        "APPRAISALFEE-TRIPOINTE",
        "WIRE TRANS SVC CHARGE",
        "RICH AMER HOMES OF",
        "AFW-AURORA",
        "THE HOME DEPOT",
    ],
    "4) ATM / CASH": [
        "ATM WITHDRAWAL",
        "WELLS FARGO ATM",
        "ATM",
        "RAMAD PAY",
        "CASH BACK REDEMPTION",
        "ETHIOPIAN EVANGE",
    ],
    "5) CITY / GOVERNMENT": [
        "CITY OF AURORA",
        "DENVER COUNTY MOTOR VEHICLE",
    ],
    "6) APPS / SUBSCRIPTIONS / ONLINE SERVICES": [
        "APPLE.COM/BILL",
        "COURSERA.ORG",
        "COURSRA",
        "UDEMY",
        "DEPT EDUCATION STUDENT LN",
        "NAME-CHEAP.COM",
        "NAME-CHEAP",
        "JOBTESTPREP",
    ],
    "7) FOOD (FAST FOOD / RESTAURANTS)": [
        "LITTLE CAESARS",
        "PANDA EXPRESS",
        "CHICK-FIL-A",
        "DOMINO'S",
        "DOMINO",  # alias -> canonicalized in reports
        "CHIPOTLE",
        "LUCY COFFEE",
        "ALL IN ONE CONVENIENCE",
        "ALL IN ONE",  # alias -> canonicalized in reports
        "7-ELEVEN",
        "CANTEEN",
        "RAISING CANES",
        "DUNKIN",
        "FIVE GUYS",
        "COCA COLA",
        "APPLEBEES",
        "OUTBACK",
        "TACOS DON JOSE",
        "EL POLLOTE MEXICAN RESTAU",
        "TOTALLY TEA",
        "HOPDODDY",
        "NILE ETHIOPIAN RESTAURANT",
        "WINGSTOP",
        "COLDSTONE",
        "URBAN KITCHEN",
        # USER REQUEST: WHOLE FOOD goes to category 7
        "WHOLE FOOD",
        "WHOLEFDS",
    ],
    "8) GROCERIES / MARKETS": [
        "COSTCO WHSE",
        "WAL-MART",
        "WM SUPERCENTER",
        "KING SOOPERS",
        # appears truncated in some bank exports (e.g., "KING SOOP 18605 E. 48T")
        "KING SOOP",
        "SAVE-A-LOT",
        "SPROUTS FARMERS MAR",
        # NOTE: Whole Foods moved to Food per your direction
        "PIASSA ETHIO MART",
        "HARAR MARKET",
        "SHEGER INTERNATIONAL MARK",
        # sometimes truncated (e.g., "SHEGER INTERNATIONAL MAR")
        "SHEGER INTERNATIONAL MAR",  # alias -> canonicalized in reports
        "SHEBELLE MARKET",
        "MEGENAGNA GROCERY",
    ],
    "9) HEALTH": [
        "DH EPIC HOSP & CLINIC",
        "WALGREENS STORE",
        "DRIVER'S CHOICE",
    ],
    "10) SHOPPING / RETAIL": [
        "TARGET",
        "AURORA MARKET",
        "ROSS STORE",
        "KOHL'S",
        "SWA",
        "JCPENNEY",
        "DRY CLEAN USA",
        "SPC",
        "AMAZON MKTPL",
        "AMZN MKTP US",
        "GOODWILL",
        "BEST BUY",
        "APPLE STORE",
        "MENS WEARHOUSE",
        "OLD NAVY",
        "FAMOUS FOOTWEAR",
        "EXPRESS",
        "NASRI FASHION STORE",
        "GEN X",
        "IDEAS ELECTRONICS",
    ],
    "11) CHECKS / PAYMENTS": [
        "CHECK",
        "DEPOSITED OR CASHED CHECK",
        "MY DEALS CASH BACK",
    ],
    "12) CREDIT CARD / INTERNAL TRANSFERS (NON-EXPENSE)": [
        "ONLINE TRANSFER TO WF ACTIVE CASH VISA",
        "ONLINE TRANSFER TO WF REFLECT VISA",
        "ONLINE TRANSFER TO WAY2SAVE SAVINGS",
        "ONLINE TRANSFER TO EVERYDAY CHECKING",
    ],
    "13) ZELLE (OUTGOING TRANSFERS)": [
        "ZELLE",
    ],
}

# Some patterns are short aliases that appear as substrings of their canonical form.
# We canonicalize them so reports don't show duplicate rows with the same totals.
PATTERN_CANONICAL = {
    "XCEL": "XCEL ENERGY-PSCO XCELENERGY",
    "DOMINO": "DOMINO'S",
    "ALL IN ONE": "ALL IN ONE CONVENIENCE",
    "SHEGER INTERNATIONAL MAR": "SHEGER INTERNATIONAL MARK",
    "ADVANCE AUTO": "ADVANCE AUTO PARTS",
    "E 470": "E 470 EXPRESS TOLLS",
    "KING SOOP": "KING SOOPERS",
    "COMCAST": "COMCAST-XFINITY",
    "COMCAST CABLE": "COMCAST-XFINITY",
    "COMCAST-XFINITY CABLE SVCS": "COMCAST-XFINITY",
    "WM SUPERCENTER": "WAL-MART",
}

EXPECTED_COLS = [
    "Master Category",
    "Subcategory",
    "Date",
    "Location",
    "Payee",
    "Description",
    "Payment Method",
    "Amount",
]


# -----------------------
# Output dirs
# -----------------------

def ensure_reports_dir(base_outdir: str = "output") -> Path:
    reports_dir = Path(base_outdir) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


# -----------------------
# Helpers
# -----------------------

def currency(x: float) -> str:
    return f"${x:,.2f}"


def money(x) -> str:
    """Format number as USD with 2 decimals. Accepts None/NaN."""
    try:
        if x is None:
            return "$0.00"
        if isinstance(x, float) and (x != x):
            return "$0.00"
        val = float(x)
    except Exception:
        return "$0.00"
    sign = "-" if val < 0 else ""
    val = abs(val)
    return f"{sign}${val:,.2f}"


def parse_amount_series(s: pd.Series) -> pd.Series:
    """Robust parsing for Amount values."""

    def one(v):
        if pd.isna(v):
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        txt = str(v).strip()
        if not txt:
            return 0.0

        neg = False
        if txt.startswith("(") and txt.endswith(")"):
            neg = True
            txt = txt[1:-1].strip()

        txt = txt.replace("$", "").replace(",", "").strip()

        # keep only first numeric token if string is noisy
        m = re.search(r"[\+\-]?\d*\.?\d+", txt)
        if not m:
            return 0.0

        try:
            val = float(m.group(0))
        except Exception:
            val = 0.0

        if neg:
            val = -abs(val)
        return val

    return s.apply(one)


def normalize_text(s: pd.Series) -> pd.Series:
    return (
        s.fillna("")
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.upper()
    )


def agg_group(df: pd.DataFrame, key: str) -> pd.DataFrame:
    out = (
        df.groupby(key, dropna=False)
        .agg(
            txns=("Amount", "size"),
            net=("Amount", "sum"),
            abs_total=("Amount", lambda x: x.abs().sum()),
        )
        .reset_index()
    )
    return out


def make_table_pdf(path: Path, title: str, sections: list, landscape_mode: bool = False) -> None:
    styles = getSampleStyleSheet()
    pagesize = landscape(LETTER) if landscape_mode else LETTER
    doc = SimpleDocTemplate(
        str(path),
        pagesize=pagesize,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    elems = []
    elems.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    elems.append(Paragraph(datetime.now().strftime("Generated: %Y-%m-%d %H:%M"), styles["Normal"]))
    elems.append(Spacer(1, 12))

    for sec_title, rows in sections:
        elems.append(Paragraph(f"<b>{sec_title}</b>", styles["Heading3"]))
        data = [["Item", "Txns", "Total (NET)", "Total (ABS)"]]
        data.extend(rows if rows else [["(none)", "0", currency(0.0), currency(0.0)]])

        col_widths = [360, 60, 90, 90] if not landscape_mode else [520, 70, 110, 110]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
                ]
            )
        )
        elems.append(t)
        elems.append(Spacer(1, 14))
        elems.append(PageBreak())

    doc.build(elems)


# -----------------------
# Simplified category assignment + UNCATEGORIZED flagging
# -----------------------



# Canonicalize single description strings for pattern matching
# (keeps matching stable even when bank adds extra noise like 'PURCHASE AUTHORIZED ON', ref codes, urls, etc.)
def canonicalize_desc(desc: str) -> str:
    if desc is None:
        return ""
    d = str(desc).upper()
    d = re.sub(r"\s+", " ", d).strip()

    # Remove common leading noise (we keep the merchant part)
    d = re.sub(r"^PURCHASE\s+AUTHORIZED\s+ON\s+\d{1,2}/\d{1,2}\s+", "", d)

    # Merchant-specific cleanup / aliases
    # COMCAST variants -> unified label
    if 'COMCAST' in d:
        # Many exports show 'COMCAST CABLE' or just 'COMCAST'
        if 'COMCAST-XFINITY' in d or 'COMCAST XFINITY' in d or 'COMCAST CABLE' in d or d == 'COMCAST':
            d = 'COMCAST-XFINITY'

    # WAL-MART variants -> unified label
    if 'WM SUPERCENTER' in d:
        d = d.replace('WM SUPERCENTER', 'WAL-MART')
    d = d.replace("EUNIFYPAY*", "EUNIFYPAY ")
    # If bank appends URL/state after PAINTED P, squash it

    # AIR CARE COLORADO: some exports jam words together (e.g., 'AIR CARECOLORADOSTAPLETON')
    if "AIR CARECOLORADOSTAPLETON" in d.replace(" ", ""):
        d = "AIR CARE COLORADO STAPLETON"
    if "EUNIFYPAY" in d and "PAINTED" in d and "P" in d:
        d = re.sub(r"\bEUNIFYPAY\b.*\bPAINTED\s+P\b.*", "EUNIFYPAY PAINTED P", d)

    # SHEGER variants (truncated / duplicated)
    d = d.replace("SHEGER INTERNATIONAL MAR", "SHEGER INTERNATIONAL MARK")
    d = d.replace("SHEGER INTERNATION", "SHEGER INTERNATIONAL MARK")
    if d.startswith("SHEGER SHEGER"):
        d = "SHEGER INTERNATIONAL MARK"

    # Online transfers: map REF format -> your standardized tokens
    if "ONLINE TRANSFER" in d and "ACTIVE CASH" in d:
        d = "ONLINE TRANSFER TO WF ACTIVE CASH VISA"
    elif "ONLINE TRANSFER" in d and "REFLECT" in d:
        d = "ONLINE TRANSFER TO WF REFLECT VISA"
    elif "ONLINE TRANSFER" in d and "WAY2SAVE" in d:
        d = "ONLINE TRANSFER TO WAY2SAVE SAVINGS"
    elif "ONLINE TRANSFER" in d and "EVERYDAY CHECKING" in d:
        d = "ONLINE TRANSFER TO EVERYDAY CHECKING"

    # COBBLESTONE: always treat as Transportation (car wash / auto service)
    if "COBBLESTONE" in d:
        d = "COBBLESTONE"

    return d


def match_simplified_group(desc: str):
    """Return (group_name, matched_pattern) for first match, else (None, None)."""
    d = canonicalize_desc(desc)
    if not d:
        return None, None

    # deterministic group order; within each group prefer longer patterns first (avoid substring collisions)
    for grp, pats in SIMPLIFIED_PATTERNS.items():
        for p in sorted(pats, key=lambda s: len(s or ""), reverse=True):
            if p and p in d:
                return grp, p
    return None, None


def add_simplified_columns(df: pd.DataFrame) -> pd.DataFrame:
    groups = []
    patterns = []
    for d in df["Description"].fillna("").astype(str).tolist():
        grp, pat = match_simplified_group(d)
        groups.append(grp if grp else "UNCATEGORIZED")
        if pat:
            pat = PATTERN_CANONICAL.get(pat, pat)
        patterns.append(pat if pat else "")

    out = df.copy()
    out["Simplified Group"] = groups
    out["Matched Pattern"] = patterns
    return out


def build_patterns_table(df: pd.DataFrame) -> list:
    """Build per-group pattern tables WITHOUT double-counting.

    We assign each row to exactly one (group, matched_pattern) using match_simplified_group,
    then aggregate. This avoids duplicates like:
      - XCEL ENERGY... vs XCEL
      - DOMINO'S vs DOMINO
      - SHEGER INTERNATIONAL MARK vs ... MAR (substring)
    """
    df2 = add_simplified_columns(df)
    sections = []
    for grp in SIMPLIFIED_PATTERNS.keys():
        g = df2[df2["Simplified Group"] == grp].copy()
        if g.empty:
            sections.append((grp, []))
            continue

        # Grand totals for the entire group (all matched rows in this simplified category)
        grp_txns = int(len(g))
        grp_net = float(g["Amount"].sum())
        grp_abs = float(g["Amount"].abs().sum())

        t = agg_group(g, "Matched Pattern")
        t = t[t["Matched Pattern"].astype(str).str.strip() != ""]
        t = t.sort_values(["txns", "abs_total"], ascending=[False, False])
        rows = [
            [p, str(int(tx)), currency(net), currency(ab)]
            for p, tx, net, ab in t[["Matched Pattern", "txns", "net", "abs_total"]].values
        ]

        # Append a clean grand total row (always last)
        rows.append(["GRAND TOTAL", str(grp_txns), currency(grp_net), currency(grp_abs)])
        sections.append((grp, rows))
    return sections


def build_mastercat_table(df: pd.DataFrame) -> pd.DataFrame:
    mc = agg_group(df, "Master Category")
    mc = mc.sort_values(["txns", "abs_total"], ascending=[False, False])
    return mc


def build_payees_by_mastercat(df: pd.DataFrame, top_n: int) -> list:
    sections = []
    for cat, g in df.groupby("Master Category"):
        t = agg_group(g, "Payee")
        t = t[t["Payee"].astype(str).str.strip() != ""]
        t = t.sort_values(["txns", "abs_total"], ascending=[False, False]).head(top_n)
        rows = [[p, str(int(tx)), currency(net), currency(ab)] for p, tx, net, ab in t[["Payee", "txns", "net", "abs_total"]].values]
        sections.append((str(cat), rows))
    return sections


# -----------------------
# UNCATEGORIZED report
# -----------------------

def cmd_uncategorized(df: pd.DataFrame, reports_dir: Path, top_n: int = 40) -> None:
    df2 = add_simplified_columns(df)
    unc = df2[df2["Simplified Group"] == "UNCATEGORIZED"].copy()

    # Always write a CSV (even if empty) so you can quickly check it.
    csv_path = reports_dir / "uncategorized_rows.csv"
    unc.to_csv(csv_path, index=False)

    if unc.empty:
        # Write a tiny PDF stating all matched
        pdf_path = reports_dir / "uncategorized_descriptions_summary.pdf"
        make_table_pdf(
            pdf_path,
            "UNCATEGORIZED Descriptions (No Pattern Match)",
            [("All good", [["No uncategorized descriptions found ✅", "0", currency(0.0), currency(0.0)]])],
            landscape_mode=False,
        )
        print(f"✅ No uncategorized rows. Wrote: {csv_path}")
        print(f"✅ Wrote: {pdf_path}")
        return

    # Summarize by normalized Description (top N)
    s = (
        unc.groupby("Description", dropna=False)
        .agg(
            txns=("Amount", "size"),
            net=("Amount", "sum"),
            abs_total=("Amount", lambda x: x.abs().sum()),
        )
        .reset_index()
        .sort_values(["txns", "abs_total"], ascending=[False, False])
        .head(top_n)
    )

    rows = [[d, str(int(t)), currency(float(n)), currency(float(a))] for d, t, n, a in s[["Description", "txns", "net", "abs_total"]].values]

    pdf_path = reports_dir / "uncategorized_descriptions_summary.pdf"
    make_table_pdf(
        pdf_path,
        "UNCATEGORIZED Descriptions (No Pattern Match)",
        [(f"Top {min(top_n, len(rows))} uncategorized descriptions (ranked by Txns → ABS)", rows)],
        landscape_mode=True,
    )

    print(f"⚠️ Found {len(unc)} uncategorized rows.")
    print(f"✅ Wrote: {csv_path}")
    print(f"✅ Wrote: {pdf_path}")


# -----------------------
# PDF commands
# -----------------------

def cmd_mastercat(df: pd.DataFrame, reports_dir: Path) -> None:
    mc = build_mastercat_table(df)
    sections = [
        (
            "Master Category Summary (ranked by Txns)",
            [[c, str(int(t)), currency(float(n)), currency(float(a))] for c, t, n, a in mc[["Master Category", "txns", "net", "abs_total"]].values],
        )
    ]
    make_table_pdf(
        reports_dir / "expenses_18mo_mastercat_ranked_by_txns.pdf",
        "18-Month Expenses — Master Category Summary",
        sections,
        landscape_mode=False,
    )


def cmd_patterns(df: pd.DataFrame, reports_dir: Path) -> None:
    sections = build_patterns_table(df)
    make_table_pdf(
        reports_dir / "expenses_18mo_simplified_patterns_ranked_by_txns.pdf",
        "18-Month Expenses — Simplified Description Patterns (Organized)",
        sections,
        landscape_mode=False,
    )


def cmd_payees(df: pd.DataFrame, reports_dir: Path, top_payees: int) -> None:
    sections = build_payees_by_mastercat(df, top_payees)
    make_table_pdf(
        reports_dir / "expenses_18mo_payees_by_mastercat_ranked_by_txns.pdf",
        f"18-Month Expenses — Stores/Payees Visited (Top {top_payees} per Category)",
        sections,
        landscape_mode=True,
    )


def build_executive_summary_elements(
    df: pd.DataFrame,
    *,
    top_categories: int = 8,
    top_payees: int = 12,
    title: str = "Executive Summary (18 Months)",
) -> list:
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    normal = styles["BodyText"]

    elems = []
    elems.append(Paragraph(title, h1))

    # Date range
    min_date = None
    max_date = None
    if "Date" in df.columns:
        dts = pd.to_datetime(df["Date"], errors="coerce")
        if dts.notna().any():
            min_date = dts.min()
            max_date = dts.max()

    total_net = float(df["Amount"].sum())
    total_abs = float(df["Amount"].abs().sum())

    months = 18.0
    if min_date is not None and max_date is not None:
        span_days = (max_date - min_date).days
        months = max(1.0, span_days / 30.4375)

    avg_net = total_net / months
    avg_abs = total_abs / months

    meta_parts = []
    if min_date is not None and max_date is not None:
        meta_parts.append(f"Date range: {min_date.date()} → {max_date.date()}")
    meta_parts.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    elems.append(Paragraph(" • ".join(meta_parts), normal))
    elems.append(Spacer(1, 10))

    totals_data = [
        ["Metric", "Value"],
        ["Total (NET)", money(total_net)],
        ["Total (ABS)", money(total_abs)],
        ["Avg Monthly (NET)", money(avg_net)],
        ["Avg Monthly (ABS)", money(avg_abs)],
    ]
    totals_tbl = Table(totals_data, colWidths=[260, 180])
    totals_tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elems.append(totals_tbl)
    elems.append(Spacer(1, 12))

    if "Master Category" in df.columns:
        g = df.groupby("Master Category", dropna=False)["Amount"]
        cat_abs = g.apply(lambda s: float(s.abs().sum()))
        cat_txn = g.size().astype(int)
        cat_net = g.sum().astype(float)
        top = (
            pd.DataFrame({"Txns": cat_txn, "Total (NET)": cat_net, "Total (ABS)": cat_abs})
            .sort_values(["Txns", "Total (ABS)"], ascending=[False, False])
            .head(top_categories)
            .reset_index()
            .rename(columns={"Master Category": "Category"})
        )

        elems.append(Paragraph("Top Categories (Txns → ABS)", h2))
        cat_data = [["Category", "Txns", "Total (NET)", "Total (ABS)"]]
        for _, r in top.iterrows():
            cat_data.append(
                [
                    str(r["Category"]),
                    int(r["Txns"]),
                    money(float(r["Total (NET)"])),
                    money(float(r["Total (ABS)"])),
                ]
            )

        cat_tbl = Table(cat_data, colWidths=[270, 45, 85, 85])
        cat_tbl.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elems.append(cat_tbl)
        elems.append(Spacer(1, 10))

    if "Payee" in df.columns:
        g = df.groupby("Payee", dropna=False)["Amount"]
        p_abs = g.apply(lambda s: float(s.abs().sum()))
        p_txn = g.size().astype(int)
        p_net = g.sum().astype(float)
        top = (
            pd.DataFrame({"Txns": p_txn, "Total (NET)": p_net, "Total (ABS)": p_abs})
            .sort_values(["Txns", "Total (ABS)"], ascending=[False, False])
            .head(top_payees)
            .reset_index()
        )

        elems.append(Paragraph("Top Payees / Merchants (Txns → ABS)", h2))
        payee_data = [["Payee", "Txns", "Total (NET)", "Total (ABS)"]]
        for _, r in top.iterrows():
            payee_data.append(
                [
                    str(r["Payee"]),
                    int(r["Txns"]),
                    money(float(r["Total (NET)"])),
                    money(float(r["Total (ABS)"])),
                ]
            )

        payee_tbl = Table(payee_data, colWidths=[270, 45, 85, 85])
        payee_tbl.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        elems.append(payee_tbl)

    return elems


def cmd_exec_summary(df: pd.DataFrame, reports_dir: Path, top_payees: int) -> None:
    outpath = reports_dir / "expenses_18mo_executive_summary_ready_to_print.pdf"
    doc = SimpleDocTemplate(str(outpath), pagesize=LETTER, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    elems = build_executive_summary_elements(df, top_payees=top_payees)
    doc.build(elems)
    print(f"✅ Wrote executive summary PDF: {outpath}")


def cmd_ready_to_print(df: pd.DataFrame, reports_dir: Path, top_payees: int, auto_flag_uncategorized: bool = True) -> None:
    styles = getSampleStyleSheet()
    outpath = reports_dir / "ready_to_print_expenses_report.pdf"
    doc = SimpleDocTemplate(str(outpath), pagesize=LETTER, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)

    elems = []
    elems.append(Paragraph("<b>18-Month Expenses — Ready to Print Report</b>", styles["Title"]))
    elems.append(Paragraph(datetime.now().strftime("Generated: %Y-%m-%d %H:%M"), styles["Normal"]))
    elems.append(Spacer(1, 12))

    # 1) Master Category summary
    mc = build_mastercat_table(df)
    data = [["Master Category", "Txns", "Total (NET)", "Total (ABS)"]]
    data.extend([[c, str(int(t)), currency(float(n)), currency(float(a))] for c, t, n, a in mc[["Master Category", "txns", "net", "abs_total"]].values])
    t = Table(data, colWidths=[300, 60, 90, 90], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
            ]
        )
    )
    elems.append(Paragraph("<b>1) Master Category Summary (ranked by Txns)</b>", styles["Heading2"]))
    elems.append(t)
    elems.append(PageBreak())

    # 2) Patterns (each group on its own page)
    elems.append(Paragraph("<b>2) Simplified Description Patterns (Organized)</b>", styles["Heading2"]))
    elems.append(Spacer(1, 10))
    doc2_sections = build_patterns_table(df)
    for sec_title, rows in doc2_sections:
        elems.append(Paragraph(f"<b>{sec_title}</b>", styles["Heading3"]))
        d = [["Pattern", "Txns", "Total (NET)", "Total (ABS)"]]
        d.extend(rows if rows else [["(none)", "0", currency(0.0), currency(0.0)]])
        tt = Table(d, colWidths=[300, 60, 90, 90], repeatRows=1)
        tt.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
                ]
            )
        )
        elems.append(tt)
        elems.append(PageBreak())

    # 3) Payees
    elems.append(Paragraph(f"<b>3) Stores/Payees Visited (Top {top_payees} per Master Category)</b>", styles["Heading2"]))
    elems.append(Spacer(1, 10))
    payee_sections = build_payees_by_mastercat(df, top_payees)
    for sec_title, rows in payee_sections:
        elems.append(Paragraph(f"<b>{sec_title}</b>", styles["Heading3"]))
        d = [["Payee", "Txns", "Total (NET)", "Total (ABS)"]]
        d.extend(rows if rows else [["(none)", "0", currency(0.0), currency(0.0)]])
        tt = Table(d, colWidths=[300, 60, 90, 90], repeatRows=1)
        tt.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
                ]
            )
        )
        elems.append(tt)
        elems.append(PageBreak())

    doc.build(elems)
    print(f"✅ Wrote ready-to-print PDF: {outpath}")

    if auto_flag_uncategorized:
        # run after PDF generation so you always get a separate QA output
        cmd_uncategorized(df, reports_dir, top_n=40)



def cmd_quick_look_up_pdf(df: pd.DataFrame, reports_dir: Path, top_payees: int, auto_flag_uncategorized: bool = True) -> None:
    """Compact, quick-look PDF.

    Same content as ready_to_print_expenses_report.pdf but with smaller fonts and tighter spacing,
    designed for fast scanning.
    """
    styles = getSampleStyleSheet()
    outpath = reports_dir / "quick_look_up_expenses_report.pdf"

    # tighter margins to fit more on each page
    doc = SimpleDocTemplate(str(outpath), pagesize=LETTER, leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)

    title_style = styles["Title"].clone('quick_title')
    title_style.fontSize = 16
    title_style.leading = 18

    normal = styles["Normal"].clone('quick_normal')
    normal.fontSize = 8
    normal.leading = 9

    h2 = styles["Heading2"].clone('quick_h2')
    h2.fontSize = 11
    h2.leading = 13

    h3 = styles["Heading3"].clone('quick_h3')
    h3.fontSize = 10
    h3.leading = 12

    # shared compact table style
    def apply_compact_style(tbl: Table) -> None:
        tbl.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.6),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
                ]
            )
        )

    elems = []
    elems.append(Paragraph("<b>18-Month Expenses — Quick Look Report</b>", title_style))
    elems.append(Paragraph(datetime.now().strftime("Generated: %Y-%m-%d %H:%M"), normal))
    elems.append(Spacer(1, 8))

    # 1) Master Category summary
    mc = build_mastercat_table(df)
    data = [["Master Category", "Txns", "Total (NET)", "Total (ABS)"]]
    data.extend(
        [[c, str(int(t)), currency(float(n)), currency(float(a))] for c, t, n, a in mc[["Master Category", "txns", "net", "abs_total"]].values]
    )
    t = Table(data, colWidths=[290, 50, 75, 75], repeatRows=1)
    apply_compact_style(t)
    elems.append(Paragraph("<b>1) Master Category Summary (ranked by Txns)</b>", h2))
    elems.append(t)
    # No forced page break here — we want multiple sections per page for quick lookup.
    elems.append(Spacer(1, 10))

    # 2) Patterns
    elems.append(Paragraph("<b>2) Simplified Description Patterns (Organized)</b>", h2))
    elems.append(Spacer(1, 6))
    doc2_sections = build_patterns_table(df)
    for sec_title, rows in doc2_sections:
        elems.append(Paragraph(f"<b>{sec_title}</b>", h3))
        d = [["Pattern", "Txns", "Total (NET)", "Total (ABS)"]]
        d.extend(rows if rows else [["(none)", "0", currency(0.0), currency(0.0)]])
        tt = Table(d, colWidths=[290, 50, 75, 75], repeatRows=1)
        apply_compact_style(tt)
        elems.append(tt)
        # Allow multiple categories per page; let ReportLab naturally flow/split tables.
        elems.append(Spacer(1, 8))

    # 3) Payees
    # Put payees on a new page so patterns can pack tightly together.
    elems.append(PageBreak())
    elems.append(Paragraph(f"<b>3) Stores/Payees Visited (Top {top_payees} per Master Category)</b>", h2))
    elems.append(Spacer(1, 6))
    payee_sections = build_payees_by_mastercat(df, top_payees)
    for sec_title, rows in payee_sections:
        elems.append(Paragraph(f"<b>{sec_title}</b>", h3))
        d = [["Payee", "Txns", "Total (NET)", "Total (ABS)"]]
        d.extend(rows if rows else [["(none)", "0", currency(0.0), currency(0.0)]])
        tt = Table(d, colWidths=[290, 50, 75, 75], repeatRows=1)
        apply_compact_style(tt)
        elems.append(tt)
        elems.append(Spacer(1, 8))

    doc.build(elems)
    print(f"✅ Wrote quick-look PDF: {outpath}")

    if auto_flag_uncategorized:
        cmd_uncategorized(df, reports_dir, top_n=40)

# -----------------------
# CLI
# -----------------------

def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing required columns: {missing}\nFound: {list(df.columns)}")

    df["Amount"] = parse_amount_series(df["Amount"])
    df["Description"] = normalize_text(df["Description"])
    df["Payee"] = normalize_text(df["Payee"])
    df["Master Category"] = df["Master Category"].fillna("").astype(str).str.strip()

    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="18-month expenses CSV (expenses.csv)")
    ap.add_argument(
        "command",
        choices=["ready_to_print", "quick_look_up_pdf", "exec_summary", "mastercat", "patterns", "payees", "uncategorized", "all"],
        help="Which report to generate",
    )
    ap.add_argument("--top-payees", type=int, default=25, help="Top N payees per master category")
    ap.add_argument(
        "--no-auto-flag",
        action="store_true",
        help="Disable auto-run of uncategorized report after ready_to_print/all",
    )

    args = ap.parse_args()

    df = load_csv(args.csv)

    reports_dir = ensure_reports_dir("output")

    if args.command in ("mastercat", "all"):
        cmd_mastercat(df, reports_dir)

    if args.command in ("patterns", "all"):
        cmd_patterns(df, reports_dir)

    if args.command in ("exec_summary", "all"):
        cmd_exec_summary(df, reports_dir, args.top_payees)

    if args.command in ("payees", "all"):
        cmd_payees(df, reports_dir, args.top_payees)

    if args.command in ("uncategorized",):
        cmd_uncategorized(df, reports_dir, top_n=40)

    if args.command == "quick_look_up_pdf":
        cmd_quick_look_up_pdf(df, reports_dir, args.top_payees, auto_flag_uncategorized=(not args.no_auto_flag))

    if args.command in ("ready_to_print", "all"):
        cmd_ready_to_print(df, reports_dir, args.top_payees, auto_flag_uncategorized=(not args.no_auto_flag))

    print("Done. See output/reports/")


if __name__ == "__main__":
    main()
