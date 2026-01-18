# Finance Project

A **DRY, modular CLI system** for cleaning, validating, and reporting on financial transaction CSV exports. The project prioritizes **data correctness, auditability, and determinism** before analysis or reporting.

---

## Overview

This repository provides a clean, repeatable pipeline to turn raw bank exports into trusted reports.

**Core components**
- **wf_transfer_cleaner.py** — data hygiene & validation
- **finance_master.py / grand_finance_master.py** — analysis, grouping, and reporting

---

## Quick Start

```bash
# Clean raw bank export
python3 wf_transfer_cleaner.py raw_export.csv

# Run full analysis pipeline
python3 grand_finance_master.py all
```

---

## What This Solves

- Prevents counting **internal transfers** as expenses
- Avoids **double-counting** credit card payments
- Ensures analysis is run only on **trusted data**
- Produces **audit-friendly** CSV, Excel, and PDF outputs

---

## CLI Usage (Summary)

```bash
python3 grand_finance_master.py --help
python3 grand_finance_master.py all
```

Common commands:
- spacing
- pipeline
- ready_to_print
- quick_pdf_18mo
- exec_txns_desc
- all

(See `CLI_REFERENCE.txt` for the complete command list.)

---

## Contributing (Short)

- Keep logic **simple and DRY**
- Do not break existing reports
- Never commit real financial data

For architecture details and design decisions, see **ARCHITECTURE.md**.

---

## Status & Versioning

- Architecture stabilized: **v1.0**
- Breaking changes require explicit version bumps

---

_End of README.md_
