# Finance Master

A DRY, modular CLI tool for cleaning and reporting on financial transaction CSV exports.

## Install
```bash
pip3 install -r requirements.txt
```

## Run
```bash
python3 finance_master.py --help
python3 finance_master.py all
```

Outputs:
- `output/csv/` (spacing-fixed CSV)
- `output/xlsx/` (Excel reports)
- `output/pdf/` (PDF reports)

## Common commands
- `spacing` → creates `output/csv/expenses_raw_spacing_fixed.csv`
- `pipeline` → creates Excel + PDF detail/summary
- `ready_to_print` → creates `ready_to_print.xlsx` + `ready_to_print.pdf`
- `quick_pdf_18mo` → creates the 18-month bucket executive PDF
- `exec_txns_desc` → highest-to-lowest transaction count PDF
- `all` → runs everything
