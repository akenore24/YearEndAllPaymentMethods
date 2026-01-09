"""
finance_core.parsing
Date/amount parsing.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, Tuple
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
