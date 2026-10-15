#!/bin/bash
# fid_all.sh OUTROOT : tools/fid_images.py for the 2020 files that have Revit exports (one process per file, sequential)
out=$1; mkdir -p "$out"
for p in 2020/20_Residential_Sample_Project:2020_20_Residential_Sample_Project 2020/19_Commercial_Sample_Project:2020_19_Commercial_Sample_Project; do
  a=${p%%:*}; b=${p##*:}
  timeout 5400 python "$(dirname "$0")/fid_images.py" ~/rvt-research/corpus/$a.rvt ~/rvt-research/gt_views/$b "$out/$b" > "$out/$b.log" 2>&1
done
echo DONE > "$out/DONE"
