#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
python tools/pdf_text_all.py ~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt 594756 > ~/spot_check.txt 2>&1; echo DONE >> ~/spot_check.txt
