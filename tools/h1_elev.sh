#!/bin/bash
# h1_elev.sh : host1 job: Snowdon 2024 elevations (201922 North, 201907 East, 4969 South): unmatched ink per element (precision .73-.85)
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
f=$(ls ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt | head -1)
for v in 201922 4969; do
  echo "== $v"
  python tools/compare_dxf.py $f $v ~/rvt-research/gt_views/2024_43_Snowdon_Towers_Sample_Structural/$v.dxf --register 2>&1 | grep -E '"precision"|"recall"'
  python tools/unm_dxf.py $f $v ~/rvt-research/gt_views/2024_43_Snowdon_Towers_Sample_Structural/$v.dxf 2>&1 | head -14
done
echo DONE
