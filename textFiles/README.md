# Finance Master (Modular / DRY)
# @Abinet Kenore 
# Jan 07, 2026
A clean, modular CLI tool for cleaning, grouping, and producing Excel/PDF
 reports from a bank-export CSV of transactions.

## Expected CSV columns
Minimum required:
- `Date`
- `Description`
- `Amount`

Optional (used when present):
- `Payee`
- `Payment Method`
- `Location`
- `Master Category`
- `Subcategory`

## Install
```bash
pip3 install -r requirements.txt
```

## Run (examples)

> Default input file is `expenses.csv` in the same folder.

### 1) Fix spacing only (writes CSV)
```bash
python3 finance_master.py spacing
```
Creates:
- `output/csv/expenses_raw_spacing_fixed.csv`

### 2) Quick summary to console
```bash
python3 finance_master.py quick --limit 40
```

### 3) Quick summary PDF (1 page)
```bash
python3 finance_master.py quick_pdf --limit 60 --sort total
```
Creates:
- `output/pdf/expenses_quick_summary.pdf`

### 4) Pipeline (Excel + PDF detail + summary)
```bash
python3 finance_master.py pipeline
```
Creates:
- `output/xlsx/expenses_clean_grouped.xlsx`
- `output/xlsx/expenses_family_summary.xlsx`
- `output/pdf/expenses_grouped_families_detail.pdf`
- `output/pdf/expenses_family_summary.pdf`

### 5) Families summaries
```bash
python3 finance_master.py excel_families --sort total --zelle-block first
python3 finance_master.py pdf_families   --sort txns  --zelle-block last
```

### 6) Organized report (summary page + detailed pages; ALL Zelle together)
```bash
python3 finance_master.py organized_pdf --top-total 25 --top-txns 25
```
Creates:
- `output/pdf/organized_report.pdf`

### 7) READY TO PRINT (Families + Zelle-by-person)
```bash
python3 finance_master.py ready_to_print
```
Creates:
- `output/xlsx/ready_to_print.xlsx`
- `output/pdf/ready_to_print.pdf`

Control how many non-priority families appear after the pinned list:
```bash
python3 finance_master.py ready_to_print --top-other 40
python3 finance_master.py ready_to_print --top-other 0
```

## Output folders
This tool creates folders automatically:
- `output/csv`
- `output/xlsx`
- `output/pdf`

## Notes
- Adds a Mountain Time (America/Denver) timestamp to Excel + PDF + console output.
- Normalizes merchants (examples: `WT FED#01794` -> `WT FED`, 
`EUNIFYPAY* ...` -> `EUNIFYPAY ...`, `LYFT *RIDE` -> `LYFT`).

# Jan 07, 26 ADDED 
Merge: 
SHEGER INTERNATIONAL and SHEGER INTERNATION and name it SHEGER MARKET
APPLEBEES 2104013 and APPLEBEES 2104028 to APPLEBEES
CHIPOTLE 0871 and CHIPOTLE 4645 to CHIPOTLE
DOMINO'S 6217 and DOMINO'S 6299 to DOMINO'S PIZZA
KING SOOP and KING SOOPERS to KING SOOPERS
NAME-CHEAP.COM VGAIJC and NAME-CHEAP.COM WUKTQL to NAME-CHEAP.COM;
PRMG WEB, PRIMELENDING ACH and PRIMELENDING WWW.PRIMELEND,TX to PRIMELENDING


