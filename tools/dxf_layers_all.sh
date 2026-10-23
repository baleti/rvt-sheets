#!/bin/bash
# dxf_layers_all.sh OUT.jsonl : compare_dxf JSON (with recall_by_revit_layer / precision_by_our_layer, ink in mm) for every 2020 view with a gt DXF (host1 job); aggregate with tools/agg_layers.py
out=$1; mkdir -p "$(dirname "$out")"; : > "$out"
C=~/rvt-research/corpus; G=~/rvt-research/gt_views
for name in 20_Residential_Sample_Project 19_Commercial_Sample_Project 18_rst_basic_sample_project; do
  for dxf in $G/2020_$name/*.dxf; do
    v=$(basename $dxf .dxf)
    timeout 600 python "$(dirname "$0")/compare_dxf.py" $C/2020/$name.rvt $v $dxf --register 2>/dev/null | python3 -c "
import sys,json
t=sys.stdin.read()
try:
    d=json.loads(t[t.index('{'):]); d['file']='$name'; print(json.dumps(d))
except Exception as e: pass" >> "$out"
  done
done
echo '{"done": 1}' >> "$out"
