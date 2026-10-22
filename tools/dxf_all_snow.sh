#!/bin/bash
# dxf_all_snow.sh OUT.tsv : compare_dxf for every Snowdon 2024 Structural view with a gt DXF (host1 job, like dxf_all.sh)
out=$1; mkdir -p "$(dirname "$out")"; : > "$out"
C=~/rvt-research/corpus; G=~/rvt-research/gt_views
name=43_Snowdon_Towers_Sample_Structural
for dxf in $G/2024_$name/*.dxf; do
  v=$(basename $dxf .dxf)
  timeout 900 python "$(dirname "$0")/compare_dxf.py" $C/2024/$name.rvt $v $dxf --register 2>/dev/null | python3 -c "
import sys,json
t=sys.stdin.read()
try:
    d=json.loads(t[t.index('{'):]); print('$name\t$v\t'+str(d.get('name'))+'\t%.3f\t%.3f'%(d['precision'],d['recall']))
except Exception as e: print('$name\t$v\terror')" >> "$out"
done
echo DONE >> "$out"
