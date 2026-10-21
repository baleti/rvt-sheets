#!/bin/bash
# vg_dxf_all.sh YEAR : compare_dxf of every plan/section view of the oracle vg scenes (2024 default) -> one line per view; run on host3 capped or host1
cd "$(dirname "$0")/.."; Y=${1:-2024}; PY=${PY:-$HOME/src/rvt-sheets/.venv/bin/python}; G=$HOME/rvt-research/gt_views; SC=$HOME/rvt-research/vg-scenes
for sc in filters hide discipline phases templates templates_var worksets inverse links; do
  f=$SC/${Y}_vg_$sc.rte; [ -f $f ] || f=$SC/${Y}_vg_$sc.rvt; d=$G/${Y}_vg_$sc; [ -d $d ] || d=$G/${Y}_vg_$sc.rte; [ -d $d ] || continue
  for dxf in $d/*.dxf; do v=$(basename $dxf .dxf)
    echo -n "$sc $v "; RVT_LINKS=1 RVT_LINK_LISTED=1 RVT_LINK_DIRS=$SC ALLOW_HOST3=1 timeout 300 systemd-run --user --scope -q -p MemoryMax=3G -p MemorySwapMax=0 nice -n 19 $PY tools/compare_dxf.py $f $v $dxf 2>&1 | python3 -c "
import sys,json
try:
    d=json.loads(sys.stdin.read()); print(d['name'][:28], 'P %.3f R %.3f ours %.0f revit %.0f' % (d['precision'], d['recall'], d['ours_mm'], d['revit_mm']))
except Exception as e: print('ERR', e)"
  done
done
