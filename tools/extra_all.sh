#!/bin/bash
# extra_all.sh OUT.txt : tools/extra_elems.py (our elements with ink Revit's DXF lacks) for every comparable 2020 view, one block per view; aggregate with tools/agg_extra.py
out=$1; mkdir -p "$(dirname "$out")"; : > "$out"
C=~/rvt-research/corpus; G=~/rvt-research/gt_views
for name in 20_Residential_Sample_Project 19_Commercial_Sample_Project 18_rst_basic_sample_project; do
  for dxf in $G/2020_$name/*.dxf; do
    v=$(basename $dxf .dxf); echo "## $name $v" >> "$out"
    timeout 600 python "$(dirname "$0")/extra_elems.py" $C/2020/$name.rvt $v $dxf 2>/dev/null | grep "extra mm" >> "$out"
  done
done
echo "## DONE" >> "$out"
