#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
python tools/rule_ab.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt > ~/rule_ab_snow.txt 2>&1
echo DONE >> ~/rule_ab_snow.txt
