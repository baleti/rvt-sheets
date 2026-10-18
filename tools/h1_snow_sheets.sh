#!/bin/bash
# h1_snow_sheets.sh : host1 job: Snowdon 55 sheets 779980 / 871873 full renders (with viewports) for text baseline checks, then the 910139 detail diagnosis (h1_detl.sh)
cd ~/src/rvt-sheets-annot; export PATH=$HOME/rvt-env/bin:$PATH
f=$(ls ~/rvt-research/corpus/*/55_Snowdon_Towers_Sample_Structural.rvt | head -1)
mkdir -p out/annot/snow
for sid in 779980 871873; do
  num=$(python - $f $sid <<'PY'
import sys; sys.path.insert(0,'.')
from rvtsheets.decode import Decoder
d=Decoder(sys.argv[1]).doc(); s=d['sheets'].get(int(sys.argv[2])) or d['sheets'].get(sys.argv[2]); print(s['sheetNumber'])
PY
)
  python tools/sheet_full.py $f out/annot/snow "$num" 2>&1 | tail -1
  mv "out/annot/snow/$num.svg" out/annot/snow/$sid.svg
done
bash tools/h1_detl.sh
echo DONE
