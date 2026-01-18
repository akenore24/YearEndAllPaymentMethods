#!/usr/bin/env bash
set -euo pipefail

OUTDIR="docs/reference/help"
mkdir -p "$OUTDIR"

stamp() { date "+%Y-%m-%d %H:%M:%S"; }

write_help () {
  local name="$1"
  local cmd="$2"
  local out="$OUTDIR/${name}_HELP.txt"

  {
    echo "Generated: $(stamp)"
    echo "Command: $cmd"
    echo "============================================================"
    eval "$cmd"
    echo
  } > "$out"

  echo "Wrote: $out"
}

write_help_md () {
  local name="$1"
  local cmd="$2"
  local out="$OUTDIR/${name}_HELP.md"

  {
    echo "# ${name} — CLI Help"
    echo
    echo "**Generated:** $(stamp)  "
    echo "**Command:** \`$cmd\`"
    echo
    echo "---"
    echo
    echo '```text'
    eval "$cmd"
    echo '```'
    echo
  } > "$out"

  echo "Wrote: $out"
}


write_help "WF_TRANSFER_CLEANER" "python3 wf_transfer_cleaner.py --help"
write_help "GRAND_FINANCE_MASTER" "python3 grand_finance_master.py --help"
write_help "GRAND_FINANCE_MASTER_WF_TO_ALL" "python3 grand_finance_master.py wf_to_all --help"
write_help "FINANCE_MASTER" "python3 finance_master.py --help"
write_help "EXPENSES_18MO_REPORTS_STABLE" "python3 expenses_18mo_reports_stable.py --help"


write_help "WF_TRANSFER_CLEANER" "python3 wf_transfer_cleaner.py --help"
write_help_md "WF_TRANSFER_CLEANER" "python3 wf_transfer_cleaner.py --help"

write_help "GRAND_FINANCE_MASTER" "python3 grand_finance_master.py --help"
write_help_md "GRAND_FINANCE_MASTER" "python3 grand_finance_master.py --help"

write_help "GRAND_FINANCE_MASTER_WF_TO_ALL" "python3 grand_finance_master.py wf_to_all --help"
write_help_md "GRAND_FINANCE_MASTER_WF_TO_ALL" "python3 grand_finance_master.py wf_to_all --help"

write_help "FINANCE_MASTER" "python3 finance_master.py --help"
write_help_md "FINANCE_MASTER" "python3 finance_master.py --help"

write_help "EXPENSES_18MO_REPORTS_STABLE" "python3 expenses_18mo_reports_stable.py --help"
write_help_md "EXPENSES_18MO_REPORTS_STABLE" "python3 expenses_18mo_reports_stable.py --help"
