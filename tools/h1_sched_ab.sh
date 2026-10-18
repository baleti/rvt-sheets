#!/bin/bash
# h1_sched_ab.sh : host1 job: Residential Window Schedule sheet 236772 and Commercial sheets (206124 Details, 206143 Cover) with the old (1.2 em, 1.597 pitch) vs new (type size / 0.72, 1.917 pitch) 2020 schedule text rule, qa-view score of each
cd ~/src/rvt-sheets-annot; PY=$HOME/rvt-env/bin/python; QPY=$HOME/src/rvt-qa/.venv/bin/python; export QA_RENDER_PY=$PY RVTSHEETS_DIR=$HOME/src/rvt-sheets-annot; out=out/annot/sched_ab; mkdir -p $out
C=~/rvt-research/corpus/2020
for spec in 19_Commercial_Sample_Project:206124 19_Commercial_Sample_Project:206143; do
  f=${spec%%:*}; v=${spec##*:}
  num=$($PY - $C/$f.rvt $v <<'PY'
import sys; sys.path.insert(0,'.')
from rvtsheets.decode import Decoder
d=Decoder(sys.argv[1]).doc(); s=d['sheets'].get(int(sys.argv[2])) or d['sheets'].get(sys.argv[2]); print(s['sheetNumber'])
PY
)
  for mode in old new; do
    RVT_SCHED_EM=$mode RVT_SCHED_P=$mode $PY tools/sheet_svg.py $C/$f.rvt $out/$mode-$v "$num" >/dev/null 2>&1
    echo "== $f $v mode $mode sheet $num"; $QPY ~/src/rvt-qa/qa-view $C/$f.rvt $v --svg "$out/$mode-$v/$num.svg" 2>&1 | sed -n 1,3p | cut -c1-250
  done
done
echo DONE
