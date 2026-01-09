"""
finance_core.merchant_normalize
Merchant normalization before grouping.
"""
from __future__ import annotations
import re
from .utils import normalize_spaces

# Regex rules are applied to UPPERCASED description
MERCHANT_NORMALIZATION_RULES = [
    # WT FED#01794 -> WT FED
    (r"\bWT\s+FED[#\s]*\d+\b", "WT FED"),

    # EUNIFYPAY* PAINTED -> EUNIFYPAY PAINTED (remove * and extra spacing)
    (r"\bEUNIFYPAY\*\s*", "EUNIFYPAY "),

    # SHEGER INTERNATIONAL / SHEGER INTERNATION -> SHEGER MARKET
    (r"\bSHEGER\s+INTERNATION(?:AL)?\b", "SHEGER MARKET"),

    # APPLEBEES 2104013 / ... -> APPLEBEES
    (r"\bAPPLEBEES\s+\d+\b", "APPLEBEES"),

    # CHIPOTLE 0871 / ... -> CHIPOTLE
    (r"\bCHIPOTLE\s+\d+\b", "CHIPOTLE"),

    # DOMINO'S 6217 / ... -> DOMINO'S PIZZA
    (r"\bDOMINO['’]S\s+\d+\b", "DOMINO'S PIZZA"),

    # KING SOOP / KING SOOPERS -> KING SOOPERS
    (r"\bKING\s+SOOP(?:ERS)?\b", "KING SOOPERS"),

    # NAME-CHEAP.COM VGAIJC -> NAME-CHEAP.COM
    (r"\bNAME-?CHEAP\.COM\s+[A-Z0-9]+\b", "NAME-CHEAP.COM"),

    # PRMG WEB / PRIMELENDING ACH / PRIMELENDING WWW.PRIMELEND,TX -> PRIMELENDING
    (r"\bPRMG\s+WEB\b", "PRIMELENDING"),
    (r"\bPRIMELENDING\s+ACH\b", "PRIMELENDING"),
    (r"\bPRIMELENDING\s+WWW\.PRIMELEND,?TX\b", "PRIMELENDING"),
]

def normalize_merchant_name(description: str) -> str:
    """
    Normalizes merchant text to reduce noise IDs, asterisks, etc.
    Runs before grouping.
    """
    if not description:
        return ""
    d = normalize_spaces(description).upper()

    # apply explicit regex merge rules
    for pattern, repl in MERCHANT_NORMALIZATION_RULES:
        d = re.sub(pattern, repl, d)

    # LYFT variants -> LYFT (LYFT *RIDE, LYFT *2, etc.)
    if d.startswith("LYFT"):
        d = "LYFT"

    # generic cleanup
    d = re.sub(r"\*+", " ", d)
    d = re.sub(r"#\d+\b", "", d)          # remove trailing #digits tokens
    d = re.sub(r"\s+\d+\b$", "", d)       # remove trailing numeric store ids
    d = normalize_spaces(d)
    return d
