#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
python tools/dim_probe.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt 581543 > ~/dimp4.txt 2>&1
python tools/dim_probe.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt 627226 > ~/dimp5.txt 2>&1
echo DONE >> ~/dimp5.txt
