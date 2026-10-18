#!/bin/bash
# vg_regress.sh : element-list precision/recall of the 4 oracle corpus files (one job; run on host1: ~/.local/share/offload/h1run run vg-regress --env rvt --dir ~/src/rvt-sheets-vg -- tools/vg_regress.sh)
cd "$(dirname "$0")/.."; PY=${PY:-$HOME/rvt-env/bin/python}
for p in 2024/43_Snowdon_Towers_Sample_Structural 2020/20_Residential_Sample_Project 2020/19_Commercial_Sample_Project 2020/18_rst_basic_sample_project; do echo "## $p"; $PY tools/check_elements.py $HOME/rvt-research/corpus/$p.rvt 2>&1 | tail -5; done
