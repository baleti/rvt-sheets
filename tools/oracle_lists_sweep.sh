#!/bin/bash
# oracle_lists_sweep.sh OUT : element-list P/R (tools/check_elements.py) of every oracle scene with a Revit per-view element list, new rules vs all the new rules switched off
cd "$(dirname "$0")/.."; PY=${PY:-$HOME/src/rvt-sheets/.venv/bin/python}; out=$1; : > $out
for v in $HOME/rvt-research/gt_views/*.rte.views; do
  b=$(basename $v .views); f=$(ls $HOME/rvt-research/vg-scenes/$b $HOME/rvt-research/rosetta/$b $HOME/rvt-research/rosetta/${b#*_} 2>/dev/null | head -1); [ -z "$f" ] && { echo "skip $b" >> $out; continue; }
  for mode in new old; do
    if [ $mode = old ]; then E="RVT_ROOM_PHASE=0 RVT_ARROW_PHASE=0 RVT_MARKER_CROP=0 RVT_DEPENDENT=0 RVT_SECFLAG7=0 RVT_ROOM_NOBOX=0 RVT_LINK_NOBOX=0"; else E="RVT_X=1"; fi
    r=$(env ALLOW_HOST3=${ALLOW_HOST3:-1} $E $PY tools/check_elements.py $f $v 2>&1 | grep '^ALL' | tail -1)
    echo "$b $mode $r" >> $out
  done
done
echo DONE >> $out
