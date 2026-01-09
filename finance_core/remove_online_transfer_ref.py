
import csv
from pathlib import Path
from openpyxl import Workbook

def remove_online_transfer_ref(csv_filename):
    base_dir = Path(__file__).parent
    input_csv = base_dir / csv_filename
    output_xlsx = base_dir / "expenses_without_online_transfer.xlsx"

    if not input_csv.exists():
        print(f"❌ File not found: {input_csv}")
        return

    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames

    # Filter out rows where Description starts with "ONLINE TRANSFER REF"
    cleaned_rows = [
        row for row in rows
        if not (row["Description"] or "").startswith("ONLINE TRANSFER REF")
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "Cleaned Data"

    ws.append(headers)
    for row in cleaned_rows:
        ws.append([row[h] for h in headers])

    wb.save(output_xlsx)
    print(f"✅ File created: {output_xlsx.name}")
    print(f"🧹 Removed {len(rows) - len(cleaned_rows)} rows")

if __name__ == "__main__":
    remove_online_transfer_ref("expenses.csv")

