#!/bin/bash
# dxf_table.sh REPO OUT [CLASS] [FILES] : compare_dxf (--register) for every view of CLASS with a Revit DXF in gt_views (fid9 results list the ids); one line per view, DONE at the end
repo=$1; out=$2; CLS=${3:-ViewPlan}; FILES=${4:-20_Residential_Sample_Project 19_Commercial_Sample_Project}; : > $out
for p in $FILES; do
  F=~/rvt-research/corpus/2020/$p.rvt; G=~/rvt-research/gt_views/2020_$p
  for v in $(python3 -c "
import json
for l in open('$repo/tools/views/2020_$p.jsonl'):
    d=json.loads(l)
    if d['class']=='$CLS': print(d['id'])"); do
    [ -f $G/$v.dxf ] || continue
    r=$(cd $repo && ${PY:-.venv/bin/python} tools/compare_dxf.py $F $v $G/$v.dxf --register 2>/dev/null | python3 -c "
import json,sys; t=sys.stdin.read(); d=json.loads(t[t.index('{'):]); print(round(d['precision'],3),round(d['recall'],3))")
    echo "$p $v $r" >> $out
  done
done
echo DONE >> $out
