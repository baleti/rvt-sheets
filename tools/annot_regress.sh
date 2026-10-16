#!/bin/bash
# annot_regress.sh : qa-view SCORE / text recall of the annotation golden views (host3, one single-view render at a time, 2 GB cap)
# needs ~/src/rvt-qa (qa-view) and the Revit exports in ~/rvt-research/gt_views. Compare the output with tools/annot_regress.baseline
cd "$(dirname "$0")/.."
C=~/rvt-research/corpus
for a in "2020/20_Residential_Sample_Project 32" "2020/20_Residential_Sample_Project 36" "2020/20_Residential_Sample_Project 156499" "2020/20_Residential_Sample_Project 228085" \
         "2020/19_Commercial_Sample_Project 32" "2020/19_Commercial_Sample_Project 173631" "2020/19_Commercial_Sample_Project 195581" \
         "2020/18_rst_basic_sample_project 1064656" "2020/18_rst_basic_sample_project 1251893" "2020/18_rst_basic_sample_project 245443"; do
  set -- $a
  systemd-run --user --scope -q -p MemoryMax=2G nice ~/src/rvt-sheets/.venv/bin/python tools/view_svg.py $C/$1.rvt $2 /tmp/ar_$2.svg >/dev/null 2>&1
  systemd-run --user --scope -q -p MemoryMax=2G ~/src/rvt-qa/.venv/bin/python ~/src/rvt-qa/qa-view $C/$1.rvt $2 --svg /tmp/ar_$2.svg 2>&1 | sed -n 1,3p | tr '\n' ' ' | sed "s#^#$1 #" | cut -c1-230
  echo
done
