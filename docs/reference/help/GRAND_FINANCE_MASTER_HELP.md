# GRAND_FINANCE_MASTER — CLI Help

**Generated:** 2026-01-17 23:16:15  
**Command:** `python3 grand_finance_master.py --help`

---

```text
usage: grand_finance_master.py [-h] [--in INPUT_CSV]
                               {spacing,quick,quick_pdf,exec_txns_desc,quick_pdf_18mo,pipeline,pdf_families,excel_families,organized_pdf,ready_to_print,all,compare_quick_pdf,wf_clean,wf_to_all} ...

Grand Finance Master: finance_master + wf_transfer_cleaner (one CLI).

positional arguments:
  {spacing,quick,quick_pdf,exec_txns_desc,quick_pdf_18mo,pipeline,pdf_families,excel_families,organized_pdf,ready_to_print,all,compare_quick_pdf,wf_clean,wf_to_all}
    spacing             Fix inconsistent spacing in raw CSV (no grouping, no
                        deletions).
    quick               Print quick summary to console.
    quick_pdf           Create a 1-page Quick Summary PDF.
    exec_txns_desc      Executive summary sorted by txns (high → low).
    quick_pdf_18mo      Executive summary PDF split into 18-month buckets.
    pipeline            Excel detail+summary + PDF detail+summary.
    pdf_families        PDF families summary (sorted).
    excel_families      Excel families summary (sorted).
    organized_pdf       Organized PDF (Top by Total).
    ready_to_print      Create ready_to_print.xlsx and ready_to_print.pdf.
    all                 Run EVERYTHING: pipeline + ready_to_print + quick
                        PDFs.
    compare_quick_pdf   Compare TWO CSV files (12m vs 18m) -> one PDF.
    wf_clean            Wells Fargo transfer cleaner.
    wf_to_all           WF export -> wf_clean -> finance ALL on clean.csv

options:
  -h, --help            show this help message and exit
  --in INPUT_CSV        Default input CSV for finance commands.
```

