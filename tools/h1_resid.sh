#!/bin/bash
cd ~/src/rvt-sheets-vg; export PATH=$HOME/rvt-env/bin:$PATH
mkdir -p out/c10
python tools/occ_probe.py ~/rvt-research/corpus/2020/20_Residential_Sample_Project.rvt 9948 -6.55 44.82 > out/c10/occ9948.txt 2>&1
echo DONE
