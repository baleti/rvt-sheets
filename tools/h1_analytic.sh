#!/bin/bash
# h1_analytic.sh : host1 job: rst_basic Analytical Model 1292652 + Structure (Complete) 1141621 + Roof Level 417295 DXF compare (layer breakdown) and vg report
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
F=~/rvt-research/corpus/2020/18_rst_basic_sample_project.rvt; G=~/rvt-research/gt_views/2020_18_rst_basic_sample_project
mkdir -p out/c10
for v in 1292652 1141621 417295; do
  python tools/compare_dxf.py $F $v $G/$v.dxf --register > out/c10/cmp$v.txt 2>&1
  python tools/vg_report.py $F $v > out/c10/rep$v.json 2>&1
done
echo DONE
