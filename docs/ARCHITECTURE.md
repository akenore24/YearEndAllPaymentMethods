# Finance Project — Architecture

_Last updated: Jan 16, 2026_

---

## Purpose

This document describes the **architecture, design principles, and data flow** of the Finance Project. It explains *why* the system is structured the way it is.

---

## High-Level Data Flow

```
[ Raw Bank CSV ]
        ↓
[ Spacing Normalization ]
        ↓
[ Split Malformed Rows ]
        ↓
[ Remove Internal Transfers & Payments ]
        ↓
[ Clean, Trusted Dataset (clean.csv) ]
        ↓
[ Analysis / Reports / PDFs ]
```

---

## Core Design Principles

### Separation of Concerns
- Cleaning ≠ Analysis
- Validation always happens before reporting

### Auditability
- Nothing is silently deleted
- Every removal is logged

### Determinism
- Same input → same output
- No hidden state

### Extensibility
- New rules can be added safely
- Core logic remains stable

---

## Component: wf_transfer_cleaner.py

### Responsibility
Prepare raw bank CSVs so they are **safe for analysis**.

### Processing Order
1. Normalize inconsistent spacing
2. Split malformed rows ("ON mm/dd/yy")
3. Remove non-expense transactions
   - Internal transfers
   - WF Active Cash Visa payments
   - WF Reflect Visa payments
4. Log all removals with reasons
5. Produce trusted outputs

### Outputs

| File | Purpose |
|---|---|
| clean.csv | Final trusted dataset |
| transfers_report.csv | Audit log of removed rows |
| clean_spacing.csv | Spacing-normalized baseline (optional) |
| *.pdf | Optional summary PDF |

---

## Component: finance_master.py / grand_finance_master.py

### Responsibility
Analyze and report on **already-clean financial data**.

### Capabilities
- Merchant normalization & grouping
- Console summaries
- Excel reports
- PDF summaries
- One-command pipeline execution

### Input Strategy
- Accepts any CSV path
- Uses `clean.csv` automatically when present
- Never re-cleans data (by design)

---

## Integration Strategy

Linear pipeline:

```
wf_transfer_cleaner.py → clean.csv → finance_master.py
```

Example:
```bash
python3 wf_transfer_cleaner.py raw_export.csv
python3 finance_master.py pipeline
```

---

## Audit & Trust Model

You can always answer:
- What was removed?
- Why was it removed?
- How many rows were affected?

Supporting artifacts:
- transfers_report.csv
- CLI summaries
- Ready-to-print PDFs

---

## Common Pitfalls Avoided

- ❌ Counting internal transfers as expenses
- ❌ Double-counting credit card payments
- ❌ Silent data mutation
- ❌ Analysis on malformed rows

---

## Maturity Model

```
Level 1: Raw CSV + Guessing
Level 2: Basic Scripts
Level 3: Data Hygiene & Validation   ← THIS SYSTEM
Level 4: Analysis & Reporting
Level 5: Automation & Optimization
```

---

## Future Enhancements

- Debit/Credit sign normalization
- Merchant canonicalization
- Optional pre-clean support
- Shared `finance_core` module

---

_End of ARCHITECTURE.md_
