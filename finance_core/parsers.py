from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from .config import DATE_FORMATS

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

def parse_date(value: str) -> Optional[datetime]:
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

def normalize_payment_method(value: str, wf_prefix: str, wf_alias: str) -> str:
    value = (value or "").strip()
    if value.upper().startswith(wf_prefix):
        suffix = value[len(wf_prefix):].strip()
        return f"{wf_alias}{suffix}"
    return value

def normalize_merchant_name(description: str, rules) -> str:
    if not description:
        return ""
    d = " ".join(description.split()).strip().upper()

    for pattern, repl in rules:
        d = re.sub(pattern, repl, d)

    # LYFT variants -> LYFT
    if d.startswith("LYFT"):
        return "LYFT"

    # generic cleanup
    d = re.sub(r"\*+", " ", d)
    d = re.sub(r"#\d+\b", "", d)
    d = re.sub(r"\s+\d+\b$", "", d)
    d = " ".join(d.split()).strip()
    return d
