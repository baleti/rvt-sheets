#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
python tools/spot_probe.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt 594756 > ~/spot_594756.txt 2>&1; echo DONE >> ~/spot_594756.txt
