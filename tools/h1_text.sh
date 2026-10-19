#!/bin/bash
# h1_text.sh : host1 job: text offset tables (tools/text_pairs.py) for the Snowdon views QA flagged, then the annot sweep
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
mkdir -p out/annot/tp
C=~/rvt-research/corpus/2024/43_Snowdon_Towers_Sample_Structural.rvt
for v in 871873 594716 843511 201892; do python tools/text_pairs.py $C $v > out/annot/tp/$v.txt 2>&1; done
python tools/bst_dump.py $C 876061 > out/annot/tp/bst876061.txt 2>&1
echo TP DONE
bash tools/h1_dxfall.sh
