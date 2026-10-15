#!/bin/bash
# dxf_all.sh OUTDIR : DXF P/R tables (tools/dxf_table.sh) for plans and sections of 2020 Residential + Commercial (host1 job)
here=$(cd "$(dirname "$0")/.." && pwd); out=$1; mkdir -p "$out"
for c in ViewPlan ViewSection; do PY=${PY:-python} "$here/tools/dxf_table.sh" "$here" "$out/$c.txt" $c; done
echo DONE > "$out/DONE"
