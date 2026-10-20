#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
python tools/dim_probe.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt 582085 > ~/dimp3.txt 2>&1; echo DONE >> ~/dimp3.txt
