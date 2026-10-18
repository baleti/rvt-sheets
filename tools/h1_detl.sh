#!/bin/bash
# h1_detl.sh : Snowdon 55 detail 910139: our texts / leader lines vs Revit's A-DETL-IDEN layer (host1)
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
f=$(ls ~/rvt-research/corpus/*/55_Snowdon_Towers_Sample_Structural.rvt | head -1)
python tools/view_svg.py $f 910139 out/annot/v910139.svg 2>&1 | tail -1 | cut -c1-300
grep -o '<text[^>]*data-e="[0-9]*"[^>]*>.*</text>' out/annot/v910139.svg | sed 's/<[^>]*>//g' | head -20
python tools/compare_dxf.py $f 910139 ~/rvt-research/gt_views/2026_55_Snowdon_Towers_Sample_Structural/910139.dxf --register 2>&1 | grep -E '"precision"|"recall"|A-DETL-IDEN'
python tools/unm_dxf.py $f 910139 ~/rvt-research/gt_views/2026_55_Snowdon_Towers_Sample_Structural/910139.dxf 2>&1 | head -12
echo DONE
