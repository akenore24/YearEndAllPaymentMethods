# Jan 10, 2026

# Finance Pipeline — Architecture Overview

## Purpose

This document describes the **architecture, design decisions, and data flow**
behind the finance pipeline composed of:

- **wf_transfer_cleaner.py** — data hygiene & validation
- **finance_master.py** — analysis, grouping, and reporting

The goal of this system is **correctness first**: ensuring that financial reports
are based on clean, trusted data before any analysis occurs.

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
[ Analysis / Reports / PDFs (finance_master.py) ]
```

Most personal finance tools skip the middle layers.
This pipeline intentionally does not.

---

## Core Design Principles

- **Separation of Concerns**

  - Cleaning ≠ Analysis
  - wf_transfer_cleaner.py fixes data correctness
  - finance_master.py consumes already-clean data

- **Auditability**

  - Nothing is silently deleted
  - Every removal has a reason
  - Human-readable reports exist at each critical stage

- **Determinism**

  - Same input → same output
  - No hidden state or side effects

- **Extensibility**
  - New rules can be added without breaking existing behavior

---

## Component 1 — wf_transfer_cleaner.py

### Responsibility

Prepare a raw bank CSV so it is **safe for financial analysis**.

### Processing Order (Intentional)

1. **Normalize Inconsistent Spacing**

   - Collapse multiple spaces
   - Trim whitespace
   - Applied across all text fields

2. **Split Malformed Rows**

   - Handles cases where multiple transactions are combined
   - Uses `ON mm/dd/yy` boundaries to separate logical transactions

3. **Remove Non-Expense Transactions**

   - Internal transfers (Checking ⇄ Savings / Way2Save)
   - Credit card payments:
     - Wells Fargo Active Cash Visa
     - Wells Fargo Reflect Visa

4. **Log Everything**

   - Removed rows written to `transfers_report.csv`
   - Each row includes a human-readable `RemovalReason`

5. **Produce Trusted Output**
   - `clean.csv` becomes the single source of truth
   - Optional `clean_spacing.csv` provides a pre-removal baseline

### Outputs

| File                   | Purpose                                |
| ---------------------- | -------------------------------------- |
| `clean.csv`            | Final trusted dataset                  |
| `transfers_report.csv` | Audit log of removed rows              |
| `clean_spacing.csv`    | Spacing-normalized baseline (optional) |
| `*.pdf`                | Executive summary (optional)           |

---

## Component 2 — finance_master.py

### Responsibility

Analyze and report on **already-clean financial data**.

### Key Behaviors

- Groups transactions by normalized merchants
- Produces:
  - Console summaries
  - Excel reports
  - PDF summaries
- Supports a **pipeline mode** that runs all reports consistently

### Input Strategy

- Accepts any CSV path
- Automatically uses `clean.csv` when present
- Never re-cleans data (by design)

This ensures analysis remains deterministic and repeatable.

---

## Integration Strategy

The two scripts form a **linear pipeline**:

```
wf_transfer_cleaner.py  →  clean.csv  →  finance_master.py
```

Example workflow:

```bash
python3 wf_transfer_cleaner.py raw_export.csv
python3 finance_master.py pipeline
```

No renaming required.
No manual cleanup steps.

---

## Audit & Trust Model

This system is designed so you can answer:

- _What was removed?_
- _Why was it removed?_
- _How many rows were affected?_
- _What impact did this have on totals?_

Artifacts that support this:

- `transfers_report.csv`
- Snapshot counts in CLI output
- Ready-to-print PDF summaries

---

## Common Pitfalls This Architecture Avoids

- ❌ Counting internal transfers as expenses
- ❌ Double-counting credit card payments
- ❌ Grouping errors caused by spacing
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

Most users jump from Level 1 → Level 4.
This pipeline deliberately does not.

---

## Future Enhancements (Optional)

- Debit/Credit sign normalization
- Merchant canonicalization
  - `7 ELEVEN` → `7-ELEVEN`
  - `COSTCO GAS #123` → `COSTCO GAS`
- One-command execution:
  ```bash
  python3 finance_master.py pipeline --preclean raw.csv
  ```

---

## Status Check

**We’re doing very well — objectively and architecturally.**

You are no longer fixing scripts.
You are designing systems.

---

## Versioning

- Architecture stabilized: **v1.0**
- Breaking changes require explicit version bumps
- New rules must preserve auditability

---

## Final Note

This document exists so future you (or collaborators)
can understand _why_ the system is structured this way,
not just _how_ it runs.
