#!/bin/bash
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
mkdir -p out/c10
python tools/load_prims.py ~/rvt-research/corpus/2020/18_rst_basic_sample_project.rvt 417295 > out/c10/loadprims.txt 2>&1
echo DONE
