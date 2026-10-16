#!/bin/bash
# dxf_all.sh OUT.tsv : compare_dxf (precision/recall vs Revit's DXF) for every view that has a gt DXF, for the 2020 Residential/Commercial/rst basic samples (host1 job)
out=$1; mkdir -p "$(dirname "$out")"; : > "$out"
C=~/rvt-research/corpus; G=~/rvt-research/gt_views
for name in 20_Residential_Sample_Project 19_Commercial_Sample_Project 18_rst_basic_sample_project; do
  for dxf in $G/2020_$name/*.dxf; do
    v=$(basename $dxf .dxf)
    timeout 600 python "$(dirname "$0")/compare_dxf.py" $C/2020/$name.rvt $v $dxf --register 2>/dev/null | python3 -c "
import sys,json
t=sys.stdin.read()
try:
    d=json.loads(t[t.index('{'):]); print('$name\t$v\t'+str(d.get('name'))+'\t%.3f\t%.3f'%(d['precision'],d['recall']))
except Exception as e: print('$name\t$v\terror')" >> "$out"
  done
done
echo DONE >> "$out"
