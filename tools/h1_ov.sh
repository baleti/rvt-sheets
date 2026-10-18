#!/bin/bash
# h1_ov.sh : host1: dxf_overlay (red Revit, blue ours) of Snowdon 2024 North elevation 201922 and South 4969
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH; mkdir -p out/annot/ov
f=$HOME/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
for v in 201922 4969; do python tools/dxf_overlay.py $f $v ~/rvt-research/gt_views/2024_43_Snowdon_Towers_Sample_Structural/$v.dxf out/annot/ov/$v.png 2>&1 | tail -1; done
echo DONE
