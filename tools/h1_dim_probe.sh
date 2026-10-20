#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
python tools/dim_probe.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt 581543 > ~/dim_probe_581543.txt 2>&1
echo DONE >> ~/dim_probe_581543.txt
