#!/bin/bash
# cover3d.sh OUTDIR : host1: Snowdon 2024 CoverSheet 3D (923315) with RVT_TRANSP_FAINT 0 / 1
here=$(cd "$(dirname "$0")/.." && pwd); mkdir -p $1
F=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
for e in 1 0; do RVT_TRANSP_FAINT=$e python $here/tools/view_svg.py $F 923315 $1/cov$e.svg > $1/cov$e.log 2>&1; done
echo DONE > $1/DONE
