# WF_TRANSFER_CLEANER — CLI Help

**Generated:** 2026-01-17 23:16:14  
**Command:** `python3 wf_transfer_cleaner.py --help`

---

```text
usage: wf_transfer_cleaner.py [-h] [--dry-run] [--no-name-filter]
                              [--out-clean OUT_CLEAN]
                              [--out-report OUT_REPORT]
                              [--out-spacing OUT_SPACING] [--no-out-spacing]
                              [--summary-pdf SUMMARY_PDF]
                              input_csv

Normalize spacing, split merged descriptions, remove internal transfers + WF Visa payments.

positional arguments:
  input_csv             Input CSV export file path

options:
  -h, --help            show this help message and exit
  --dry-run             Analyze only; write no output files
  --no-name-filter      Do not require 'KENORE' for Way2Save transfer matching
  --out-clean OUT_CLEAN
                        Final cleaned output CSV filename (default: clean.csv)
  --out-report OUT_REPORT
                        Removed rows report filename (default: transfers_report.csv)
  --out-spacing OUT_SPACING
                        Spacing baseline filename (default: clean_spacing.csv)
  --no-out-spacing      Disable writing the spacing baseline file
  --summary-pdf SUMMARY_PDF
                        Create a ready-to-print summary PDF at the given path/filename

Examples:
  wf_transfer_cleaner.py export.csv --dry-run
  wf_transfer_cleaner.py export.csv --summary-pdf summary.pdf
  wf_transfer_cleaner.py export.csv --no-out-spacing --no-name-filter
```

