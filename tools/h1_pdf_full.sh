#!/bin/bash
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
for f in 2024/43_Snowdon_Towers_Sample_Structural 2024/46_Snowdon_Towers_Sample_Facades; do python tools/pdf_text_all.py ~/rvt-research/corpus/$f.rvt > ~/pdf_full_$(basename $f | cut -c1-2).txt 2>&1; done; echo DONE > ~/pdf_full.done
