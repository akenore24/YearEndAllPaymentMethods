"""
finance_core.grouping
Grouping rules: Zelle and merchant family cores.
"""
from __future__ import annotations
import re
from typing import Any
from .utils import normalize_spaces
from .merchant_normalize import normalize_merchant_name

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

def merchant_core(description_upper: str) -> str:
    d = description_upper
    if not d:
        return "OTHER"

    # common families
    if d.startswith("AMAZON"):
        return "AMAZON"
    if d.startswith("7-ELEVEN"):
        return "7-ELEVEN"
    if d.startswith("COSTCO GAS"):
        return "COSTCO GAS"
    if d.startswith("COSTCO WHSE") or d.startswith("COSTCO WHOLESALE"):
        return "COSTCO WHSE"
    if d.startswith("WAL-MART") or d.startswith("WM SUPERCENTER") or d.startswith("WALMART"):
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
    if d.startswith("WT FED"):
        return "WT FED"
    if d.startswith("EUNIFYPAY"):
        return "EUNIFYPAY"
    if d.startswith("ONLINE TRANSFER"):
        return "ONLINE TRANSFER"
    if d.startswith("SHEGER MARKET"):
        return "SHEGER MARKET"
    if d.startswith("DOMINO'S PIZZA"):
        return "DOMINO'S PIZZA"
    if d.startswith("APPLEBEES"):
        return "APPLEBEES"
    if d.startswith("CHIPOTLE"):
        return "CHIPOTLE"
    if d.startswith("NAME-CHEAP.COM"):
        return "NAME-CHEAP.COM"
    if d.startswith("PRIMELENDING"):
        return "PRIMELENDING"

    tokens = d.split()
    if not tokens:
        return "OTHER"
    return " ".join(tokens[:2]) if len(tokens) >= 2 else tokens[0]

def group_key(description: str) -> str:
    d = normalize_merchant_name(description)
    if not d:
        return "OTHER"
    if d.startswith("ZELLE TO"):
        return f"ZELLE - {extract_zelle_person(d)}"
    return merchant_core(d)

def group_key_organized(description: str) -> str:
    d = normalize_merchant_name(description)
    if not d:
        return "OTHER"
    if d.startswith("ZELLE TO"):
        return "ZELLE"
    return merchant_core(d)

def is_zelle_group(name: str) -> bool:
    return name.upper().startswith("ZELLE - ")
