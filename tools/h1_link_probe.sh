#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
python tools/link_probe.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt > ~/link_probe_snow.txt 2>&1; echo DONE >> ~/link_probe_snow.txt
