#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
for v in 579516 582085 581553; do python tools/dim_probe.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt $v > ~/dimp_$v.txt 2>&1; done; echo DONE > ~/dimp.done
