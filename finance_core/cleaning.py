"""
finance_core.cleaning
Row-level cleaning: spacing, narration removal, payment method normalization.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple
from .config import REMOVE_DESC_PREFIX, WF_CARD_PREFIX, WF_CARD_ALIAS
from .utils import normalize_spaces

def clean_description(raw: str) -> str:
    d = normalize_spaces(raw)
    if not d:
        return ""

    m = re.match(r"^PURCHASE\s+AUTHORIZED\s+ON\s+\d{2}/\d{2}\s+(.*)$", d, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    m = re.match(r"^ATM\s+WITHDRAWAL\s+AUTHORIZED\s+ON\s+\d{2}/\d{2}\s+(.*)$", d, flags=re.IGNORECASE)
    if m:
        return ("ATM WITHDRAWAL " + m.group(1).strip()).strip()

    if re.match(r"^DEPOSITED\s+OR\s+CASHED\s+CHECK", d, flags=re.IGNORECASE):
        return "DEPOSITED OR CASHED CHECK"

    return d

def normalize_payment_method(value: str) -> str:
    value = (value or "").strip()
    if value.upper().startswith(WF_CARD_PREFIX):
        suffix = value[len(WF_CARD_PREFIX):].strip()
        return f"{WF_CARD_ALIAS}{suffix}"
    return value

def clean_rows(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    cleaned: List[Dict[str, Any]] = []
    removed = 0
    for r in rows:
        r["Description"] = clean_description(r.get("Description"))
        if (r.get("Description") or "").upper().startswith(REMOVE_DESC_PREFIX.upper()):
            removed += 1
            continue
        r["Payment Method"] = normalize_payment_method(r.get("Payment Method"))
        cleaned.append(r)
    return cleaned, removed
