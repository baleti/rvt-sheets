#!/bin/bash
# h1_all.sh : host1 job: elevation overlays first (short), then snowdon_l2_check + dxf_all sweep
cd ~/src/rvt-sheets-annot
bash tools/h1_ov.sh
bash tools/h1_dxfall.sh
