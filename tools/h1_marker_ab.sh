#!/bin/bash
# element-list P/R of the 4 oracle corpus files with the marker discipline rule on (1) and off (0): host1 job
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
for m in 1 0; do echo "######## RVT_MARKER_DISC=$m"; RVT_MARKER_DISC=$m bash tools/vg_regress.sh 2>&1 | tail -40; done > ~/marker_ab.txt 2>&1
echo DONE >> ~/marker_ab.txt
