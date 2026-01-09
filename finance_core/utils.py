"""
finance_core.utils
Small reusable helpers.
"""
from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo

def normalize_spaces(text: str) -> str:
    return " ".join((text or "").split()).strip()

def fmt_money(n: float) -> str:
    return f"${n:,.2f}"

def now_mountain() -> datetime:
    try:
        return datetime.now(ZoneInfo("America/Denver"))
    except Exception:
        return datetime.now()

def mt_timestamp_line(prefix: str = "Generated") -> str:
    dt = now_mountain()
    return f"{prefix}: {dt.strftime('%Y-%m-%d %H:%M:%S')} MT"
