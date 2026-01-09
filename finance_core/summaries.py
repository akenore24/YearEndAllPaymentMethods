"""
finance_core.summaries
Sorting + summary builders.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Callable, Dict, List, Tuple
from .parsing import parse_amount, parse_date
from .grouping import is_zelle_group

def sort_rows_for_detail(rows: List[Dict[str, Any]], key_fn: Callable[[str], str]) -> List[Dict[str, Any]]:
    rows.sort(
        key=lambda r: (
            key_fn(r.get("Description") or ""),
            (r.get("Description") or "").upper(),
            parse_date(r.get("Date")) or datetime.max,
        )
    )
    return rows

def build_summary(rows: List[Dict[str, Any]], key_fn: Callable[[str], str]) -> Dict[str, Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        g = key_fn(r.get("Description") or "")
        amt = parse_amount(r.get("Amount"))
        summary.setdefault(g, {"txns": 0, "total": 0.0})
        summary[g]["txns"] += 1
        summary[g]["total"] += amt
    return summary

def sort_summary_items(summary: Dict[str, Dict[str, Any]], sort_mode: str) -> List[Tuple[str, Dict[str, Any]]]:
    items = list(summary.items())
    if sort_mode == "total":
        return sorted(items, key=lambda kv: (-kv[1]["total"], -kv[1]["txns"], kv[0]))
    return sorted(items, key=lambda kv: (-kv[1]["txns"], kv[0], -kv[1]["total"]))

def apply_zelle_blocking(items_sorted: List[Tuple[str, Dict[str, Any]]], zelle_block: str):
    if zelle_block == "none":
        return items_sorted
    zelle_items = [kv for kv in items_sorted if is_zelle_group(kv[0])]
    other_items = [kv for kv in items_sorted if not is_zelle_group(kv[0])]
    return (zelle_items + other_items) if zelle_block == "first" else (other_items + zelle_items)

def reorder_priority_first(items_sorted: List[Tuple[str, Dict[str, Any]]], priority: List[str]) -> List[Tuple[str, Dict[str, Any]]]:
    lookup = {name: info for name, info in items_sorted}
    used = set()
    out: List[Tuple[str, Dict[str, Any]]] = []
    for p in priority:
        if p in lookup:
            out.append((p, lookup[p]))
            used.add(p)
    out.extend([(name, info) for name, info in items_sorted if name not in used])
    return out
