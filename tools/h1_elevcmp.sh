#!/bin/bash
# h1_elevcmp.sh : host1 job: Commercial East 29154 / South 29201 elevations DXF compare (layer breakdown)
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2020/19_Commercial_Sample_Project.rvt; G=~/rvt-research/gt_views/2020_19_Commercial_Sample_Project
mkdir -p out/c10
for v in 29154 29201; do
  python tools/compare_dxf.py $F $v $G/$v.dxf --register > out/c10/cmp$v.txt 2>&1
done
echo DONE
